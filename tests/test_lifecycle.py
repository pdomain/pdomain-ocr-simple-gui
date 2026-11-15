"""Tests for server-owned browser leases and graceful shutdown decisions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest

from pdomain_ocr_simple_gui.lifecycle import (
    ExitReason,
    LifecycleController,
    LifecycleRejectedError,
    ShutdownState,
    WrongInstanceError,
)


@dataclass
class FakeClock:
    """A monotonic clock advanced explicitly by each test."""

    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@dataclass
class ExitRecorder:
    """Records graceful exit requests without stopping the test process."""

    requests: int = 0

    def __call__(self) -> None:
        self.requests += 1


def _controller(
    *,
    persistent: bool = False,
    keep_running: bool = False,
) -> tuple[LifecycleController, FakeClock, ExitRecorder]:
    clock = FakeClock()
    recorder = ExitRecorder()
    return (
        LifecycleController(
            "instance-1",
            clock=clock,
            request_exit=recorder,
            persistent=persistent,
            keep_running=keep_running,
        ),
        clock,
        recorder,
    )


def test_initial_grace_requests_exit_once_without_a_browser_connection() -> None:
    controller, clock, recorder = _controller()

    clock.advance(119.9)
    assert controller.evaluate() is False
    assert recorder.requests == 0

    clock.advance(0.1)
    assert controller.evaluate() is True
    assert controller.evaluate() is False

    snapshot = controller.snapshot()
    assert recorder.requests == 1
    assert snapshot.shutdown_state is ShutdownState.EXIT_REQUESTED
    assert snapshot.shutdown_reason is ExitReason.INITIAL_GRACE_EXPIRED


def test_connections_get_distinct_leases_and_last_tab_grace_cancels_on_reconnect() -> None:
    controller, clock, recorder = _controller()
    first = controller.attach("instance-1", "page-a")
    second = controller.attach("instance-1", "page-b")

    assert controller.detach(first) is True
    assert controller.snapshot().shutdown_deadline is None
    assert controller.detach(second) is True
    assert controller.snapshot().shutdown_deadline == 30.0

    clock.advance(29.0)
    replacement = controller.attach("instance-1", "page-c")
    assert replacement.page_id == "page-c"
    assert controller.snapshot().shutdown_deadline is None

    clock.advance(60.0)
    assert controller.evaluate() is False
    assert recorder.requests == 0


def test_replacement_connection_survives_predecessor_late_disconnect() -> None:
    controller, _, _ = _controller()
    original = controller.attach("instance-1", "page-a")
    replacement = controller.attach("instance-1", "page-a")

    assert replacement.generation == original.generation + 1
    assert controller.detach(original) is False
    assert controller.snapshot().active_leases == (replacement,)
    assert controller.detach(replacement) is True


def test_wrong_instance_is_rejected_and_old_instance_lease_cannot_detach() -> None:
    controller, _, _ = _controller()
    lease = controller.attach("instance-1", "page-a")

    with pytest.raises(WrongInstanceError):
        controller.attach("restarted-instance", "page-b")
    with pytest.raises(WrongInstanceError):
        controller.begin_activity("restarted-instance", "ocr")

    foreign_lease = lease.__class__(
        instance_id="restarted-instance",
        page_id=lease.page_id,
        generation=lease.generation,
    )
    assert controller.detach(foreign_lease) is False
    assert controller.snapshot().active_leases == (lease,)


def test_activity_defers_expired_last_tab_shutdown_until_every_operation_finishes() -> None:
    controller, clock, recorder = _controller()
    lease = controller.attach("instance-1", "page-a")
    assert controller.detach(lease) is True
    first = controller.begin_activity("instance-1", "ocr")
    second = controller.begin_activity("instance-1", "save")

    clock.advance(30.0)
    assert controller.evaluate() is False
    assert controller.snapshot().activity_kinds == ("ocr", "save")

    assert controller.end_activity(first) is True
    assert controller.evaluate() is False
    assert controller.end_activity(second) is True
    assert controller.evaluate() is True
    assert recorder.requests == 1


@pytest.mark.parametrize(
    ("persistent", "keep_running"),
    [(True, False), (False, True)],
)
def test_persistent_modes_opt_out_of_automatic_shutdown(persistent: bool, keep_running: bool) -> None:
    controller, clock, recorder = _controller(persistent=persistent, keep_running=keep_running)

    clock.advance(120.0)
    assert controller.evaluate() is False
    assert recorder.requests == 0
    assert controller.snapshot().shutdown_deadline is None


def test_quit_requires_confirmation_for_other_tabs_and_rejects_active_work() -> None:
    controller, _, recorder = _controller()
    controller.attach("instance-1", "page-a")
    controller.attach("instance-1", "page-b")

    pending = controller.prepare_quit(caller_page_id="page-a")
    assert pending.other_tab_count == 1
    assert pending.active_activity_count == 0
    assert pending.can_quit is False

    unconfirmed = controller.request_quit(confirm_other_tabs=False, caller_page_id="page-a")
    assert unconfirmed.accepted is False
    assert unconfirmed.other_tab_count == 1
    assert recorder.requests == 0

    activity = controller.begin_activity("instance-1", "upload")
    active = controller.request_quit(confirm_other_tabs=True)
    assert active.accepted is False
    assert active.active_activity_count == 1
    assert controller.end_activity(activity) is True

    accepted = controller.request_quit(confirm_other_tabs=True)
    assert accepted.accepted is True
    assert recorder.requests == 1
    assert controller.snapshot().shutdown_reason is ExitReason.USER_QUIT


def test_native_or_unidentified_quit_counts_every_live_tab_as_other() -> None:
    controller, _, recorder = _controller()
    _ = controller.attach("instance-1", "active-page")
    result = controller.request_quit(confirm_other_tabs=False)
    assert not result.accepted
    assert result.other_tab_count == 1
    assert recorder.requests == 0


def test_disconnected_page_cannot_claim_the_live_pages_quit_exemption() -> None:
    controller, _, recorder = _controller()
    _ = controller.attach("instance-1", "active-page")
    with pytest.raises(LifecycleRejectedError, match="connected"):
        _ = controller.request_quit(confirm_other_tabs=True, caller_page_id="not-connected")
    assert recorder.requests == 0


def test_exit_decision_rejects_later_connections_and_activity() -> None:
    controller, clock, _ = _controller()
    clock.advance(120.0)
    assert controller.evaluate() is True

    with pytest.raises(LifecycleRejectedError):
        controller.attach("instance-1", "page-a")
    with pytest.raises(LifecycleRejectedError):
        controller.begin_activity("instance-1", "ocr")


def test_concurrent_activity_completion_and_evaluation_requests_one_exit() -> None:
    controller, clock, recorder = _controller()
    lease = controller.attach("instance-1", "page-a")
    assert controller.detach(lease) is True
    activities = [controller.begin_activity("instance-1", "ocr") for _ in range(16)]
    clock.advance(30.0)

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(controller.end_activity, activities))
        results = list(executor.map(lambda _: controller.evaluate(), range(16)))

    assert sum(results) == 1
    assert recorder.requests == 1
    assert controller.snapshot().shutdown_state is ShutdownState.EXIT_REQUESTED


def test_concurrent_replacement_attaches_leave_one_latest_lease() -> None:
    controller, _, _ = _controller()

    with ThreadPoolExecutor(max_workers=12) as executor:
        leases = list(executor.map(lambda _: controller.attach("instance-1", "page-a"), range(24)))

    snapshot = controller.snapshot()
    assert snapshot.active_leases == (max(leases, key=lambda lease: lease.generation),)
    assert snapshot.active_leases[0].generation == 24

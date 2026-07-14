from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast, final

from statemachine import State, StateMachine
from statemachine.exceptions import StateMachineError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pdomain_ocr_simple_gui.models import PageResult

JobState = Literal["new", "queued", "running", "succeeded", "failed", "cancelled"]
JobLifecycleEvent = Literal[
    "queue",
    "start",
    "succeed",
    "fail",
    "cancel",
    "rerun_requested",
    "page_rerun",
]
JOB_STATES: tuple[JobState, ...] = ("new", "queued", "running", "succeeded", "failed", "cancelled")


class InvalidJobTransition(ValueError):  # noqa: N818
    """Raised when a job lifecycle event cannot be applied."""


@final
class JobLifecycleMachine(StateMachine):
    """Runtime statechart for backend job lifecycle transitions."""

    new = State("new", initial=True)
    queued = State("queued")
    running = State("running")
    succeeded = State("succeeded")
    failed = State("failed")
    cancelled = State("cancelled")

    queue = new.to(queued)
    start = queued.to(running)
    succeed = running.to(succeeded)
    fail = queued.to(failed) | running.to(failed)
    # Modeled but unreachable: no cancel endpoint ships yet
    # (ocr-container-meta#395, deferred). The frontend no-ops cancellation
    # (frontend/src/api/useOcrJob.ts).
    cancel = running.to(cancelled)
    rerun_requested = succeeded.to(queued) | failed.to(queued) | cancelled.to(queued)
    # Models in-place single-page rerun: a page can be rerun from a
    # succeeded or failed job without first cycling the whole job back
    # through "queued" (see aggregate_pages_state / routes/pages.py rerun_page).
    page_rerun = succeeded.to(running) | failed.to(running)


JOB_LIFECYCLE_BEHAVIOR: dict[tuple[str, str, str], tuple[str, ...]] = {
    ("new", "queue", "queued"): ("B-HOME-011",),
}


def transition_job_state(current: JobState, event: JobLifecycleEvent) -> JobState:
    """Apply a lifecycle event and return the next job state."""
    try:
        machine = JobLifecycleMachine(start_value=current)
        machine.send(event)  # pyright: ignore[reportUnknownMemberType] python-statemachine dispatch is dynamic.
    except StateMachineError as exc:
        raise InvalidJobTransition(f"cannot apply {event!r} from {current!r}") from exc
    next_state = cast("object", machine.current_state_value)
    if next_state not in JOB_STATES:
        raise InvalidJobTransition(f"invalid statechart result {next_state!r}")
    return next_state


def assert_job_transition(current: JobState, event: JobLifecycleEvent) -> JobState:
    """Validate a lifecycle event and return the next job state."""
    return transition_job_state(current, event)


# Maps (current, target) aggregate states to the machine event that models
# that move. Keeps per-page aggregation on the same validated transition
# path as every other job-state change, instead of writing the target state
# directly.
_AGG_EVENT: dict[tuple[JobState, JobState], JobLifecycleEvent] = {
    ("queued", "running"): "start",
    ("running", "succeeded"): "succeed",
    ("running", "failed"): "fail",
    ("queued", "failed"): "fail",
    ("succeeded", "running"): "page_rerun",
    ("failed", "running"): "page_rerun",
    ("succeeded", "queued"): "rerun_requested",
    ("failed", "queued"): "rerun_requested",
    ("cancelled", "queued"): "rerun_requested",
}


def aggregate_pages_state(pages: Sequence[PageResult], current: JobState) -> JobState:
    """Aggregate per-page states into the overall job state.

    Precedence for the target state — preserved exactly from the legacy
    inline aggregation this replaces: running > failed > all-succeeded >
    queued > keep current.

    The target is then reached by firing the machine event mapped in
    ``_AGG_EVENT`` for ``(current, target)``, so every aggregation result
    is a validated statechart transition rather than a directly-assigned
    state. An unmapped ``(current, target)`` pair raises
    ``InvalidJobTransition``, surfacing any divergence between this
    function's precedence and the machine's allowed moves instead of
    masking it.
    """
    all_states = {p.state for p in pages}
    target: JobState
    if "running" in all_states:
        target = "running"
    elif "failed" in all_states:
        target = "failed"
    elif all_states == {"succeeded"}:
        target = "succeeded"
    elif "queued" in all_states:
        target = "queued"
    else:
        target = current
    if target == current:
        return current
    try:
        event = _AGG_EVENT[(current, target)]
    except KeyError as exc:
        raise InvalidJobTransition(f"no aggregation event mapped for {current!r} -> {target!r}") from exc
    return transition_job_state(current, event)

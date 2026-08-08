from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast, final

from statemachine import State, StateMachine
from statemachine.exceptions import StateMachineError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pdomain_ocr_simple_gui.models import PageResult

JobState = Literal["new", "queued", "running", "succeeded", "failed"]
JobLifecycleEvent = Literal[
    "queue",
    "start",
    "succeed",
    "fail",
    "rerun_requested",
    "page_rerun",
]
JOB_STATES: tuple[JobState, ...] = ("new", "queued", "running", "succeeded", "failed")


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

    queue = new.to(queued)
    start = queued.to(running)
    succeed = running.to(succeeded)
    fail = queued.to(failed) | running.to(failed)
    rerun_requested = succeeded.to(queued) | failed.to(queued)
    # Models in-place single-page rerun: a page can be rerun from a
    # succeeded or failed job without first cycling the whole job back
    # through "queued" (see aggregate_pages_state / routes/pages.py rerun_page).
    page_rerun = succeeded.to(running) | failed.to(running)


JOB_LIFECYCLE_BEHAVIOR: dict[tuple[str, str, str], tuple[str, ...]] = {
    ("new", "queue", "queued"): ("B-HOME-011",),
}


def narrow_job_state(state: str) -> JobState:
    """Validate a wire-level state string and narrow it to the live JobState.

    The wire-level Literals (``ApiJobState`` / ``ProjectStatus.state`` /
    ``PageResult.state``) keep ``"cancelled"`` as a legal value for
    backward-compat with the shared frontend JobState type, even though the
    backend statechart no longer models it (ocr-container-meta#395: the
    ``cancel`` transition was unreachable and was stripped). A caller holding
    a wire-typed state must run it through this check before treating it as
    a machine ``JobState`` — a stored ``"cancelled"`` value, which nothing in
    this codebase writes anymore, raises ``InvalidJobTransition`` here
    instead of silently mismatching the static type.
    """
    if state not in JOB_STATES:
        raise InvalidJobTransition(f"not a valid job state: {state!r}")
    return state


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

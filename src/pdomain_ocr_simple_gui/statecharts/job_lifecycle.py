from __future__ import annotations

from typing import Literal, cast, final

from statemachine import State, StateMachine
from statemachine.exceptions import StateMachineError

JobState = Literal["new", "queued", "running", "succeeded", "failed", "cancelled"]
JobLifecycleEvent = Literal[
    "queue",
    "start",
    "succeed",
    "fail",
    "cancel",
    "rerun_requested",
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
    cancel = running.to(cancelled)
    rerun_requested = succeeded.to(queued) | failed.to(queued) | cancelled.to(queued)


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

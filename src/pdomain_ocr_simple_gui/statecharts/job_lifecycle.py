from __future__ import annotations

from typing import Literal

from statemachine import State, StateMachine

JobState = Literal["new", "queued", "running", "succeeded", "failed", "cancelled"]
JobLifecycleEvent = Literal[
    "queue",
    "start",
    "succeed",
    "fail",
    "cancel",
    "rerun_requested",
]


class InvalidJobTransition(ValueError):  # noqa: N818
    """Raised when a job lifecycle event cannot be applied."""


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


def transition_job_state(current: str, event: str) -> str:
    """Apply a lifecycle event and return the next job state."""
    try:
        machine = JobLifecycleMachine(start_value=current)
        machine.send(event)
    except Exception as exc:
        raise InvalidJobTransition(f"cannot apply {event!r} from {current!r}") from exc
    return str(machine.current_state_value)


def assert_job_transition(current: str, event: str) -> str:
    """Validate a lifecycle event and return the next job state."""
    return transition_job_state(current, event)

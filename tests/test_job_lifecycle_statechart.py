from typing import cast

import pytest

from pdomain_ocr_simple_gui import statecharts
from pdomain_ocr_simple_gui.statecharts.job_lifecycle import (
    JOB_LIFECYCLE_BEHAVIOR,
    InvalidJobTransition,
    JobLifecycleEvent,
    JobState,
    assert_job_transition,
    transition_job_state,
)


def test_statecharts_package_exports_public_lifecycle_adapter_names() -> None:
    assert statecharts.InvalidJobTransition is InvalidJobTransition
    assert statecharts.JobLifecycleEvent is JobLifecycleEvent
    assert statecharts.JobState is JobState
    assert statecharts.JOB_LIFECYCLE_BEHAVIOR is JOB_LIFECYCLE_BEHAVIOR
    assert statecharts.transition_job_state is transition_job_state
    assert statecharts.assert_job_transition is assert_job_transition
    assert statecharts.__all__ == (
        "JOB_LIFECYCLE_BEHAVIOR",
        "InvalidJobTransition",
        "JobLifecycleEvent",
        "JobState",
        "assert_job_transition",
        "transition_job_state",
    )


@pytest.mark.parametrize(
    ("current", "event", "expected"),
    [
        ("new", "queue", "queued"),
        ("queued", "start", "running"),
        ("queued", "fail", "failed"),
        ("running", "succeed", "succeeded"),
        ("running", "fail", "failed"),
        ("running", "cancel", "cancelled"),
        ("succeeded", "rerun_requested", "queued"),
        ("failed", "rerun_requested", "queued"),
        ("cancelled", "rerun_requested", "queued"),
    ],
)
def test_valid_job_lifecycle_transitions(
    current: JobState,
    event: JobLifecycleEvent,
    expected: JobState,
) -> None:
    assert transition_job_state(current, event) == expected


@pytest.mark.parametrize(
    ("current", "event"),
    [
        ("new", "start"),
        ("queued", "succeed"),
        ("succeeded", "start"),
        ("failed", "succeed"),
        ("cancelled", "fail"),
    ],
)
def test_invalid_job_lifecycle_transitions_raise(current: JobState, event: JobLifecycleEvent) -> None:
    with pytest.raises(InvalidJobTransition):
        _ = transition_job_state(current, event)


def test_invalid_starting_state_raises_invalid_job_transition() -> None:
    with pytest.raises(InvalidJobTransition):
        _ = transition_job_state(cast("JobState", cast("object", "bogus")), "queue")


def test_lifecycle_behavior_mapping_uses_documented_ids() -> None:
    """Machine-Covers: B-HOME-011"""
    assert JOB_LIFECYCLE_BEHAVIOR[("new", "queue", "queued")] == ("B-HOME-011",)

import pytest

from pdomain_ocr_simple_gui.statecharts.job_lifecycle import (
    JOB_LIFECYCLE_BEHAVIOR,
    InvalidJobTransition,
    transition_job_state,
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
def test_valid_job_lifecycle_transitions(current: str, event: str, expected: str) -> None:
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
def test_invalid_job_lifecycle_transitions_raise(current: str, event: str) -> None:
    with pytest.raises(InvalidJobTransition):
        transition_job_state(current, event)


def test_lifecycle_behavior_mapping_uses_documented_ids() -> None:
    assert JOB_LIFECYCLE_BEHAVIOR[("new", "queue", "queued")] == ("B-HOME-011",)

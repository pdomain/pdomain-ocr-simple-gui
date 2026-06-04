"""Single source of truth for the e2e test-job id prefix."""

from __future__ import annotations

TEST_JOB_PREFIX = "e2etestjob-"


def is_test_job(project_id: str) -> bool:
    """Return True if *project_id* is an ephemeral e2e test-job artifact.

    Test jobs are written by the e2e fixture layer with a well-known prefix so
    the backend can exclude them from user-facing listings and prefs.
    """
    return project_id.startswith(TEST_JOB_PREFIX)

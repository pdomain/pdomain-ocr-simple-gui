"""Single source of truth for the e2e test-job id prefixes."""

from __future__ import annotations

# Canonical seeding prefix — used when generating new test-job ids in fixtures.
TEST_JOB_PREFIX = "e2etestjob-"

# All known e2e fixture prefixes.  Any project_id starting with one of these
# is considered an ephemeral test artifact and excluded from user-facing
# listings, prefs recent_projects, and kept in purge operations.
# Keep in sync with the fixture assignments in tests/e2e/conftest.py.
TEST_JOB_PREFIXES: tuple[str, ...] = (
    "e2etestjob-",
    "e2etest2pg-",
    "e2ererun-",
    "e2efailed-",
    "e2eflowrerun-",
    "e2epgrerun-",
    "e2etestmgd-",
)


def is_test_job(project_id: str) -> bool:
    """Return True if *project_id* is an ephemeral e2e test-job artifact.

    Test jobs are written by the e2e fixture layer with a well-known prefix so
    the backend can exclude them from user-facing listings and prefs.
    """
    return any(project_id.startswith(prefix) for prefix in TEST_JOB_PREFIXES)

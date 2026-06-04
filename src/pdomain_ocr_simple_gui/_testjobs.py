"""Single source of truth for the e2e test-job signature.

A real user job's source is **never** under a pytest tmp directory.  That
content-based fact is the PRIMARY, false-positive-proof signature for an
ephemeral test artifact (see ``is_test_source_path``).  The legacy
``e2etestjob-`` id prefix family is a SECONDARY signal kept for back-compat
with jobs that fixtures seeded with a well-known prefix.

The leaked jobs CT observed in the real projects root are UUID-named (no
prefix) — they only match via the source-path signature, which is why the
prefix-only check that shipped earlier never hid or purged them.
"""

from __future__ import annotations

import re

# Canonical seeding prefix — used when generating new test-job ids in fixtures.
TEST_JOB_PREFIX = "e2etestjob-"

# All known e2e fixture prefixes.  Any project_id starting with one of these
# is considered an ephemeral test artifact and excluded from user-facing
# listings, prefs recent_projects, and removed in purge operations.
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

# pytest's tmp factory produces paths under ``/tmp/pytest-of-<user>/pytest-<n>``
# or ``/tmp/pytest-<n>`` (and the OS tmp dir may differ from /tmp, so we match a
# ``pytest-of-`` or ``pytest-<digit>`` path segment anywhere in the path).  Real
# user sources live under the uploads dir or arbitrary user folders and never
# contain these segments.
_PYTEST_TMP_RE = re.compile(r"(?:^|/)pytest-(?:of-|\d)")


def is_test_source_path(source_path: str) -> bool:
    """Return True when *source_path* points under a pytest tmp directory.

    This is a pure string predicate — it does NOT touch the filesystem — so it
    is safe to call on the runtime hot path and gives a deterministic answer
    regardless of whether the (now usually deleted) tmp dir still exists.

    A real user job's source is never under ``/tmp/pytest-*`` /
    ``pytest-of-*``, so this signature cannot false-positive on real jobs.
    """
    if not source_path:
        return False
    return _PYTEST_TMP_RE.search(source_path) is not None


def is_test_job(project_id: str, source_path: str = "") -> bool:
    """Return True if a project is an ephemeral e2e test-job artifact.

    Two complementary signatures:

    1. ``source_path`` is under a pytest tmp dir (PRIMARY, content-based,
       false-positive-proof — catches the UUID-named leaked jobs).
    2. ``project_id`` starts with a known fixture prefix (SECONDARY, legacy).

    *source_path* defaults to empty so existing prefix-only callers keep their
    original behavior; pass it to enable the robust content-based check.
    """
    if any(project_id.startswith(prefix) for prefix in TEST_JOB_PREFIXES):
        return True
    return is_test_source_path(source_path)

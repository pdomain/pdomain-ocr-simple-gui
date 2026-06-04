"""Unit tests for the central test-job signature in ``_testjobs``.

The robust signature is content-based: a real user job's source is never
under a pytest tmp dir (``/tmp/pytest-*`` / ``pytest-of-*``).  This is the
PRIMARY signal because it cannot false-positive on real jobs.  The legacy
``e2etestjob-`` id prefix is a secondary signal kept for back-compat.
"""

from __future__ import annotations

import pytest

from pdomain_ocr_simple_gui._testjobs import (
    is_test_job,
    is_test_source_path,
)


class TestIsTestSourcePath:
    """``is_test_source_path`` — pure string predicate, no disk access."""

    @pytest.mark.parametrize(
        "source_path",
        [
            "/tmp/pytest-of-vscode/pytest-411/test_e2e_job_completes0/source",
            "/tmp/pytest-of-root/pytest-1/test_x0/source",
            "/tmp/pytest-1247/test_page_view0/source",
            "/tmp/pytest-of-ubuntu/pytest-current/x",
        ],
    )
    def test_matches_pytest_tmp_paths(self, source_path: str) -> None:
        """Any /tmp/pytest-* style path is recognised as a test source."""
        assert is_test_source_path(source_path) is True

    @pytest.mark.parametrize(
        "source_path",
        [
            "",
            "/home/vscode/.local/share/pdomain-ocr-simple-gui/uploads/96eacdc1",
            "/home/user/scans",
            "/tmp/claude-1000/some-real-thing",
            "/data/books/vol1",
        ],
    )
    def test_does_not_match_real_paths(self, source_path: str) -> None:
        """Real user source paths are never flagged."""
        assert is_test_source_path(source_path) is False

    def test_is_pure_string_predicate_no_disk_access(self) -> None:
        """Predicate must not depend on the path existing on disk.

        It returns True for a non-existent pytest tmp path, proving it is a
        pure string test (safe for runtime filtering where the source dir may
        or may not still exist).
        """
        assert is_test_source_path("/tmp/pytest-999/never/existed/source") is True


class TestIsTestJob:
    """``is_test_job`` — prefix OR test-source-path signature."""

    def test_legacy_prefix_still_matches(self) -> None:
        """The legacy e2etestjob- id prefix is still recognised."""
        assert is_test_job("e2etestjob-abc") is True

    def test_other_known_prefixes_still_match(self) -> None:
        """Other legacy fixture prefixes still match."""
        assert is_test_job("e2ererun-xyz") is True

    def test_uuid_id_with_pytest_source_matches(self) -> None:
        """A UUID-named job with a pytest-tmp source is flagged (the real leak)."""
        assert (
            is_test_job(
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                source_path="/tmp/pytest-411/test_e2e0/source",
            )
            is True
        )

    def test_uuid_id_with_real_source_is_not_a_test_job(self) -> None:
        """A UUID-named job with a real uploads source is NOT flagged."""
        assert (
            is_test_job(
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                source_path="/home/vscode/.local/share/pdomain-ocr-simple-gui/uploads/abc",
            )
            is False
        )

    def test_default_source_path_preserves_prefix_only_behavior(self) -> None:
        """Calling with only project_id keeps the original prefix-only semantics."""
        assert is_test_job("ocr-job-abc123") is False
        assert is_test_job("e2etestjob-abc") is True

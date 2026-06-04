"""Tests for the purge_test_jobs script."""

from __future__ import annotations

import json
from pathlib import Path


class TestPurgeTestJobs:
    """purge() removes e2etestjob-* dirs and cleans prefs recent_projects."""

    def test_removes_test_job_dir(self, tmp_path: Path) -> None:
        """purge() removes e2etestjob-* directory from projects_root."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        # Create a test job dir
        (projects_root / "e2etestjob-a").mkdir()
        # Create a real job dir that must be kept
        (projects_root / "keep-b").mkdir()

        removed = purge(projects_root=projects_root)

        assert not (projects_root / "e2etestjob-a").exists()
        assert (projects_root / "keep-b").exists()
        assert "e2etestjob-a" in removed

    def test_returns_list_of_removed_ids(self, tmp_path: Path) -> None:
        """purge() returns the ids of removed test job dirs."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        (projects_root / "e2etestjob-one").mkdir()
        (projects_root / "e2etestjob-two").mkdir()
        (projects_root / "real-three").mkdir()

        removed = purge(projects_root=projects_root)

        assert set(removed) == {"e2etestjob-one", "e2etestjob-two"}

    def test_keep_b_remains_after_purge(self, tmp_path: Path) -> None:
        """Non-test-prefixed dirs survive purge."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        (projects_root / "e2etestjob-a").mkdir()
        (projects_root / "keep-b").mkdir()

        purge(projects_root=projects_root)

        assert (projects_root / "keep-b").exists()

    def test_drops_test_ids_from_prefs_recent_projects(self, tmp_path: Path) -> None:
        """purge() removes matching ids from prefs recent_projects."""
        from pdomain_ops.suite.prefs import LocalFilePrefs  # pyright: ignore[reportMissingTypeStubs]

        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()

        # Create test job dir
        (projects_root / "e2etestjob-a").mkdir()

        # Create a prefs file with the test job id in recent_projects
        prefs_root = tmp_path / "suite_data"
        prefs_root.mkdir()
        prefs_file = prefs_root / "ui-prefs.json"
        prefs_data = {
            "common": {},
            "apps": {
                "pdomain-ocr-simple-gui": {
                    "recent_projects": [
                        {"project_id": "e2etestjob-a", "name": "Test A"},
                        {"project_id": "real-keep", "name": "Real"},
                    ]
                }
            },
        }
        prefs_file.write_text(json.dumps(prefs_data), encoding="utf-8")

        # LocalFilePrefs takes the full path to the JSON file, not a directory
        adapter = LocalFilePrefs(root=prefs_file)
        purge(projects_root=projects_root, prefs_adapter=adapter)

        updated = adapter.read()
        app_prefs = updated.apps.get("pdomain-ocr-simple-gui", {})
        recent = app_prefs.get("recent_projects", [])  # type: ignore[union-attr]
        ids = [entry.get("project_id") for entry in recent]  # type: ignore[union-attr]
        assert "e2etestjob-a" not in ids
        assert "real-keep" in ids

    def test_empty_projects_root_returns_empty_list(self, tmp_path: Path) -> None:
        """purge() on a non-existent or empty root returns empty list without error."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        missing = tmp_path / "nonexistent"
        removed = purge(projects_root=missing)
        assert removed == []

    def test_no_test_jobs_returns_empty_list(self, tmp_path: Path) -> None:
        """purge() when there are no test jobs returns empty list."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        (projects_root / "real-a").mkdir()
        (projects_root / "real-b").mkdir()

        removed = purge(projects_root=projects_root)
        assert removed == []

    def test_removes_from_output_and_jobs_meta_roots(self, tmp_path: Path) -> None:
        """purge() removes test-job dirs from output_root and jobs_meta_root too."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        output_root = tmp_path / "outputs"
        jobs_meta_root = tmp_path / "jobs_meta"
        for d in (projects_root, output_root, jobs_meta_root):
            d.mkdir()

        # Seed a test job across all three roots
        (projects_root / "e2etestjob-abc").mkdir()
        (output_root / "e2etestjob-abc").mkdir()
        (jobs_meta_root / "e2etestjob-abc").mkdir()

        # Seed a real job in all three roots — must be kept
        (projects_root / "real-job-1").mkdir()
        (output_root / "real-job-1").mkdir()
        (jobs_meta_root / "real-job-1").mkdir()

        removed = purge(
            projects_root=projects_root,
            output_root=output_root,
            jobs_meta_root=jobs_meta_root,
        )

        # Test dirs removed from all three roots
        assert not (projects_root / "e2etestjob-abc").exists()
        assert not (output_root / "e2etestjob-abc").exists()
        assert not (jobs_meta_root / "e2etestjob-abc").exists()

        # Real dirs kept in all three roots
        assert (projects_root / "real-job-1").exists()
        assert (output_root / "real-job-1").exists()
        assert (jobs_meta_root / "real-job-1").exists()

        assert "e2etestjob-abc" in removed

    def test_removed_ids_deduped_across_roots(self, tmp_path: Path) -> None:
        """purge() returns a deduplicated list when a job exists in multiple roots."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        output_root = tmp_path / "outputs"
        jobs_meta_root = tmp_path / "jobs_meta"
        for d in (projects_root, output_root, jobs_meta_root):
            d.mkdir()

        # Same id present in all three roots
        (projects_root / "e2etestjob-dup").mkdir()
        (output_root / "e2etestjob-dup").mkdir()
        (jobs_meta_root / "e2etestjob-dup").mkdir()

        removed = purge(
            projects_root=projects_root,
            output_root=output_root,
            jobs_meta_root=jobs_meta_root,
        )

        # Must appear exactly once despite being in 3 roots
        assert removed.count("e2etestjob-dup") == 1

    def test_partial_presence_still_removed(self, tmp_path: Path) -> None:
        """purge() removes from whichever roots contain the test-job dir."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        output_root = tmp_path / "outputs"
        jobs_meta_root = tmp_path / "jobs_meta"
        for d in (projects_root, output_root, jobs_meta_root):
            d.mkdir()

        # Job only exists in projects_root and output_root (no jobs_meta entry)
        (projects_root / "e2ererun-xyz").mkdir()
        (output_root / "e2ererun-xyz").mkdir()

        removed = purge(
            projects_root=projects_root,
            output_root=output_root,
            jobs_meta_root=jobs_meta_root,
        )

        assert not (projects_root / "e2ererun-xyz").exists()
        assert not (output_root / "e2ererun-xyz").exists()
        assert "e2ererun-xyz" in removed


# ---------------------------------------------------------------------------
# Spec-aligned signature tests (FIX 3 — REAL mechanism for the leaked jobs).
#
# Robust signature: spec.source_path under a pytest tmp dir (PRIMARY, cannot
# false-positive), OR the legacy e2etestjob- id prefix, OR a degenerate
# empty-name/empty-source/zero-page artifact.  ocr-job-* and any job with a
# real source or real pages are always preserved.
# ---------------------------------------------------------------------------


def _write_project_json(
    proj_dir: Path,
    *,
    name: str,
    source_path: str = "",
    page_count: int = 0,
) -> None:
    """Write a minimal project.json (spec + status) into *proj_dir*."""
    proj_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "spec": {
            "project_id": proj_dir.name,
            "name": name,
            "source_path": source_path,
        },
        "status": {"project_id": proj_dir.name, "page_count": page_count, "pages": []},
    }
    (proj_dir / "project.json").write_text(json.dumps(data), encoding="utf-8")


class TestClassifyEntry:
    """classify_entry buckets each project dir into the right category."""

    def test_pytest_tmp_source_uuid_dir(self, tmp_path: Path) -> None:
        """A UUID dir with a /tmp/pytest-* source -> pytest-tmp-source."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import CAT_PYTEST_SOURCE, classify_entry

        pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        _write_project_json(
            tmp_path / pid,
            name="e2e-smoke",
            source_path="/tmp/pytest-of-vscode/pytest-411/test_e2e0/source",
        )
        assert classify_entry(tmp_path / pid) == CAT_PYTEST_SOURCE

    def test_legacy_prefix_dir(self, tmp_path: Path) -> None:
        """A dir whose name carries the legacy prefix -> legacy-prefix (no IO)."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import CAT_LEGACY_PREFIX, classify_entry

        d = tmp_path / "e2etestjob-abc"
        d.mkdir()
        assert classify_entry(d) == CAT_LEGACY_PREFIX

    def test_degenerate_empty_dir(self, tmp_path: Path) -> None:
        """Empty name + empty source + zero pages -> degenerate-empty."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import CAT_DEGENERATE, classify_entry

        pid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
        _write_project_json(tmp_path / pid, name="", source_path="", page_count=0)
        assert classify_entry(tmp_path / pid) == CAT_DEGENERATE

    def test_real_ocr_job_kept(self, tmp_path: Path) -> None:
        """A canonical ocr-job-* job with a real source -> keep."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import CAT_KEEP, classify_entry

        pid = "cccccccc-1111-1111-1111-111111111111"
        _write_project_json(
            tmp_path / pid,
            name="ocr-job-abc123",
            source_path="/home/vscode/.local/share/pdomain-ocr-simple-gui/uploads/abc",
            page_count=3,
        )
        assert classify_entry(tmp_path / pid) == CAT_KEEP

    def test_real_source_with_test_like_name_kept(self, tmp_path: Path) -> None:
        """A job named e2e-smoke but with a non-tmp source is KEPT (source wins)."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import CAT_KEEP, classify_entry

        pid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        _write_project_json(
            tmp_path / pid,
            name="e2e-smoke",
            source_path="/home/user/scans/source",
            page_count=2,
        )
        assert classify_entry(tmp_path / pid) == CAT_KEEP

    def test_job_with_pages_never_degenerate(self, tmp_path: Path) -> None:
        """A job with real pages is never classified degenerate even if name/source empty."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import CAT_KEEP, classify_entry

        pid = "eeeeeeee-2222-2222-2222-222222222222"
        _write_project_json(tmp_path / pid, name="", source_path="", page_count=5)
        assert classify_entry(tmp_path / pid) == CAT_KEEP


class TestSummarize:
    """summarize() returns per-category id lists without deleting anything."""

    def test_buckets_and_no_deletion(self, tmp_path: Path) -> None:
        """summarize() classifies all dirs and leaves them on disk."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import (
            CAT_DEGENERATE,
            CAT_KEEP,
            CAT_LEGACY_PREFIX,
            CAT_PYTEST_SOURCE,
            summarize,
        )

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        _write_project_json(
            projects_root / "leak-uuid",
            name="e2e-smoke",
            source_path="/tmp/pytest-411/test_x0/source",
        )
        (projects_root / "e2etestjob-old").mkdir()
        _write_project_json(projects_root / "degen", name="", source_path="", page_count=0)
        _write_project_json(
            projects_root / "real-uuid",
            name="ocr-job-zzz",
            source_path="/home/user/uploads/zzz",
            page_count=1,
        )

        buckets = summarize(projects_root=projects_root)
        assert buckets[CAT_PYTEST_SOURCE] == ["leak-uuid"]
        assert buckets[CAT_LEGACY_PREFIX] == ["e2etestjob-old"]
        assert buckets[CAT_DEGENERATE] == ["degen"]
        assert buckets[CAT_KEEP] == ["real-uuid"]
        # Nothing deleted.
        for name in ("leak-uuid", "e2etestjob-old", "degen", "real-uuid"):
            assert (projects_root / name).exists()


class TestSignaturePurgeIntegration:
    """purge() deletes only leaked jobs and preserves real jobs; dry-run is safe."""

    def test_purge_removes_pytest_tmp_source_uuid_dir(self, tmp_path: Path) -> None:
        """purge() removes a UUID dir whose source is under /tmp/pytest-*."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        _write_project_json(
            projects_root / pid,
            name="e2e-smoke",
            source_path="/tmp/pytest-of-vscode/pytest-411/test_e2e0/source",
        )
        _write_project_json(
            projects_root / "real-uuid",
            name="ocr-job-abc",
            source_path="/home/user/uploads/abc",
            page_count=2,
        )

        removed = purge(projects_root=projects_root)
        assert pid in removed
        assert not (projects_root / pid).exists()
        assert (projects_root / "real-uuid").exists()

    def test_purge_removes_degenerate_dir(self, tmp_path: Path) -> None:
        """purge() removes the empty-name/empty-source/zero-page artifact."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        pid = "dddddddd-dddd-dddd-dddd-dddddddddddd"
        _write_project_json(projects_root / pid, name="", source_path="", page_count=0)

        removed = purge(projects_root=projects_root)
        assert pid in removed

    def test_purge_preserves_real_ocr_job(self, tmp_path: Path) -> None:
        """purge() never removes a canonical ocr-job-* job."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        pid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
        _write_project_json(
            projects_root / pid,
            name="ocr-job-abc12345",
            source_path="/home/user/uploads/x",
            page_count=4,
        )

        removed = purge(projects_root=projects_root)
        assert pid not in removed
        assert (projects_root / pid).exists()

    def test_purge_preserves_real_source_even_with_test_name(self, tmp_path: Path) -> None:
        """purge() keeps a job whose source is NOT under pytest tmp, regardless of name."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        pid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        _write_project_json(
            projects_root / pid,
            name="e2e-smoke",
            source_path="/home/user/scans/source",
            page_count=2,
        )

        removed = purge(projects_root=projects_root)
        assert pid not in removed
        assert (projects_root / pid).exists()

    def test_dry_run_deletes_nothing(self, tmp_path: Path) -> None:
        """purge(dry_run=True) returns ids but removes no directories."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        _write_project_json(
            projects_root / pid,
            name="e2e-smoke",
            source_path="/tmp/pytest-411/test_e2e0/source",
        )

        removed = purge(projects_root=projects_root, dry_run=True)
        assert pid in removed
        assert (projects_root / pid).exists()  # nothing actually deleted

    def test_purge_propagates_leaked_ids_to_mirror_roots(self, tmp_path: Path) -> None:
        """A leaked id detected in projects root is also removed from output/jobs-meta."""
        from pdomain_ocr_simple_gui.scripts.purge_test_jobs import purge

        projects_root = tmp_path / "projects"
        output_root = tmp_path / "output"
        jobs_meta_root = tmp_path / "jobs_meta"
        for r in (projects_root, output_root, jobs_meta_root):
            r.mkdir()

        pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        # project.json only lives in projects root; mirror roots are bare dirs.
        _write_project_json(
            projects_root / pid,
            name="e2e-smoke",
            source_path="/tmp/pytest-411/test_e2e0/source",
        )
        (output_root / pid).mkdir()
        (jobs_meta_root / pid).mkdir()

        removed = purge(
            projects_root=projects_root,
            output_root=output_root,
            jobs_meta_root=jobs_meta_root,
        )
        assert pid in removed
        assert not (projects_root / pid).exists()
        assert not (output_root / pid).exists()
        assert not (jobs_meta_root / pid).exists()

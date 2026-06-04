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

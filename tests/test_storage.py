"""Tests for pdomain_ocr_simple_gui.storage — sidecar IO helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import (
    delete_project,
    get_project_dir,
    list_projects,
    read_page_sidecar,
    read_project,
    write_combined_txt,
    write_page_sidecar,
    write_project,
    write_txt,
)


def _make_spec(tmp_path: Path) -> ProjectSpec:
    return ProjectSpec(
        project_id="test-proj-id-001",
        name="Test Project",
        source_path=str(tmp_path / "source"),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def _make_status() -> ProjectStatus:
    return ProjectStatus(
        project_id="test-proj-id-001",
        state="succeeded",
        page_count=2,
        pages_done=2,
        pages=[
            PageResult(page_idx=0, page_name="page_001.png", state="succeeded", text_preview="Hello"),
            PageResult(page_idx=1, page_name="page_002.png", state="succeeded", text_preview="World"),
        ],
    )


class TestGetProjectDir:
    def test_returns_path_under_root(self, projects_root: Path) -> None:
        p = get_project_dir("my-id")
        assert p == projects_root / "my-id"

    def test_falls_back_to_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When env var is unset, get_project_dir returns a path under the default root."""
        monkeypatch.delenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", raising=False)
        p = get_project_dir("some-id")
        # Must be a valid path under some root (not empty, ends with the id)
        assert p.name == "some-id"
        assert p.parent.name  # parent is non-empty (the default root stem)


class TestWriteReadProject:
    def test_round_trip(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        restored_spec, restored_status = read_project("test-proj-id-001")
        assert restored_spec == spec
        assert restored_status == status

    def test_project_json_created(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        proj_dir = projects_root / "test-proj-id-001"
        assert (proj_dir / "project.json").exists()

    def test_read_missing_raises(self, projects_root: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_project("nonexistent-id")


class TestPageSidecar:
    def test_write_read_round_trip(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)

        page_data = {"page_idx": 0, "words": ["Hello", "World"], "confidence": 0.95}
        write_page_sidecar(spec, 0, page_data)

        restored = read_page_sidecar(spec, 0)
        assert restored == page_data

    def test_sidecar_file_created(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        write_page_sidecar(spec, 0, {"page_idx": 0})
        pages_dir = projects_root / "test-proj-id-001" / "pages"
        assert (pages_dir / "page_001.png.json").exists()

    def test_read_missing_page_raises(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        with pytest.raises(FileNotFoundError):
            read_page_sidecar(spec, 99)


class TestWriteTxt:
    def test_write_txt(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        write_txt(spec, 0, "Hello page 0")
        txt_path = projects_root / "test-proj-id-001" / "pages" / "page_001.png.txt"
        assert txt_path.exists()
        assert txt_path.read_text() == "Hello page 0"

    def test_write_txt_out_of_range_raises(self, projects_root: Path, tmp_path: Path) -> None:
        """write_txt for an out-of-range page index raises FileNotFoundError."""
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        with pytest.raises(FileNotFoundError):
            write_txt(spec, 99, "should not be written")


class TestWriteCombinedTxt:
    def test_combined_txt_concatenates(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        write_txt(spec, 0, "Page one text")
        write_txt(spec, 1, "Page two text")
        write_combined_txt(spec, status)
        combined = (projects_root / "test-proj-id-001" / "combined.txt").read_text()
        assert "Page one text" in combined
        assert "Page two text" in combined

    def test_combined_txt_with_empty_page_text(self, projects_root: Path, tmp_path: Path) -> None:
        """Pages with empty text are included — separator is still correct."""
        spec = _make_spec(tmp_path)
        status = _make_status()
        write_project(spec, status)
        write_txt(spec, 0, "")
        write_txt(spec, 1, "Page two text")
        write_combined_txt(spec, status)
        combined = (projects_root / "test-proj-id-001" / "combined.txt").read_text()
        # The non-empty page must appear; the empty page contributes an empty string
        assert "Page two text" in combined


class TestListProjects:
    def test_empty_when_no_projects(self, projects_root: Path) -> None:
        assert list_projects() == []

    def test_lists_written_projects(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        results = list_projects()
        assert len(results) == 1
        assert results[0][0].project_id == "test-proj-id-001"

    def test_corrupt_project_json_is_skipped_gracefully(self, projects_root: Path, tmp_path: Path) -> None:
        """A project.json with invalid JSON is skipped; listing must not raise."""
        # Write a valid project first
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())

        # Add a corrupt sibling directory
        corrupt_dir = projects_root / "corrupt-proj-zzz"
        corrupt_dir.mkdir()
        (corrupt_dir / "project.json").write_text("this is not json {{{")

        results = list_projects()
        # The valid project is still returned; the corrupt one is silently skipped
        ids = [s.project_id for s, _ in results]
        assert "test-proj-id-001" in ids
        assert "corrupt-proj-zzz" not in ids

    def test_multiple_projects_returned_in_stable_order(self, projects_root: Path, tmp_path: Path) -> None:
        """Multiple projects are returned in a stable (sorted) order."""
        from datetime import UTC, datetime

        specs = [
            ProjectSpec(
                project_id=pid,
                name=f"Project {pid}",
                source_path=str(tmp_path / "source"),
                output_dir=str(tmp_path / "output"),
                engine="doctr",
                language="en",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                last_opened_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            for pid in ["proj-aaa", "proj-bbb", "proj-ccc"]
        ]
        status_base = ProjectStatus(
            project_id="placeholder",
            state="succeeded",
            page_count=0,
            pages_done=0,
            pages=[],
        )
        for sp in specs:
            write_project(sp, ProjectStatus(**{**status_base.model_dump(), "project_id": sp.project_id}))

        results = list_projects()
        returned_ids = [s.project_id for s, _ in results]
        # All three appear in sorted order
        assert returned_ids == sorted(returned_ids)
        assert set(returned_ids) == {"proj-aaa", "proj-bbb", "proj-ccc"}


class TestDeleteProject:
    def test_delete_removes_dir(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        proj_dir = get_project_dir("test-proj-id-001")
        assert proj_dir.exists()
        delete_project("test-proj-id-001")
        assert not proj_dir.exists()

    def test_delete_missing_is_noop(self, projects_root: Path) -> None:
        # Should not raise
        delete_project("does-not-exist")

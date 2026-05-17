"""Tests for pd_ocr_simple_gui.storage — sidecar IO helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pd_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pd_ocr_simple_gui.storage import (
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
        state="done",
        page_count=2,
        pages_done=2,
        pages=[
            PageResult(page_idx=0, page_name="page_001.png", state="done", text_preview="Hello"),
            PageResult(page_idx=1, page_name="page_002.png", state="done", text_preview="World"),
        ],
    )


@pytest.fixture
def projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect storage root to tmp_path."""
    root = tmp_path / "projects"
    root.mkdir()
    import pd_ocr_simple_gui.storage as storage_mod

    monkeypatch.setattr(storage_mod, "_PROJECTS_ROOT", root)
    return root


class TestGetProjectDir:
    def test_returns_path_under_root(self, projects_root: Path) -> None:
        p = get_project_dir("my-id")
        assert p == projects_root / "my-id"


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


class TestListProjects:
    def test_empty_when_no_projects(self, projects_root: Path) -> None:
        assert list_projects() == []

    def test_lists_written_projects(self, projects_root: Path, tmp_path: Path) -> None:
        spec = _make_spec(tmp_path)
        write_project(spec, _make_status())
        results = list_projects()
        assert len(results) == 1
        assert results[0][0].project_id == "test-proj-id-001"


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

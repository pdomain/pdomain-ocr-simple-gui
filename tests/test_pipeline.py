"""Tests for pipeline.py — collect_images + run_project."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.pipeline import collect_images, run_project


def _make_spec(tmp_path: Path, source_path: str | None = None) -> ProjectSpec:
    from datetime import UTC, datetime

    return ProjectSpec(
        project_id="proj-test-001",
        name="Test Project",
        source_path=source_path or str(tmp_path / "source"),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        save_json=False,
        combined_txt=False,
        created_at=datetime.now(UTC),
        last_opened_at=datetime.now(UTC),
    )


def _make_stub_stage_result(page_id: str, page_dict: dict[str, Any]):
    """Build a minimal StageResult with the given page dict as metadata."""
    from pdomain_ops.gpu.types import StageResult

    return StageResult(
        stage_id="ocr",
        page_id=page_id,
        device="cpu",
        duration_ms=10,
        metadata={"pages": [page_dict]},
    )


EMPTY_PAGE_DICT: dict[str, Any] = {
    "type": "Page",
    "width": 100,
    "height": 100,
    "page_index": 0,
    "bounding_box": None,
    "items": [],
    "ocr_provenance": None,
}

SIMPLE_PAGE_DICT: dict[str, Any] = {
    "type": "Page",
    "width": 100,
    "height": 100,
    "page_index": 0,
    "bounding_box": None,
    "items": [
        {
            "type": "Block",
            "child_type": "WORD",
            "block_category": None,
            "block_labels": [],
            "block_role_labels": [],
            "block_position_labels": [],
            "line_role_labels": [],
            "line_position_labels": [],
            "baseline": None,
            "bounding_box": None,
            "items": [
                {
                    "type": "Word",
                    "text": "Hello",
                    "bounding_box": None,
                    "ocr_confidence": 0.9,
                    "word_labels": [],
                    "text_style_labels": [],
                    "text_style_label_scopes": [],
                    "word_components": [],
                    "baseline": None,
                    "ground_truth_text": None,
                    "ground_truth_bounding_box": None,
                    "ground_truth_match_keys": [],
                },
                {
                    "type": "Word",
                    "text": "world",
                    "bounding_box": None,
                    "ocr_confidence": 0.85,
                    "word_labels": [],
                    "text_style_labels": [],
                    "text_style_label_scopes": [],
                    "word_components": [],
                    "baseline": None,
                    "ground_truth_text": None,
                    "ground_truth_bounding_box": None,
                    "ground_truth_match_keys": [],
                },
            ],
            "override_page_sort_order": None,
            "unmatched_ground_truth_words": [],
            "additional_block_attributes": {},
            "base_ground_truth_text": "",
        }
    ],
    "ocr_provenance": None,
}


class TestCollectImages:
    async def test_returns_sorted_png_files(self, tmp_path: Path) -> None:
        src = tmp_path / "imgs"
        src.mkdir()
        (src / "c.png").touch()
        (src / "a.png").touch()
        (src / "b.png").touch()
        result = await collect_images(str(src))
        names = [p.name for p in result]
        assert names == ["a.png", "b.png", "c.png"]

    async def test_returns_jpg_and_tiff(self, tmp_path: Path) -> None:
        src = tmp_path / "imgs"
        src.mkdir()
        (src / "a.jpg").touch()
        (src / "b.jpeg").touch()
        (src / "c.tiff").touch()
        (src / "d.tif").touch()
        result = await collect_images(str(src))
        exts = {p.suffix.lower() for p in result}
        assert exts == {".jpg", ".jpeg", ".tiff", ".tif"}

    async def test_skips_non_image_files(self, tmp_path: Path) -> None:
        src = tmp_path / "imgs"
        src.mkdir()
        (src / "image.png").touch()
        (src / "readme.txt").touch()
        (src / "data.json").touch()
        (src / "script.py").touch()
        result = await collect_images(str(src))
        assert len(result) == 1
        assert result[0].name == "image.png"

    async def test_accepts_single_file(self, tmp_path: Path) -> None:
        img = tmp_path / "page.png"
        img.touch()
        result = await collect_images(str(img))
        assert len(result) == 1
        assert result[0] == img

    async def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        src = tmp_path / "empty"
        src.mkdir()
        result = await collect_images(str(src))
        assert result == []

    async def test_returns_empty_for_nonexistent(self, tmp_path: Path) -> None:
        result = await collect_images(str(tmp_path / "nonexistent"))
        assert result == []


class TestRunProject:
    async def test_calls_run_stage_once_per_image(self, tmp_path: Path, monkeypatch) -> None:
        """run_project calls dispatcher.run_stage once per image file."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Create two image files
        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").touch()
        (src / "page1.png").touch()

        spec = _make_spec(tmp_path, source_path=str(src))

        # Pre-write the project with queued pages so storage helpers work
        pages = [
            PageResult(page_idx=0, page_name="page0.png", state="queued"),
            PageResult(page_idx=1, page_name="page1.png", state="queued"),
        ]
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=2,
                pages_done=0,
                pages=pages,
            ),
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.run_stage = AsyncMock(
            return_value=_make_stub_stage_result("proj-test-001/0", EMPTY_PAGE_DICT)
        )

        callbacks: list[ProjectStatus] = []

        async def _cb(status: ProjectStatus) -> None:
            callbacks.append(status)

        await run_project(spec, mock_dispatcher, _cb)

        assert mock_dispatcher.run_stage.call_count == 2
        assert len(callbacks) == 2

    async def test_status_callback_receives_project_status(self, tmp_path: Path, monkeypatch) -> None:

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").touch()

        spec = _make_spec(tmp_path, source_path=str(src))
        pages = [PageResult(page_idx=0, page_name="page0.png", state="queued")]
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=pages,
            ),
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.run_stage = AsyncMock(
            return_value=_make_stub_stage_result("proj-test-001/0", SIMPLE_PAGE_DICT)
        )

        received: list[ProjectStatus] = []

        async def _cb(s: ProjectStatus) -> None:
            received.append(s)

        await run_project(spec, mock_dispatcher, _cb)

        assert len(received) == 1
        assert received[0].project_id == spec.project_id
        assert isinstance(received[0], ProjectStatus)

    async def test_run_stage_kwargs(self, tmp_path: Path, monkeypatch) -> None:
        """run_project passes image_path, engine, language to run_stage."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        img = src / "pg.png"
        img.touch()

        spec = _make_spec(tmp_path, source_path=str(src))
        pages = [PageResult(page_idx=0, page_name="pg.png", state="queued")]
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=pages,
            ),
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.run_stage = AsyncMock(
            return_value=_make_stub_stage_result("proj-test-001/0", EMPTY_PAGE_DICT)
        )

        await run_project(spec, mock_dispatcher, AsyncMock())

        call_kwargs = mock_dispatcher.run_stage.call_args
        assert call_kwargs.kwargs.get("image_path") == str(img)
        assert call_kwargs.kwargs.get("engine") == spec.engine
        assert call_kwargs.kwargs.get("language") == spec.language

    async def test_extracts_text_from_page_dict(self, tmp_path: Path, monkeypatch) -> None:
        """run_project extracts text from the page dict and writes it."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").touch()

        spec = _make_spec(tmp_path, source_path=str(src))
        pages = [PageResult(page_idx=0, page_name="page0.png", state="queued")]
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=pages,
            ),
        )

        mock_dispatcher = MagicMock()
        mock_dispatcher.run_stage = AsyncMock(
            return_value=_make_stub_stage_result("proj-test-001/0", SIMPLE_PAGE_DICT)
        )

        await run_project(spec, mock_dispatcher, AsyncMock())

        # Verify txt was written with extracted text
        from pdomain_ocr_simple_gui.storage import get_project_dir

        txt_path = get_project_dir(spec.project_id) / "pages" / "page0.png.txt"
        assert txt_path.exists()
        text = txt_path.read_text()
        assert "Hello" in text
        assert "world" in text

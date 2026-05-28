"""Tests for pipeline.py — collect_images + run_project."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.pipeline import (
    build_sidecar_payload,
    collect_images,
    extract_words,
    run_project,
)


def _make_batch_dispatcher(page_dicts: list[dict[str, Any]]) -> MagicMock:
    """Build a mock dispatcher whose run_ocr_batch returns page_dicts in order.

    Successive calls each return one page dict per image in the chunk.
    The side_effect receives an OcrBatchRequest and returns the next slice.
    """
    dispatcher = MagicMock()
    # Each call to run_ocr_batch returns page_dicts for pages in that chunk.
    # We use a closure that slices out the right portion per call.
    call_count = [0]
    page_queue = list(page_dicts)

    async def _run_ocr_batch(req):  # type: ignore[no-untyped-def]
        n = len(req.images)
        result = page_queue[:n]
        del page_queue[:n]
        call_count[0] += 1
        return result

    dispatcher.run_ocr_batch = _run_ocr_batch
    dispatcher._call_count = call_count
    return dispatcher


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


def _make_single_batch_dispatcher(page_dict: dict[str, Any]) -> MagicMock:
    """Build a mock dispatcher whose run_ocr_batch always returns [page_dict] per image."""
    dispatcher = MagicMock()

    async def _run_ocr_batch(req):  # type: ignore[no-untyped-def]
        return [page_dict] * len(req.images)

    dispatcher.run_ocr_batch = _run_ocr_batch
    return dispatcher


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


def _word_node(text: str, x0: float, y0: float, x1: float, y1: float, conf: float = 0.9) -> dict[str, Any]:
    return {
        "type": "Word",
        "text": text,
        "bounding_box": {
            "top_left": {"x": x0, "y": y0, "is_normalized": True},
            "bottom_right": {"x": x1, "y": y1, "is_normalized": True},
            "is_normalized": True,
        },
        "ocr_confidence": conf,
        "word_labels": [],
        "text_style_labels": [],
        "text_style_label_scopes": [],
        "word_components": [],
        "baseline": None,
        "ground_truth_text": None,
        "ground_truth_bounding_box": None,
        "ground_truth_match_keys": [],
    }


def _bboxed_page_dict() -> dict[str, Any]:
    """Page with two real word boxes — matches what DocTR actually emits."""
    return {
        "type": "Page",
        "width": 200,
        "height": 300,
        "page_index": 0,
        "bounding_box": None,
        "items": [
            {
                "type": "Block",
                "child_type": "WORDS",
                "block_category": None,
                "block_labels": [],
                "block_role_labels": [],
                "block_position_labels": [],
                "line_role_labels": [],
                "line_position_labels": [],
                "baseline": None,
                "bounding_box": None,
                "items": [
                    _word_node("Hello", 0.1, 0.1, 0.3, 0.15, conf=0.95),
                    _word_node("world", 0.35, 0.1, 0.55, 0.15, conf=0.80),
                ],
                "override_page_sort_order": None,
                "unmatched_ground_truth_words": [],
                "additional_block_attributes": {},
                "base_ground_truth_text": "",
            }
        ],
        "ocr_provenance": None,
    }


class TestExtractWords:
    def test_flattens_word_tree(self) -> None:
        page = _bboxed_page_dict()
        words = extract_words(page)
        assert [w["text"] for w in words] == ["Hello", "world"]

    def test_bbox_is_xywh_normalized(self) -> None:
        import pytest

        page = _bboxed_page_dict()
        words = extract_words(page)
        bbox = words[0]["bbox"]
        assert isinstance(bbox, dict)
        assert bbox["x"] == pytest.approx(0.1)
        assert bbox["y"] == pytest.approx(0.1)
        assert bbox["w"] == pytest.approx(0.2)
        assert bbox["h"] == pytest.approx(0.05)

    def test_skips_words_without_geometry(self) -> None:
        page = _bboxed_page_dict()
        # Strip bounding_box from the second word
        page["items"][0]["items"][1]["bounding_box"] = None
        words = extract_words(page)
        assert [w["text"] for w in words] == ["Hello"]

    def test_empty_for_page_with_no_words(self) -> None:
        page = {"type": "Page", "items": []}
        assert extract_words(page) == []


class TestBuildSidecarPayload:
    def test_adds_text_width_height_words(self) -> None:
        page = _bboxed_page_dict()
        payload = build_sidecar_payload(page, "Hello world")
        assert payload["text"] == "Hello world"
        assert payload["width"] == 200
        assert payload["height"] == 300
        words = payload["words"]
        assert isinstance(words, list)
        assert len(words) == 2
        # Each entry has the canonical shape consumed by /api/pages/.../words
        first = words[0]
        assert isinstance(first, dict)
        assert set(first.keys()) == {"text", "bbox", "confidence"}
        bbox = first["bbox"]
        assert isinstance(bbox, dict)
        assert set(bbox.keys()) == {"x", "y", "w", "h"}

    def test_preserves_original_tree(self) -> None:
        page = _bboxed_page_dict()
        payload = build_sidecar_payload(page, "Hi")
        # original recursive tree is still present
        assert payload["type"] == "Page"
        assert isinstance(payload["items"], list)


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

    async def test_accepts_jpeg2000_family(self, tmp_path: Path) -> None:
        """JPEG 2000 extensions (.jp2, .j2k, .jpf, .jpx, .jpm) must be picked up."""
        from pdomain_ocr_simple_gui.pipeline import _IMAGE_SUFFIXES

        assert {".jp2", ".j2k", ".jpf", ".jpx", ".jpm"}.issubset(_IMAGE_SUFFIXES)

        src = tmp_path / "imgs"
        src.mkdir()
        (src / "a.jp2").touch()
        (src / "b.j2k").touch()
        (src / "c.jpf").touch()
        (src / "d.jpx").touch()
        (src / "e.jpm").touch()
        (src / "skip.txt").touch()
        result = await collect_images(str(src))
        names = sorted(p.name for p in result)
        assert names == ["a.jp2", "b.j2k", "c.jpf", "d.jpx", "e.jpm"]


class TestRunProject:
    async def test_calls_run_ocr_batch_for_images(self, tmp_path: Path, monkeypatch) -> None:
        """run_project calls dispatcher.run_ocr_batch for all image files."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        # Create two image files with real content so bytes reads work
        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png-0")
        (src / "page1.png").write_bytes(b"fake-png-1")

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

        batch_calls: list[object] = []

        mock_dispatcher = MagicMock()

        async def _run_ocr_batch(req):  # type: ignore[no-untyped-def]
            batch_calls.append(req)
            return [EMPTY_PAGE_DICT] * len(req.images)

        mock_dispatcher.run_ocr_batch = _run_ocr_batch

        callbacks: list[ProjectStatus] = []

        async def _cb(status: ProjectStatus) -> None:
            callbacks.append(status)

        await run_project(spec, mock_dispatcher, _cb)

        # All 2 pages processed across 1 or more batch calls
        total_pages_batched = sum(len(r.images) for r in batch_calls)  # type: ignore[union-attr]
        assert total_pages_batched == 2
        # 1 warm-up callback + 1 completion callback per chunk.
        # combined_txt=False so the "Writing outputs" callback is skipped.
        assert len(callbacks) >= 2

    async def test_status_callback_receives_project_status(self, tmp_path: Path, monkeypatch) -> None:

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png")

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

        mock_dispatcher = _make_single_batch_dispatcher(SIMPLE_PAGE_DICT)

        received: list[ProjectStatus] = []

        async def _cb(s: ProjectStatus) -> None:
            received.append(s)

        await run_project(spec, mock_dispatcher, _cb)

        # 1 warm-up + 1 completion callback for the single page.
        assert len(received) >= 2
        assert received[0].project_id == spec.project_id
        assert isinstance(received[0], ProjectStatus)

    async def test_run_ocr_batch_request_fields(self, tmp_path: Path, monkeypatch) -> None:
        """run_project passes correct engine, language, and image bytes to run_ocr_batch."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        img = src / "pg.png"
        img.write_bytes(b"fake-image-bytes")

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

        captured_reqs: list[object] = []
        mock_dispatcher = MagicMock()

        async def _run_ocr_batch(req):  # type: ignore[no-untyped-def]
            captured_reqs.append(req)
            return [EMPTY_PAGE_DICT] * len(req.images)

        mock_dispatcher.run_ocr_batch = _run_ocr_batch

        await run_project(spec, mock_dispatcher, AsyncMock())

        assert len(captured_reqs) == 1
        req = captured_reqs[0]
        assert req.engine == spec.engine  # type: ignore[union-attr]
        assert req.language == spec.language  # type: ignore[union-attr]
        assert req.images == [b"fake-image-bytes"]  # type: ignore[union-attr]

    async def test_extracts_text_from_page_dict(self, tmp_path: Path, monkeypatch) -> None:
        """run_project extracts text from the page dict and writes it."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png")

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

        mock_dispatcher = _make_single_batch_dispatcher(SIMPLE_PAGE_DICT)

        await run_project(spec, mock_dispatcher, AsyncMock())

        # Verify txt was written with extracted text
        from pdomain_ocr_simple_gui.storage import get_project_dir

        txt_path = get_project_dir(spec.project_id) / "pages" / "page0.png.txt"
        assert txt_path.exists()
        text = txt_path.read_text()
        assert "Hello" in text
        assert "world" in text

    async def test_sidecar_carries_text_dims_and_words(self, tmp_path: Path, monkeypatch) -> None:
        """The sidecar JSON pipeline writes must expose normalized top-level keys."""
        import json as _json

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "p0.png").write_bytes(b"fake-png")

        spec = _make_spec(tmp_path, source_path=str(src))
        pages = [PageResult(page_idx=0, page_name="p0.png", state="queued")]
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

        page_dict = _bboxed_page_dict()
        mock_dispatcher = _make_single_batch_dispatcher(page_dict)

        await run_project(spec, mock_dispatcher, AsyncMock())

        from pdomain_ocr_simple_gui.storage import get_project_dir

        sidecar_path = get_project_dir(spec.project_id) / "pages" / "p0.png.json"
        assert sidecar_path.exists()
        data = _json.loads(sidecar_path.read_text())
        assert isinstance(data["text"], str)
        assert "Hello" in data["text"]
        assert data["width"] == 200
        assert data["height"] == 300
        assert isinstance(data["words"], list)
        assert len(data["words"]) == 2
        w0 = data["words"][0]
        assert w0["text"] == "Hello"
        assert set(w0["bbox"].keys()) == {"x", "y", "w", "h"}
        assert isinstance(w0["confidence"], float)

    async def test_writes_outputs_into_output_dir(self, tmp_path: Path, monkeypatch) -> None:
        """When save_json + combined_txt are set, output_dir gets json + txt + combined.txt."""
        from datetime import UTC, datetime

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "p0.png").write_bytes(b"fake-png")

        out_dir = tmp_path / "user-outputs"
        spec = ProjectSpec(
            project_id="proj-out-001",
            name="My Run",
            source_path=str(src),
            output_dir=str(out_dir),
            engine="doctr",
            language="en",
            save_json=True,
            combined_txt=True,
            created_at=datetime.now(UTC),
            last_opened_at=datetime.now(UTC),
        )
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="p0.png", state="queued")],
            ),
        )

        mock_dispatcher = _make_single_batch_dispatcher(_bboxed_page_dict())

        await run_project(spec, mock_dispatcher, AsyncMock())

        assert (out_dir / "p0.txt").exists(), list(out_dir.iterdir())
        assert "Hello" in (out_dir / "p0.txt").read_text()
        assert (out_dir / "p0.json").exists()  # save_json=True
        # Combined uses sanitised spec.name
        assert (out_dir / "My_Run.txt").exists()

    async def test_save_json_false_skips_json_in_output_dir(self, tmp_path: Path, monkeypatch) -> None:
        """save_json=False → no .json file mirrored to output_dir (txt still written)."""
        from datetime import UTC, datetime

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        src = tmp_path / "source"
        src.mkdir()
        (src / "p0.png").write_bytes(b"fake-png")
        out_dir = tmp_path / "out2"
        spec = ProjectSpec(
            project_id="proj-out-002",
            name="run",
            source_path=str(src),
            output_dir=str(out_dir),
            engine="doctr",
            language="en",
            save_json=False,
            combined_txt=False,
            created_at=datetime.now(UTC),
            last_opened_at=datetime.now(UTC),
        )
        from pdomain_ocr_simple_gui.storage import write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="p0.png", state="queued")],
            ),
        )
        mock_dispatcher = _make_single_batch_dispatcher(_bboxed_page_dict())
        await run_project(spec, mock_dispatcher, AsyncMock())
        assert (out_dir / "p0.txt").exists()
        assert not (out_dir / "p0.json").exists()
        # combined_txt=False → no combined file
        assert not any(p.suffix == ".txt" and p.name != "p0.txt" for p in out_dir.iterdir())


class TestProgressMessage:
    async def test_progress_message_sequence(self, tmp_path: Path, monkeypatch) -> None:
        """run_project emits the documented per-phase progress messages.

        Chunked flow on a 2-page job with batch_pages=1 and combined_txt=False:
          1. "Loading OCR engine..." (once, before any batch dispatch).
          2. "Processed 1/2 pages" (after chunk 1 completes).
          3. "Processed 2/2 pages" (after chunk 2 completes).
          Terminal callback is NOT emitted via status_callback, but the
          persisted ProjectStatus clears progress_message to None.
        """
        from datetime import UTC, datetime

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "name0.png").write_bytes(b"fake-png-0")
        (src / "name1.png").write_bytes(b"fake-png-1")

        # Use batch_pages=1 so we get two separate chunks → deterministic message order
        spec = ProjectSpec(
            project_id="proj-test-001",
            name="Test Project",
            source_path=str(src),
            output_dir=str(tmp_path / "output"),
            engine="doctr",
            language="en",
            save_json=False,
            combined_txt=False,
            batch_pages=1,
            created_at=datetime.now(UTC),
            last_opened_at=datetime.now(UTC),
        )
        pages = [
            PageResult(page_idx=0, page_name="name0.png", state="queued"),
            PageResult(page_idx=1, page_name="name1.png", state="queued"),
        ]
        from pdomain_ocr_simple_gui.storage import read_project, write_project

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

        mock_dispatcher = _make_single_batch_dispatcher(EMPTY_PAGE_DICT)

        messages: list[str | None] = []

        async def _cb(status: ProjectStatus) -> None:
            messages.append(status.progress_message)

        await run_project(spec, mock_dispatcher, _cb)

        loading_msg = "Loading OCR engine — first run may download ~200 MB to ~/.cache/huggingface"
        assert messages == [
            loading_msg,
            "Processed 1/2 pages",
            "Processed 2/2 pages",
        ]

        # Terminal persisted status clears the message.
        _, final_status = read_project(spec.project_id)
        assert final_status.progress_message is None
        assert final_status.state == "succeeded"


class TestChunkFailureIsolation:
    async def test_second_chunk_failure_does_not_abort_first(self, tmp_path: Path, monkeypatch) -> None:
        """Chunk failure isolation: a non-OOM RuntimeError on chunk 2 must not abort chunk 1.

        Setup:
          - 4 pages, batch_pages=2  → 2 chunks of 2 pages each
          - chunk 1 succeeds (pages 0, 1)
          - chunk 2 raises RuntimeError (pages 2, 3)

        Expected:
          - pages 0+1 have state="succeeded" with sidecar+txt written
          - pages 2+3 have state="failed" with error set
          - job terminal state = "failed" (not aborted/cancelled)
          - per-chunk progress callbacks fired (at least 3: warm-up + 2 chunk completions)
        """
        from datetime import UTC, datetime

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        for i in range(4):
            (src / f"pg{i}.png").write_bytes(f"fake-png-{i}".encode())

        spec = ProjectSpec(
            project_id="proj-chunk-isolation",
            name="Chunk Test",
            source_path=str(src),
            output_dir=str(tmp_path / "output"),
            engine="doctr",
            language="en",
            save_json=False,
            combined_txt=False,
            batch_pages=2,
            created_at=datetime.now(UTC),
            last_opened_at=datetime.now(UTC),
        )
        pages = [PageResult(page_idx=i, page_name=f"pg{i}.png", state="queued") for i in range(4)]
        from pdomain_ocr_simple_gui.storage import get_project_dir, read_project, write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=4,
                pages_done=0,
                pages=pages,
            ),
        )

        chunk_call = [0]

        async def _run_ocr_batch_partial_fail(req):  # type: ignore[no-untyped-def]
            chunk_call[0] += 1
            if chunk_call[0] == 1:
                return [EMPTY_PAGE_DICT] * len(req.images)
            raise RuntimeError("simulated chunk-2 failure")

        mock_dispatcher = MagicMock()
        mock_dispatcher.run_ocr_batch = _run_ocr_batch_partial_fail

        callbacks: list[ProjectStatus] = []

        async def _cb(status: ProjectStatus) -> None:
            callbacks.append(status)

        await run_project(spec, mock_dispatcher, _cb)

        _, final_status = read_project(spec.project_id)

        # Job ends in "failed" (not aborted)
        assert final_status.state == "failed"

        # Pages 0+1 succeeded
        assert final_status.pages[0].state == "succeeded"
        assert final_status.pages[1].state == "succeeded"

        # Pages 2+3 failed with error set
        assert final_status.pages[2].state == "failed"
        assert final_status.pages[3].state == "failed"
        assert "simulated chunk-2 failure" in (final_status.pages[2].error or "")
        assert "simulated chunk-2 failure" in (final_status.pages[3].error or "")

        # Sidecar + txt written for pages 0+1
        pages_dir = get_project_dir(spec.project_id) / "pages"
        assert (pages_dir / "pg0.png.txt").exists()
        assert (pages_dir / "pg1.png.txt").exists()

        # No sidecar/txt for pages 2+3 (they failed before post-processing)
        assert not (pages_dir / "pg2.png.txt").exists()
        assert not (pages_dir / "pg3.png.txt").exists()

        # Per-chunk progress callbacks: warm-up + at least 2 chunk completions
        assert len(callbacks) >= 3

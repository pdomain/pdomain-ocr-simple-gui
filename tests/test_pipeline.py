"""Tests for pipeline.py — collect_images + run_project."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

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


def _word_node(*, text: str, x0: float, y0: float, x1: float, y1: float, conf: float = 0.9) -> dict[str, Any]:
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
                    _word_node(text="Hello", x0=0.1, y0=0.1, x1=0.3, y1=0.15, conf=0.95),
                    _word_node(text="world", x0=0.35, y0=0.1, x1=0.55, y1=0.15, conf=0.80),
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

    def test_word_with_missing_bounding_box_keys_is_skipped(self) -> None:
        """A word whose bounding_box lacks required keys is skipped (no crash)."""
        page = _bboxed_page_dict()
        # Replace bounding_box with a dict missing 'bottom_right'
        page["items"][0]["items"][0]["bounding_box"] = {
            "top_left": {"x": 0.1, "y": 0.1, "is_normalized": True}
        }
        words = extract_words(page)
        # The malformed word is excluded; the other valid word remains
        texts = [w["text"] for w in words]
        assert "Hello" not in texts  # malformed word skipped

    def test_skips_words_without_geometry(self) -> None:
        page = _bboxed_page_dict()
        # Strip bounding_box from the second word
        page["items"][0]["items"][1]["bounding_box"] = None
        words = extract_words(page)
        assert [w["text"] for w in words] == ["Hello"]

    def test_empty_for_page_with_no_words(self) -> None:
        page: dict[str, Any] = {"type": "Page", "items": []}
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

    def test_zero_words_payload_has_empty_words_list(self) -> None:
        """A page with no words produces a payload with an empty words list."""
        payload = build_sidecar_payload(EMPTY_PAGE_DICT, "")
        assert payload["words"] == []
        assert payload["text"] == ""

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
    async def test_project_state_transitions_use_lifecycle_adapter(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """run_project validates queued->running->terminal via lifecycle adapter."""
        import pdomain_ocr_simple_gui.pipeline as pipeline_mod
        from pdomain_ocr_simple_gui.storage import read_project, write_project

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png")

        spec = _make_spec(tmp_path, source_path=str(src))
        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="page0.png", state="queued")],
            ),
        )

        transitions: list[tuple[str, str]] = []

        def _fake_assert_job_transition(current: str, event: str) -> str:
            transitions.append((current, event))
            if (current, event) == ("queued", "start"):
                return "running"
            if (current, event) == ("running", "succeed"):
                return "succeeded"
            raise AssertionError(f"unexpected lifecycle transition: {(current, event)!r}")

        monkeypatch.setattr(
            pipeline_mod,
            "assert_job_transition",
            _fake_assert_job_transition,
            raising=False,
        )

        await run_project(spec, _make_single_batch_dispatcher(EMPTY_PAGE_DICT), AsyncMock())

        _, final_status = read_project(spec.project_id)
        assert final_status.state == "succeeded"
        assert transitions == [("queued", "start"), ("running", "succeed")]

    async def test_page_updates_do_not_persist_terminal_project_state_before_final_transition(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Per-page completion must not terminalize the project before final lifecycle validation."""
        import pdomain_ocr_simple_gui.pipeline as pipeline_mod
        import pdomain_ocr_simple_gui.storage as storage_mod
        from pdomain_ocr_simple_gui.storage import read_project, write_project

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png")

        spec = _make_spec(tmp_path, source_path=str(src))
        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="page0.png", state="queued")],
            ),
        )

        terminal_transition_validated = False
        terminal_states = {"succeeded", "failed", "cancelled"}
        original_write_project = storage_mod.write_project

        def _guarded_write_project(spec: ProjectSpec, status: ProjectStatus) -> None:
            if not terminal_transition_validated and status.state in terminal_states:
                raise AssertionError(
                    f"terminal project state {status.state!r} written before lifecycle validation",
                )
            original_write_project(spec, status)

        def _fake_assert_job_transition(current: str, event: str) -> str:
            nonlocal terminal_transition_validated
            if event == "start":
                assert current == "queued"
                return "running"
            if event == "succeed":
                _, persisted = read_project(spec.project_id)
                assert persisted.state == "running"
                assert current == persisted.state
                terminal_transition_validated = True
                return "succeeded"
            raise AssertionError(f"unexpected lifecycle transition: {(current, event)!r}")

        monkeypatch.setattr(storage_mod, "write_project", _guarded_write_project)
        monkeypatch.setattr(
            pipeline_mod,
            "assert_job_transition",
            _fake_assert_job_transition,
            raising=False,
        )

        await run_project(spec, _make_single_batch_dispatcher(EMPTY_PAGE_DICT), AsyncMock())

        _, final_status = read_project(spec.project_id)
        assert final_status.state == "succeeded"

    async def test_combined_output_failure_does_not_persist_success_terminal_state(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Combined output failures must happen before terminal success is persisted."""
        import pytest

        import pdomain_ocr_simple_gui.storage as storage_mod

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png")

        spec = _make_spec(tmp_path, source_path=str(src))
        storage_mod.write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="page0.png", state="queued")],
            ),
        )

        def _raise_combined_write(spec: ProjectSpec, status: ProjectStatus) -> None:
            raise RuntimeError("combined write failed")

        monkeypatch.setattr(storage_mod, "write_combined_txt", _raise_combined_write)

        with pytest.raises(RuntimeError, match="combined write failed"):
            await run_project(spec, _make_single_batch_dispatcher(EMPTY_PAGE_DICT), AsyncMock())

        _, persisted = storage_mod.read_project(spec.project_id)
        assert persisted.state == "running"

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
        total_pages_batched = sum(len(cast("Any", r).images) for r in batch_calls)
        assert total_pages_batched == 2
        # 1 warm-up callback + 1 completion callback per chunk + 1 "Writing
        # outputs" callback (combined.txt is now always written).
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

    @pytest.mark.parametrize(
        ("device_choice", "expected_req_device"),
        [
            ("auto", None),
            ("cpu", "cpu"),
        ],
    )
    async def test_run_ocr_batch_request_fields(
        self,
        tmp_path: Path,
        monkeypatch,
        device_choice: str,
        expected_req_device: str | None,
    ) -> None:
        """run_project passes correct engine, language, image bytes, and device to run_ocr_batch."""

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        img = src / "pg.png"
        img.write_bytes(b"fake-image-bytes")

        spec = _make_spec(tmp_path, source_path=str(src)).model_copy(update={"device": device_choice})
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
        req = cast("Any", captured_reqs[0])
        assert req.engine == spec.engine
        assert req.language == spec.language
        assert req.images == [b"fake-image-bytes"]
        assert req.device == expected_req_device

    async def test_run_project_times_out_hung_dispatcher(self, tmp_path: Path, monkeypatch) -> None:
        """A dispatcher that never returns is bounded by PDOMAIN_OCR_BATCH_TIMEOUT_S.

        The wall-clock assertion (not just the terminal state) is the point:
        without the timeout wired in, the chunk would still end up "failed"
        eventually (indexing the never-returned batch result raises), but
        only after the full 30s sleep — the job would sit "running" for
        30s instead of failing in ~0.05s.
        """
        import asyncio
        import time

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
        monkeypatch.setenv("PDOMAIN_OCR_BATCH_TIMEOUT_S", "0.05")

        src = tmp_path / "source"
        src.mkdir()
        (src / "page0.png").write_bytes(b"fake-png")

        spec = _make_spec(tmp_path, source_path=str(src))
        from pdomain_ocr_simple_gui.storage import read_project, write_project

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="page0.png", state="queued")],
            ),
        )

        class HungDispatcher:
            async def run_ocr_batch(self, req: object) -> list[dict[str, object]]:
                await asyncio.sleep(30)
                return []

        start = time.monotonic()
        await run_project(spec, HungDispatcher(), AsyncMock())
        elapsed = time.monotonic() - start

        _, status = read_project(spec.project_id)
        assert status.state == "failed"
        assert all(p.state == "failed" for p in status.pages)
        assert elapsed < 5.0, f"run_project took {elapsed:.1f}s — dispatcher wait was not bounded"

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
        """output_dir always gets per-page json + txt + combined.txt (no knobs).

        B-HOME-011 cleanup: the save_json / combined_txt knobs are gone — the
        output mirror always includes the per-page sidecar .json AND the
        combined .txt, because the bbox display needs both.
        """
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
        # Sidecar .json is ALWAYS mirrored now (no save_json knob).
        assert (out_dir / "p0.json").exists()
        # Combined .txt is ALWAYS written, using the sanitised spec.name.
        assert (out_dir / "My_Run.txt").exists()

    async def test_sidecar_and_combined_always_written(self, tmp_path: Path, monkeypatch) -> None:
        """No knob can suppress the canonical sidecar or combined.txt.

        B-HOME-011 cleanup: the canonical per-page sidecar (pages/<name>.json)
        and the canonical combined.txt are written unconditionally — the bbox
        overlay + combined download depend on them.
        """
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
            created_at=datetime.now(UTC),
            last_opened_at=datetime.now(UTC),
        )
        from pdomain_ocr_simple_gui.storage import get_project_dir, write_project

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

        proj_dir = get_project_dir(spec.project_id)
        # Canonical sidecar + combined always present.
        assert (proj_dir / "pages" / "p0.png.json").exists()
        assert (proj_dir / "combined.txt").exists()
        # Output mirror always gets the per-page .json + combined .txt.
        assert (out_dir / "p0.txt").exists()
        assert (out_dir / "p0.json").exists()
        assert (out_dir / "run.txt").exists()

    async def test_create_job_request_has_no_save_json_knob(self) -> None:
        """B-HOME-011 cleanup: CreateJobRequest no longer exposes save_json."""
        from pdomain_ocr_simple_gui.routes.jobs import CreateJobRequest

        assert "save_json" not in CreateJobRequest.model_fields
        # A POST body that still sends save_json=false must NOT disable sidecars
        # — the field is simply ignored (extra fields ignored by default).
        req = CreateJobRequest.model_validate({"source_path": "/x", "save_json": False})
        assert not hasattr(req, "save_json") or "save_json" not in req.model_dump()


class TestProgressMessage:
    async def test_progress_message_sequence(self, tmp_path: Path, monkeypatch) -> None:
        """run_project emits the documented per-phase progress messages.

        Chunked flow on a 2-page job with batch_pages=1:
          1. "Loading OCR engine..." (once, before any batch dispatch).
          2. "Processed 1/2 pages" (after chunk 1 completes).
          3. "Processed 2/2 pages" (after chunk 2 completes).
          4. "Writing outputs" (combined.txt is always written now).
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
            "Writing outputs",
        ]

        # Terminal persisted status clears the message.
        _, final_status = read_project(spec.project_id)
        assert final_status.progress_message is None
        assert final_status.state == "succeeded"

    async def test_dispatcher_failure_leaves_job_in_failed_state(self, tmp_path: Path, monkeypatch) -> None:
        """A dispatcher that raises on every page leaves the job in failed state."""
        from datetime import UTC, datetime

        from pdomain_ocr_simple_gui.storage import read_project, write_project

        root = tmp_path / "projects"
        root.mkdir()
        monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

        src = tmp_path / "source"
        src.mkdir()
        (src / "pg.png").write_bytes(b"fake-png")

        spec = ProjectSpec(
            project_id="proj-fail-001",
            name="Fail Test",
            source_path=str(src),
            output_dir=str(tmp_path / "output"),
            engine="doctr",
            language="en",
            created_at=datetime.now(UTC),
            last_opened_at=datetime.now(UTC),
        )

        write_project(
            spec,
            ProjectStatus(
                project_id=spec.project_id,
                state="queued",
                page_count=1,
                pages_done=0,
                pages=[PageResult(page_idx=0, page_name="pg.png", state="queued")],
            ),
        )

        fail_dispatcher = MagicMock()

        async def _always_fail(req):  # type: ignore[no-untyped-def]
            raise RuntimeError("dispatcher exploded")

        fail_dispatcher.run_ocr_batch = _always_fail

        await run_project(spec, fail_dispatcher, AsyncMock())

        _, final_status = read_project(spec.project_id)
        assert final_status.state == "failed"
        assert final_status.pages[0].state == "failed"
        assert "dispatcher exploded" in (final_status.pages[0].error or "")


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


# ──────────────────────────────────────────────────────────────────────────────
# Task B2 — fake dispatcher page dict must not contain stale 0.17 removed fields
# ──────────────────────────────────────────────────────────────────────────────

STALE_FIELDS = {"ocr_provenance", "source", "ocr_failed", "rotation_applied", "image_path"}


class TestFakeDispatcherPageDictShape:
    """Verify that FakeStageDispatcher's page dict matches the real 0.17 Page surface.

    The fake dict is round-tripped through ``Page.from_dict().to_dict()`` to
    assert that none of the pre-0.17 operational fields survive.  Before the
    fix the fake emits them; after the fix it does not.
    """

    def test_page_dict_roundtrip_has_no_stale_fields(self) -> None:
        """Page.from_dict(fake_dict).to_dict() must not contain any stale field."""
        from pdomain_book_tools.ocr.page import Page

        from pdomain_ocr_simple_gui.testing.fake_dispatcher import _page_dict_for

        raw = _page_dict_for("hello world", page_index=0)
        # Verify round-trip does not carry the stale keys through
        roundtripped = Page.from_dict(raw).to_dict()
        for field in STALE_FIELDS:
            assert field not in roundtripped, (
                f"Stale field {field!r} survived Page.from_dict().to_dict() round-trip. "
                "Remove it from _page_dict_for."
            )

    def test_fake_dict_itself_has_no_stale_fields(self) -> None:
        """The dict emitted by _page_dict_for must not contain any stale field.

        This is the stricter check: the fake should mirror what the real 0.17
        dispatcher emits, not just survive a round-trip.
        """
        from pdomain_ocr_simple_gui.testing.fake_dispatcher import _page_dict_for

        raw = _page_dict_for("hello world", page_index=0)
        for field in STALE_FIELDS:
            assert field not in raw, (
                f"Stale field {field!r} is present in _page_dict_for output. "
                "Remove it from the returned dict."
            )

    def test_fake_dict_has_page_id(self) -> None:
        """The dict must carry a valid UUID string page_id (required for 0.17 Page)."""
        from pdomain_ocr_simple_gui.testing.fake_dispatcher import _page_dict_for

        raw = _page_dict_for("hello", page_index=0)
        # page_id may be absent (Page.from_dict mints one) but if present it must be a str
        if "page_id" in raw:
            assert isinstance(raw["page_id"], str), "page_id must be a UUID string"

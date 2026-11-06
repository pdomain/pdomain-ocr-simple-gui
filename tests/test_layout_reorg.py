"""Layout detection feeds reorganize_page and uses the upright OCR frame."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from pdomain_book_contracts.layout.types import PageLayout
from pdomain_ops.gpu.types import OcrBatchRequest

from pdomain_ocr_simple_gui.layout_pass import load_layout_detector
from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.pipeline import run_project
from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher


class _BatchReq:
    """Duck-typed batch request. FakeStageDispatcher only reads ``images``."""

    def __init__(self, count: int) -> None:
        self.images = [b"x"] * count


class _OnePageDispatcher:
    def __init__(self, page: dict[str, object]) -> None:
        self._page = page

    async def run_ocr_batch(self, req: OcrBatchRequest) -> list[dict[str, object]]:
        _ = req
        return [self._page]


def _spec(tmp_path: Path, source: Path) -> ProjectSpec:
    return ProjectSpec(
        project_id="proj-layout-001",
        name="Layout",
        source_path=str(source),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 11, 6, tzinfo=UTC),
        last_opened_at=datetime(2026, 11, 6, tzinfo=UTC),
    )


def _seed(spec: ProjectSpec, page_name: str) -> None:
    from pdomain_ocr_simple_gui.storage import write_project

    write_project(
        spec,
        ProjectStatus(
            project_id=spec.project_id,
            state="queued",
            page_count=1,
            pages_done=0,
            pages=[PageResult(page_idx=0, page_name=page_name, state="queued")],
        ),
    )


def _write_png(path: Path, image: np.ndarray) -> None:
    import cv2

    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


async def _page_dict(text: str = "Hello") -> dict[str, object]:
    pages = await FakeStageDispatcher(text).run_ocr_batch(cast("object", _BatchReq(1)))
    return pages[0]


def _top_word(page: dict[str, object]) -> None:
    """Point the page's word box at the top strip of the upright frame."""
    items = page["items"]
    assert isinstance(items, list)
    block = items[0]
    assert isinstance(block, dict)
    paragraph = block["items"]
    assert isinstance(paragraph, list)
    para = paragraph[0]
    assert isinstance(para, dict)
    lines = para["items"]
    assert isinstance(lines, list)
    line = lines[0]
    assert isinstance(line, dict)
    words = line["items"]
    assert isinstance(words, list)
    word = words[0]
    assert isinstance(word, dict)
    word["bounding_box"] = {
        "top_left": {"x": 0.0, "y": 0.0, "is_normalized": True},
        "bottom_right": {"x": 1.0, "y": 0.4, "is_normalized": True},
        "is_normalized": True,
    }


class _RecordingDetector:
    def __init__(self, layout: PageLayout) -> None:
        self.layout = layout
        self.sources: list[object] = []

    def detect(self, source: object) -> PageLayout:
        self.sources.append(source)
        return self.layout


@pytest.fixture
def _projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    return root


@pytest.mark.usefixtures("_projects_root")
async def test_run_project_passes_layout_and_saves_reorganized_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reorganize_page receives the detector's layout, and the .txt is that text."""
    from pdomain_book_tools.ocr.page import Page

    from pdomain_ocr_simple_gui import layout_pass
    from pdomain_ocr_simple_gui.storage import get_project_dir

    source = tmp_path / "source"
    source.mkdir()
    image = np.full((40, 80, 3), 255, dtype=np.uint8)
    _write_png(source / "page.png", image)

    page = await _page_dict("Hello")
    page["width"] = 80
    page["height"] = 40
    sentinel = PageLayout(regions=[], image_width=80, image_height=40, detector="sentinel")
    recorder = _RecordingDetector(sentinel)

    def _load(device: str) -> _RecordingDetector:
        assert device
        return recorder

    monkeypatch.setattr(layout_pass, "load_layout_detector", _load)

    calls: list[dict[str, object]] = []

    def _reorganize(
        self: Page,
        layout: object = None,
        *,
        drop_layout_words: bool = False,
        emit_illustration_placeholders: bool = True,
        **_kwargs: object,
    ) -> None:
        calls.append(
            {
                "layout": layout,
                "drop_layout_words": drop_layout_words,
            }
        )
        words = list(self.words)
        assert words
        words[0].text = "LAYOUT-REORGANIZED"

    monkeypatch.setattr(Page, "reorganize_page", _reorganize)

    spec = _spec(tmp_path, source)
    _seed(spec, "page.png")
    await run_project(spec, _OnePageDispatcher(page), _status)

    assert calls
    assert calls[0]["layout"] is sentinel
    assert calls[0]["drop_layout_words"] is False
    saved = (get_project_dir(spec.project_id) / "pages" / "page.png.txt").read_text()
    assert "LAYOUT-REORGANIZED" in saved
    assert "Hello" not in saved


@pytest.mark.usefixtures("_projects_root")
async def test_rotated_90_page_detects_layout_on_the_upright_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sideways file whose OCR frame is portrait is detected upright, ink at the top."""
    from pdomain_ocr_simple_gui import layout_pass

    source = tmp_path / "source"
    source.mkdir()
    sideways = np.full((40, 80, 3), 255, dtype=np.uint8)
    sideways[:, :40] = 0
    _write_png(source / "page.png", sideways)

    page = await _page_dict()
    page["width"] = 40
    page["height"] = 80
    _top_word(page)
    sentinel = PageLayout(regions=[], image_width=40, image_height=80, detector="sentinel")
    recorder = _RecordingDetector(sentinel)
    monkeypatch.setattr(layout_pass, "load_layout_detector", lambda _device: recorder)

    spec = _spec(tmp_path, source)
    _seed(spec, "page.png")
    await run_project(spec, _OnePageDispatcher(page), _status)

    assert recorder.sources
    seen = recorder.sources[0]
    assert isinstance(seen, np.ndarray)
    assert seen.shape[:2] == (80, 40)
    assert float(seen[:32].mean()) < 10
    assert float(seen[48:].mean()) > 200


@pytest.mark.usefixtures("_projects_root")
async def test_rotated_180_page_detects_layout_on_the_upright_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same width and height as the file, but the ink only matches after a half turn."""
    from pdomain_ocr_simple_gui import layout_pass

    source = tmp_path / "source"
    source.mkdir()
    upside_down = np.full((40, 80, 3), 255, dtype=np.uint8)
    upside_down[20:] = 0
    _write_png(source / "page.png", upside_down)

    page = await _page_dict()
    page["width"] = 80
    page["height"] = 40
    _top_word(page)
    sentinel = PageLayout(regions=[], image_width=80, image_height=40, detector="sentinel")
    recorder = _RecordingDetector(sentinel)
    monkeypatch.setattr(layout_pass, "load_layout_detector", lambda _device: recorder)

    spec = _spec(tmp_path, source)
    _seed(spec, "page.png")
    await run_project(spec, _OnePageDispatcher(page), _status)

    assert recorder.sources
    seen = recorder.sources[0]
    assert isinstance(seen, np.ndarray)
    assert seen.shape[:2] == (40, 80)
    assert float(seen[:16].mean()) < 10
    assert float(seen[24:].mean()) > 200


def _two_words(page: dict[str, object], boxes: list[tuple[float, float, float, float]]) -> None:
    """Replace the page's words with one Word dict per normalized box."""
    items = page["items"]
    assert isinstance(items, list)
    block = items[0]
    assert isinstance(block, dict)
    paragraph = block["items"]
    assert isinstance(paragraph, list)
    para = paragraph[0]
    assert isinstance(para, dict)
    lines = para["items"]
    assert isinstance(lines, list)
    line = lines[0]
    assert isinstance(line, dict)
    words = line["items"]
    assert isinstance(words, list)
    template = words[0]
    assert isinstance(template, dict)
    built: list[dict[str, object]] = []
    for x, y, box_w, box_h in boxes:
        word = dict(template)
        word["bounding_box"] = {
            "top_left": {"x": x, "y": y, "is_normalized": True},
            "bottom_right": {"x": x + box_w, "y": y + box_h, "is_normalized": True},
            "is_normalized": True,
        }
        built.append(word)
    line["items"] = built


@pytest.mark.usefixtures("_projects_root")
async def test_small_dark_box_does_not_outvote_the_large_text_box(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Area-weighted ink keeps the upright frame when a tiny box is bright."""
    from pdomain_ocr_simple_gui import layout_pass

    source = tmp_path / "source"
    source.mkdir()
    upright = np.full((40, 80, 3), 255, dtype=np.uint8)
    upright[:32] = 0
    _write_png(source / "page.png", upright)

    page = await _page_dict()
    page["width"] = 80
    page["height"] = 40
    _two_words(
        page,
        [
            (0.0, 0.0, 1.0, 0.8),
            (0.0, 0.9, 1.0, 0.1),
        ],
    )
    sentinel = PageLayout(regions=[], image_width=80, image_height=40, detector="sentinel")
    recorder = _RecordingDetector(sentinel)
    monkeypatch.setattr(layout_pass, "load_layout_detector", lambda _device: recorder)

    spec = _spec(tmp_path, source)
    _seed(spec, "page.png")
    await run_project(spec, _OnePageDispatcher(page), _status)

    assert recorder.sources
    seen = recorder.sources[0]
    assert isinstance(seen, np.ndarray)
    assert seen.shape[:2] == (40, 80)
    assert float(seen[:16].mean()) < 10


@pytest.mark.usefixtures("_projects_root")
async def test_layout_detect_runs_off_the_event_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model load and detect must not block the job's event-loop thread."""
    from pdomain_ocr_simple_gui import layout_pass

    caller = threading.get_ident()
    seen: list[int] = []

    class _ThreadRecorder:
        def detect(self, source: object) -> PageLayout:
            seen.append(threading.get_ident())
            _ = source
            return PageLayout(regions=[], detector="sentinel")

    monkeypatch.setattr(layout_pass, "load_layout_detector", lambda _device: _ThreadRecorder())

    source = tmp_path / "source"
    source.mkdir()
    _write_png(source / "page.png", np.full((8, 8, 3), 255, dtype=np.uint8))
    page = await _page_dict()
    page["width"] = 8
    page["height"] = 8
    spec = _spec(tmp_path, source)
    _seed(spec, "page.png")
    await run_project(spec, _OnePageDispatcher(page), _status)

    assert seen
    assert seen[0] != caller


def test_failed_layout_load_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """One failed model load covers the rest of the job."""
    from pdomain_ocr_simple_gui import layout_pass

    calls = 0

    def _load(_device: str) -> object:
        nonlocal calls
        calls += 1
        raise RuntimeError("weights unavailable")

    monkeypatch.setattr(layout_pass, "load_layout_detector", _load)
    session = layout_pass.LayoutSession("cpu")
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    assert session.detect(image, page_name="page.png") is None
    assert session.detect(image, page_name="page.png") is None
    assert calls == 1


def test_layout_sessions_detect_one_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two jobs must not run the shared layout model at the same time."""
    from pdomain_ocr_simple_gui import layout_pass

    in_detect = 0
    peak = 0
    counter = threading.Lock()

    class _Slow:
        def detect(self, source: object) -> PageLayout:
            nonlocal in_detect, peak
            _ = source
            with counter:
                in_detect += 1
                peak = max(peak, in_detect)
            time.sleep(0.05)
            with counter:
                in_detect -= 1
            return PageLayout(regions=[], detector="slow")

    monkeypatch.setattr(layout_pass, "load_layout_detector", lambda _device: _Slow())
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    sessions = [layout_pass.LayoutSession("cpu") for _ in range(2)]
    errors: list[BaseException] = []

    def _run(session: layout_pass.LayoutSession) -> None:
        try:
            session.detect(image, page_name="page.png")
        except Exception as exc:
            errors.append(exc)

    workers = [threading.Thread(target=_run, args=(session,)) for session in sessions]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert errors == []
    assert peak == 1


def test_load_layout_detector_uses_pp_doclayout_plus_l(monkeypatch: pytest.MonkeyPatch) -> None:
    """The GUI asks book-tools for the same default model the CLI uses."""
    import pdomain_book_tools.layout as layout_mod

    seen: dict[str, object] = {}

    def _get(*args: object, **kwargs: object) -> object:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(layout_mod, "get_detector", _get)
    load_layout_detector("cpu")
    kwargs = seen["kwargs"]
    assert isinstance(kwargs, dict)
    assert seen["args"] == ("pp-doclayout-plus-l",)
    assert kwargs["device"] == "cpu"
    assert kwargs["confidence"] == 0.5


async def _status(status: ProjectStatus) -> None:
    _ = status

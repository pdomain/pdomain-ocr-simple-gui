"""Run PP-DocLayout on the upright OCR image and reorganize with that layout.

This is the same book-tools pairing as ``pdomain-ocr-cli``: detector
``pp-doclayout-plus-l``, word dropping left off, and the ``PageLayout``
passed to ``Page.reorganize_page``. The dispatcher only returns
``Page.to_dict()``, which drops the upright pixels book-tools stashed
after auto-rotate, so the upright frame is rebuilt from the page size
and the word boxes before ``detect`` runs.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Protocol, cast

import cv2
import numpy as np
from numpy import ndarray
from pdomain_book_tools.ocr.rotation import rotate_image

if TYPE_CHECKING:
    from pathlib import Path

    from pdomain_book_contracts.layout.types import PageLayout

logger = logging.getLogger(__name__)

_LAYOUT_MODEL = "pp-doclayout-plus-l"
_LAYOUT_CONFIDENCE = 0.5
_QUARTER_TURNS = (0, 90, 180, 270)
# get_detector memoises one model. Two jobs must not call detect together.
_DETECT_LOCK = threading.Lock()


class _LayoutDetector(Protocol):
    def detect(self, source: object) -> PageLayout:
        """Return regions for one page image."""
        ...


def load_layout_detector(device: str) -> _LayoutDetector:
    """Return the shared PP-DocLayout-Plus-L detector on ``device``."""
    from pdomain_book_tools.layout import get_detector

    return cast(
        "_LayoutDetector",
        get_detector(
            _LAYOUT_MODEL,
            device=device,
            confidence=_LAYOUT_CONFIDENCE,
        ),
    )


def layout_torch_device(choice: str) -> str:
    """Map a job device choice to the torch device the layout model accepts.

    ``cpu`` stays on CPU. ``auto`` and ``gpu`` follow CUDA, then MPS, then CPU.
    This never returns the ops device name ``local``.
    """
    if choice == "cpu":
        return "cpu"
    return _probe_torch_device()


class LayoutSession:
    """One job's layout detector.

    The model loads on the first page that needs it. A failed load is
    remembered for the rest of the job, so a missing checkpoint is not
    downloaded again on every page. ``detect`` holds a process-wide lock
    because the book-tools registry returns one shared model.
    """

    def __init__(self, device_choice: str) -> None:
        self._device_choice: str = device_choice
        self._detector: _LayoutDetector | None = None
        self._load_failed: bool = False

    def detect(self, source: ndarray, *, page_name: str) -> PageLayout | None:
        """Detect layout for one upright page, or return None."""
        with _DETECT_LOCK:
            detector = self._load(page_name)
            if detector is None:
                return None
            try:
                return detector.detect(source)
            except Exception:
                logger.exception("layout detection failed for %s", page_name)
                return None

    def _load(self, page_name: str) -> _LayoutDetector | None:
        if self._load_failed:
            return None
        if self._detector is not None:
            return self._detector
        try:
            self._detector = load_layout_detector(layout_torch_device(self._device_choice))
        except Exception:
            logger.exception(
                "layout detector failed to load; skipping layout for the rest of this job (%s)",
                page_name,
            )
            self._load_failed = True
            return None
        return self._detector


def reorganize_ocr_page(
    page_dict: dict[str, object],
    image_path: Path,
    *,
    emit_illustration_placeholders: bool,
    session: LayoutSession,
) -> tuple[dict[str, object], str]:
    """Reorganize one OCR page dict, using layout when detection succeeds.

    ``drop_layout_words`` stays false, matching the CLI default. A failure
    to decode the image or to run the detector still reorganizes the words.
    ``Page.from_dict`` and ``reorganize_page`` errors propagate so the
    caller can keep the raw OCR text.
    """
    from pdomain_book_tools.ocr.page import Page

    page = Page.from_dict(page_dict)
    layout = detect_page_layout(image_path, page_dict, session=session)
    page.reorganize_page(
        layout=layout,
        drop_layout_words=False,
        emit_illustration_placeholders=emit_illustration_placeholders,
    )
    return page.to_dict(), page.text


def detect_page_layout(
    image_path: Path,
    page_dict: dict[str, object],
    *,
    session: LayoutSession,
) -> PageLayout | None:
    """Detect layout on the upright image, or return None when that cannot run."""
    image = _read_bgr(image_path)
    if image is None:
        logger.info("layout detection skipped; could not decode %s", image_path.name)
        return None
    upright = _upright_image(image, page_dict, image_path.name)
    return session.detect(upright, page_name=image_path.name)


def _probe_torch_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"

    cuda = getattr(torch, "cuda", None)
    cuda_is_available = getattr(cuda, "is_available", None)
    if callable(cuda_is_available) and bool(cuda_is_available()):
        return "cuda"

    backends = getattr(torch, "backends", None)
    mps = getattr(backends, "mps", None)
    mps_is_available = getattr(mps, "is_available", None)
    if callable(mps_is_available) and bool(mps_is_available()):
        return "mps"
    return "cpu"


def _read_bgr(image_path: Path) -> ndarray | None:
    encoded = np.frombuffer(image_path.read_bytes(), dtype=np.uint8)
    decoded = cv2.imdecode(np.array(encoded), cv2.IMREAD_COLOR)
    if decoded is None:
        return None
    return cast("ndarray", decoded)


def _upright_image(image: ndarray, page_dict: dict[str, object], page_name: str) -> ndarray:
    """Return ``image`` turned so it matches the frame OCR text uses.

    Auto-rotate keeps word boxes in the rotated frame and discards the
    angle. Quarter-turns that reproduce the page width and height are the
    candidates. When two remain, the turn whose word boxes cover more ink
    is the upright one. A tie keeps the earlier turn, so an unrotated page
    stays as it is.
    """
    page_width, page_height = _page_size(page_dict)
    height, width = _hw(image)
    if page_width <= 0 or page_height <= 0:
        return image

    candidates = [
        degrees
        for degrees in _QUARTER_TURNS
        if _turned_size(width, height, degrees) == (page_width, page_height)
    ]
    if not candidates:
        logger.debug(
            "layout image for %s kept on disk; page is %sx%s and the file is %sx%s",
            page_name,
            page_width,
            page_height,
            width,
            height,
        )
        return image

    boxes = _word_boxes(page_dict)
    best = image
    best_degrees = candidates[0]
    best_score = -1.0
    for degrees in candidates:
        turned = image if degrees == 0 else rotate_image(image, degrees)
        score = _ink_score(turned, boxes)
        if score > best_score:
            best = turned
            best_degrees = degrees
            best_score = score
    if best_degrees != 0:
        logger.info("layout image for %s rotated %d degrees to match OCR", page_name, best_degrees)
    return best


def _turned_size(width: int, height: int, degrees: int) -> tuple[int, int]:
    if degrees in (90, 270):
        return height, width
    return width, height


def _page_size(page_dict: dict[str, object]) -> tuple[int, int]:
    width = _as_float(page_dict.get("width"))
    height = _as_float(page_dict.get("height"))
    if width is None or height is None:
        return 0, 0
    return int(width), int(height)


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _word_boxes(page_dict: dict[str, object]) -> list[tuple[float, float, float, float]]:
    return _walk_boxes(page_dict)


def _walk_boxes(node: dict[str, object]) -> list[tuple[float, float, float, float]]:
    if node.get("type") == "Word":
        box = _normalized_box(node.get("bounding_box"))
        return [box] if box is not None else []
    boxes: list[tuple[float, float, float, float]] = []
    for item in _child_nodes(node.get("items")):
        boxes.extend(_walk_boxes(item))
    return boxes


def _normalized_box(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, dict):
        return None
    raw = cast("dict[str, object]", value)
    top_left = raw.get("top_left")
    bottom_right = raw.get("bottom_right")
    if not isinstance(top_left, dict) or not isinstance(bottom_right, dict):
        return None
    tl = cast("dict[str, object]", top_left)
    br = cast("dict[str, object]", bottom_right)
    x0 = _as_float(tl.get("x"))
    y0 = _as_float(tl.get("y"))
    x1 = _as_float(br.get("x"))
    y1 = _as_float(br.get("y"))
    if x0 is None or y0 is None or x1 is None or y1 is None:
        return None
    width = x1 - x0
    height = y1 - y0
    if width <= 0 or height <= 0:
        return None
    return x0, y0, width, height


def _ink_score(image: ndarray, boxes: list[tuple[float, float, float, float]]) -> float:
    """Mean darkness inside word boxes. Higher means the boxes sit on ink."""
    if not boxes:
        return 0.0
    gray = _as_gray(image)
    height, width = _hw(gray)
    if width <= 0 or height <= 0:
        return 0.0
    weighted = 0.0
    counted = 0
    for x, y, box_w, box_h in boxes:
        x0 = max(0, min(width, int(x * width)))
        y0 = max(0, min(height, int(y * height)))
        x1 = max(0, min(width, int((x + box_w) * width)))
        y1 = max(0, min(height, int((y + box_h) * height)))
        if x1 <= x0 or y1 <= y0:
            continue
        darkness, pixels = _patch_stats(gray[y0:y1, x0:x1])
        if pixels == 0:
            continue
        weighted += darkness * pixels
        counted += pixels
    if counted == 0:
        return 0.0
    return weighted / counted


def _hw(image: ndarray) -> tuple[int, int]:
    """Height and width. Zero when the array is not at least two-dimensional.

    A bare ``ndarray`` types its shape as ``tuple[Any, ...]``. Decoded pages
    are height by width, or height by width by channel.
    """
    if image.ndim < 2:
        return 0, 0
    shape = cast("tuple[int, ...]", image.shape)
    return shape[0], shape[1]


def _as_gray(image: ndarray) -> ndarray:
    if image.ndim != 3:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _patch_stats(patch: ndarray) -> tuple[float, int]:
    """Mean of ``255`` minus each byte, and the number of bytes.

    A non-uint8 patch contributes nothing. The caller weights by the
    byte count, so a small box cannot outvote a large one.
    """
    if patch.dtype != np.uint8:
        return 0.0, 0
    raw = patch.tobytes()
    if not raw:
        return 0.0, 0
    return 255.0 - (sum(raw) / len(raw)), len(raw)


def _child_nodes(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast("dict[str, object]", item) for item in cast("list[object]", value) if isinstance(item, dict)]

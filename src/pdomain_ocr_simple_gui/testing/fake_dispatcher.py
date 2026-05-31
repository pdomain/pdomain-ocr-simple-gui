"""Deterministic fake OCR dispatcher for testing.

``FakeStageDispatcher`` implements the ``OCRDispatcher`` protocol from
``pdomain_ocr_simple_gui.pipeline`` without loading any model weights.  Every
call to ``run_ocr_batch`` returns one page dict per input image, each
containing the configured text and a minimal non-empty word-bounding-box tree
so that downstream code (sidecar builder, word overlays, ``extract_text``) all
behave as they would with a real dispatcher.

The emitted dict mirrors the real ``Page.to_dict()`` shape from
``pdomain-book-tools``, so it passes ``Page.from_dict()`` without triggering
the pipeline's text-only fallback.  The canonical hierarchy is::

    Page (page_index, width, height)
    └── Block (child_type=BLOCKS, block_category=BLOCK)
        └── Block (child_type=BLOCKS, block_category=PARAGRAPH)
            └── Block (child_type=WORDS, block_category=LINE)
                └── Word (text, bounding_box, ocr_confidence)

Intended use::

    from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

    # In a conftest.py fixture:
    monkeypatch.setattr(pdomain_ocr_simple_gui.app, "_dispatcher", FakeStageDispatcher())

    # Or as a FastAPI dependency override (see conftest use_fake_dispatcher fixture).
"""

from __future__ import annotations

from typing import cast


def _bbox_dict(tl_x: float, tl_y: float, br_x: float, br_y: float) -> dict[str, object]:
    """Return a normalized BoundingBox dict as produced by ``BoundingBox.to_dict()``."""
    return {
        "top_left": {"x": tl_x, "y": tl_y, "is_normalized": True},
        "bottom_right": {"x": br_x, "y": br_y, "is_normalized": True},
        "is_normalized": True,
    }


def _word_node(
    text: str, x: float = 0.1, y: float = 0.1, w: float = 0.1, h: float = 0.05
) -> dict[str, object]:
    """Build a Word node in ``pdomain-book-tools`` ``Page.to_dict()`` format.

    Includes all required fields so that ``Word.from_dict()`` succeeds
    without falling back to defaults that would strip geometry.
    """
    return {
        "type": "Word",
        "text": text,
        "bounding_box": _bbox_dict(x, y, x + w, y + h),
        "ocr_confidence": 0.99,
        "word_labels": [],
        "text_style_labels": ["regular"],
        "text_style_label_scopes": {"regular": "whole"},
        "word_components": [],
        "baseline": None,
        "ground_truth_text": None,
        "ground_truth_bounding_box": None,
        "ground_truth_match_keys": {},
    }


def _bbox_corners(node: dict[str, object]) -> tuple[float, float, float, float]:
    """Return (tl_x, tl_y, br_x, br_y) from a node whose "bounding_box" key
    holds a dict produced by :func:`_bbox_dict`.

    Uses :func:`cast` to satisfy basedpyright's ``reportIndexIssue`` — the
    values are always floats/dicts produced internally by this module.
    """
    bb = cast("dict[str, object]", node["bounding_box"])
    tl = cast("dict[str, object]", bb["top_left"])
    br = cast("dict[str, object]", bb["bottom_right"])
    return (
        float(cast("float", tl["x"])),
        float(cast("float", tl["y"])),
        float(cast("float", br["x"])),
        float(cast("float", br["y"])),
    )


def _union_bbox(nodes: list[dict[str, object]]) -> dict[str, object]:
    """Return a ``_bbox_dict`` that is the union of all nodes' bounding boxes."""
    corners = [_bbox_corners(n) for n in nodes]
    return _bbox_dict(
        min(c[0] for c in corners),
        min(c[1] for c in corners),
        max(c[2] for c in corners),
        max(c[3] for c in corners),
    )


def _block_dict(
    child_type: str,
    block_category: str,
    items: list[dict[str, object]],
) -> dict[str, object]:
    """Build a Block node dict with all required fields populated."""
    return {
        "type": "Block",
        "child_type": child_type,
        "block_category": block_category,
        "block_labels": None,
        "block_role_labels": [],
        "block_position_labels": [],
        "line_role_labels": [],
        "line_position_labels": [],
        "baseline": None,
        "bounding_box": _union_bbox(items),
        "items": items,
        "override_page_sort_order": None,
        "unmatched_ground_truth_words": [],
        "additional_block_attributes": {},
        "base_ground_truth_text": "",
    }


def _line_block(word_nodes: list[dict[str, object]]) -> dict[str, object]:
    """Wrap *word_nodes* in a LINE block (child_type=WORDS)."""
    if not word_nodes:
        raise ValueError("_line_block: word_nodes must be non-empty")
    return _block_dict("WORDS", "LINE", word_nodes)


def _paragraph_block(line_blocks: list[dict[str, object]]) -> dict[str, object]:
    """Wrap *line_blocks* in a PARAGRAPH block (child_type=BLOCKS)."""
    if not line_blocks:
        raise ValueError("_paragraph_block: line_blocks must be non-empty")
    return _block_dict("BLOCKS", "PARAGRAPH", line_blocks)


def _top_block(paragraph_blocks: list[dict[str, object]]) -> dict[str, object]:
    """Wrap *paragraph_blocks* in a top-level BLOCK (child_type=BLOCKS)."""
    if not paragraph_blocks:
        raise ValueError("_top_block: paragraph_blocks must be non-empty")
    return _block_dict("BLOCKS", "BLOCK", paragraph_blocks)


def _page_dict_for(text: str, page_index: int = 0) -> dict[str, object]:
    """Build a ``Page.to_dict()``-compatible dict with one block/paragraph/line.

    The hierarchy mirrors the real ``pdomain-book-tools`` output so that
    ``Page.from_dict()`` accepts it and the pipeline's ``reorganize_page()``
    step does not trigger the text-only fallback.

    The text is split on whitespace; each token becomes one Word node.
    Words are laid out left-to-right in a single LINE block, wrapped in a
    PARAGRAPH inside a top-level BLOCK.
    """
    tokens = text.split()
    if not tokens:
        tokens = [text]  # shouldn't happen after __init__ validation

    word_nodes: list[dict[str, object]] = []
    x = 0.05
    word_width = 0.1
    gap = 0.02
    for token in tokens:
        word_nodes.append(_word_node(token, x=x, y=0.1, w=word_width, h=0.05))
        x += word_width + gap

    line = _line_block(word_nodes)
    paragraph = _paragraph_block([line])
    block = _top_block([paragraph])

    return {
        "type": "Page",
        "width": 800,
        "height": 1000,
        "page_index": page_index,
        "bounding_box": _bbox_dict(0.0, 0.0, 1.0, 1.0),
        "items": [block],
        "ocr_provenance": None,
        "source": "ocr",
        "ocr_failed": False,
        "rotation_applied": 0,
        "image_path": None,
        "name": None,
    }


class FakeStageDispatcher:
    """Deterministic fake implementing the ``OCRDispatcher`` protocol.

    Every page dict returned by :meth:`run_ocr_batch` passes
    ``Page.from_dict()`` from ``pdomain-book-tools`` without triggering
    the pipeline's text-only fallback — the full four-level
    ``Page → Block → Paragraph → Line → Word`` hierarchy is populated with
    deterministic geometry so that ``GET /api/pages/{id}/{idx}/words``
    returns real bounding boxes.

    Parameters
    ----------
    text:
        The text string that every page result will carry.  Must be
        non-blank (an empty/whitespace-only string would silently produce
        pages with no content, masking downstream assertion bugs).

    Raises:
    ------
    ValueError
        When *text* is blank or whitespace-only.
    """

    def __init__(self, text: str = "fake OCR output") -> None:
        """Initialise the fake dispatcher with a fixed output text."""
        if not text or not text.strip():
            raise ValueError("FakeStageDispatcher: text must be non-blank")
        self._text = text

    async def run_ocr_batch(self, req: object) -> list[dict[str, object]]:
        """Return one page dict per image in *req*, all with the configured text.

        The returned dicts match the ``Page.to_dict()`` shape that the pipeline
        post-processes: ``{"type": "Page", "page_index": int, "width": int,
        "height": int, "items": [Block nodes...]}``.

        Each block node follows the real
        ``Block(child_type=BLOCKS/WORDS) → Word`` nesting so that
        ``Page.from_dict()`` accepts the dict and ``extract_words`` returns
        real bounding boxes instead of an empty list.
        """
        # req is an OcrBatchRequest (real or local fallback) or a compatible
        # test stub — use duck typing on the ``images`` attribute so this code
        # works whether pdomain-ops is >= 0.3.1 (has the real type) or == 0.3.0
        # (local fallback dataclass defined in pipeline.py).
        images = getattr(req, "images", None)
        count = len(images) if isinstance(images, (list, tuple)) else 1
        return [_page_dict_for(self._text, page_index=i) for i in range(count)]

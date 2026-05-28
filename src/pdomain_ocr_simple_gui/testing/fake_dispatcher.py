"""Deterministic fake OCR dispatcher for testing.

``FakeStageDispatcher`` implements the ``OCRDispatcher`` protocol from
``pdomain_ocr_simple_gui.pipeline`` without loading any model weights.  Every
call to ``run_ocr_batch`` returns one page dict per input image, each
containing the configured text and a minimal non-empty word-bounding-box tree
so that downstream code (sidecar builder, word overlays, ``extract_text``) all
behave as they would with a real dispatcher.

Intended use::

    from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

    # In a conftest.py fixture:
    monkeypatch.setattr(pdomain_ocr_simple_gui.app, "_dispatcher", FakeStageDispatcher())

    # Or as a FastAPI dependency override (see conftest use_fake_dispatcher fixture).
"""

from __future__ import annotations


def _word_node(
    text: str, x: float = 0.1, y: float = 0.1, w: float = 0.2, h: float = 0.05
) -> dict[str, object]:
    """Build a minimal Word node in pdomain-book-tools Page.to_dict() format."""
    return {
        "type": "Word",
        "text": text,
        "bounding_box": {
            "top_left": {"x": x, "y": y, "is_normalized": True},
            "bottom_right": {"x": x + w, "y": y + h, "is_normalized": True},
            "is_normalized": True,
        },
        "ocr_confidence": 0.99,
        "items": [],
    }


def _page_dict_for(text: str) -> dict[str, object]:
    """Build a minimal Page dict in DocTR / pdomain-book-tools export format.

    Produces a Page → Block (child_type=WORD) → Word tree so that both
    ``pipeline.extract_text`` and ``pipeline.extract_words`` return correct
    results without any real OCR model.

    The text is split on whitespace; each token becomes one Word node.
    Words are laid out left-to-right in a single line block.
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

    block: dict[str, object] = {
        "type": "Block",
        "child_type": "WORD",
        "items": word_nodes,
        "bounding_box": {
            "top_left": {"x": 0.05, "y": 0.1, "is_normalized": True},
            "bottom_right": {"x": x, "y": 0.15, "is_normalized": True},
            "is_normalized": True,
        },
    }

    return {
        "type": "Page",
        "width": 800,
        "height": 1000,
        "items": [block],
        "bounding_box": {
            "top_left": {"x": 0.0, "y": 0.0, "is_normalized": True},
            "bottom_right": {"x": 1.0, "y": 1.0, "is_normalized": True},
            "is_normalized": True,
        },
    }


class FakeStageDispatcher:
    """Deterministic fake implementing the ``OCRDispatcher`` protocol.

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
        post-processes: ``{"type": "Page", "width": int, "height": int,
        "items": [Block nodes...]}``.  ``extract_text`` and ``extract_words``
        in ``pipeline.py`` will produce correct results from these dicts.
        """
        # req is an OcrBatchRequest or compatible object; we only need len(images)
        images_attr = getattr(req, "images", None)
        count = len(images_attr) if isinstance(images_attr, (list, tuple)) else 1
        return [_page_dict_for(self._text) for _ in range(count)]

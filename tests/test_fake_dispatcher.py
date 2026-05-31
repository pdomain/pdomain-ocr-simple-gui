"""Tests for the deterministic fake OCR dispatcher used in integration tests."""

from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest
from pdomain_book_tools.ocr.page import Page

from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher


class _SingleImageReq:
    """Minimal OcrBatchRequest-like stub with one image."""

    images: ClassVar[list[bytes]] = [b"fakebytes"]
    source_identifiers: ClassVar[list[str]] = ["proj/0"]
    engine = "doctr"
    language = "en"
    device = None


class _ThreeImageReq:
    """Minimal OcrBatchRequest-like stub with three images."""

    images: ClassVar[list[bytes]] = [b"a", b"b", b"c"]
    source_identifiers: ClassVar[list[str]] = ["proj/0", "proj/1", "proj/2"]
    engine = "doctr"
    language = "en"
    device = None


def test_fake_dispatcher_returns_deterministic_page_text() -> None:
    """FakeStageDispatcher.run_ocr_batch returns a list with the configured text."""
    disp = FakeStageDispatcher(text="lorem")

    result = asyncio.run(disp.run_ocr_batch(_SingleImageReq()))
    assert len(result) == 1
    page_dict = result[0]
    # Must be a dict (JsonObject shape that pipeline post-processes)
    assert isinstance(page_dict, dict)
    # Text is extractable via pipeline.extract_text
    from pdomain_ocr_simple_gui.pipeline import extract_text

    text = extract_text(page_dict)
    assert text == "lorem"


def test_fake_dispatcher_returns_non_empty_words() -> None:
    """FakeStageDispatcher page dict carries at least one Word node for overlay rendering."""
    disp = FakeStageDispatcher(text="hello world")
    result = asyncio.run(disp.run_ocr_batch(_SingleImageReq()))
    page_dict = result[0]

    # Collect all Word nodes
    words: list[dict[str, object]] = []

    def _collect(node: dict[str, object]) -> None:
        if node.get("type") == "Word":
            words.append(node)
            return
        for item in node.get("items") or []:
            if isinstance(item, dict):
                _collect(item)  # type: ignore[arg-type]

    _collect(page_dict)
    assert len(words) >= 1, "Expected at least one Word node for overlay rendering"


def test_fake_dispatcher_batch_returns_one_result_per_image() -> None:
    """run_ocr_batch returns exactly one page dict per image in the request."""
    disp = FakeStageDispatcher(text="page text")
    result = asyncio.run(disp.run_ocr_batch(_ThreeImageReq()))
    assert len(result) == 3


def test_fake_dispatcher_default_text() -> None:
    """FakeStageDispatcher uses 'fake OCR output' when no text is supplied."""
    from pdomain_ocr_simple_gui.pipeline import extract_text

    disp = FakeStageDispatcher()
    result = asyncio.run(disp.run_ocr_batch(_SingleImageReq()))
    text = extract_text(result[0])
    assert text == "fake OCR output"


@pytest.mark.parametrize(
    "bad_text",
    ["", "  "],
    ids=["empty", "whitespace-only"],
)
def test_fake_dispatcher_rejects_blank_text(bad_text: str) -> None:
    """FakeStageDispatcher raises ValueError for blank text (would produce empty results)."""
    with pytest.raises(ValueError, match="text"):
        FakeStageDispatcher(text=bad_text)


def test_fake_dispatcher_page_dict_passes_from_dict() -> None:
    """Page.from_dict() accepts the fake page dict without raising.

    This test verifies that the fake emits the real Page.to_dict() shape,
    so the pipeline's reorganize_page() step does NOT trigger the
    text-only fallback.  The parsed page must expose at least one Word
    with a valid bounding box — matching the contract a real dispatcher
    would satisfy.
    """
    disp = FakeStageDispatcher(text="hello world")
    result = asyncio.run(disp.run_ocr_batch(_SingleImageReq()))
    page_dict = result[0]

    # Must not raise (previously raised ValueError: BlockChildType("WORD"))
    page = Page.from_dict(page_dict)

    # The parsed page must have words with geometry
    words = page.words
    assert len(words) >= 1, "Page.from_dict result must contain at least one Word"
    for word in words:
        assert word.bounding_box is not None, f"Word {word.text!r} has no bounding_box"
        bb = word.bounding_box
        assert bb.is_normalized, "Word bounding box must be normalised (0..1)"
        assert bb.width > 0, f"Word {word.text!r} bbox has zero width"
        assert bb.height > 0, f"Word {word.text!r} bbox has zero height"

    # Text round-trips correctly
    assert page.text.strip() == "hello world"


def test_fake_dispatcher_extract_words_returns_geometry() -> None:
    """extract_words() returns non-empty word records with valid bbox dicts.

    Ensures the fake's word geometry is preserved through the pipeline's
    dict-walking code (no fallback, no empty list).
    """
    from pdomain_ocr_simple_gui.pipeline import extract_words

    disp = FakeStageDispatcher(text="alpha beta gamma")
    result = asyncio.run(disp.run_ocr_batch(_SingleImageReq()))
    page_dict = result[0]

    words = extract_words(page_dict)
    assert len(words) == 3, f"Expected 3 word records, got {len(words)}"
    for rec in words:
        assert isinstance(rec["text"], str) and rec["text"]
        bbox = rec["bbox"]
        assert isinstance(bbox, dict)
        assert set(bbox.keys()) == {"x", "y", "w", "h"}
        assert float(bbox["w"]) > 0, "bbox width must be > 0"
        assert float(bbox["h"]) > 0, "bbox height must be > 0"
        assert isinstance(rec["confidence"], float)
        assert rec["confidence"] > 0


def test_fake_dispatcher_uses_images_attribute_from_real_request() -> None:
    """run_ocr_batch counts pages via the images attribute on the request object.

    Passes an OcrBatchRequest (real pdomain-ops type when >= 0.3.1; local
    fallback dataclass from pipeline.py when == 0.3.0) with two images and
    asserts exactly two page dicts are returned.  This exercises the duck-typed
    getattr(req, "images") path in FakeStageDispatcher.run_ocr_batch.
    """
    from pdomain_ocr_simple_gui.pipeline import OcrBatchRequest

    req = OcrBatchRequest(
        images=[b"fake-image-a", b"fake-image-b"],
        source_identifiers=["proj/0", "proj/1"],
        engine="doctr",
        language="en",
    )
    disp = FakeStageDispatcher(text="hello")
    result = asyncio.run(disp.run_ocr_batch(req))
    assert len(result) == 2, f"Expected 2 page dicts for 2 images, got {len(result)}"
    # page_index is set correctly for both pages
    assert result[0]["page_index"] == 0
    assert result[1]["page_index"] == 1

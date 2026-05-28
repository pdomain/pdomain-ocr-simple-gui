"""Tests for the deterministic fake OCR dispatcher used in integration tests."""

from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest

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

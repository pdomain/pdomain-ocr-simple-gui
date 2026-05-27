"""Playwright e2e test: uploading a single image opens the JobConfigDialog.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

B5.3: pick a file via the source-picker-file-pick input, assert the
run-ocr-button sentinel becomes visible in the JobConfigDialog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Skip the whole module if playwright is not installed
pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect

# Minimal valid 1x1 PNG (1x1 pixel, 8-bit grayscale, no alpha)
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"  # PNG signature
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"  # IHDR chunk
    b"\x00\x00\x00:~\x9bU"  # IHDR CRC
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"  # IDAT chunk
    b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND chunk
)


@pytest.mark.slow
@pytest.mark.e2e
def test_upload_single_image(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """Pick a single PNG via the file-pick input; JobConfigDialog should open."""
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Use set_input_files to simulate the file picker (works without browser dialog)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))

    # JobConfigDialog should open — its run-ocr-button sentinel becomes visible
    expect(page.get_by_test_id("run-ocr-button")).to_be_visible(timeout=10_000)

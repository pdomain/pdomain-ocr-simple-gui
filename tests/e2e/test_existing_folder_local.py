"""Playwright e2e test: typing a local folder path opens the JobConfigDialog.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

B5.4: type a folder path into source-picker-path-input, press Enter,
assert run-ocr-button becomes visible.

The folder must be accessible to the running uvicorn process.  We use
``tmp_path`` (pytest session workdir) which is already set via the
``PD_OCR_SIMPLE_GUI_UPLOAD_ROOT`` / ``PD_OCR_SIMPLE_GUI_OUTPUT_ROOT``
env in conftest — the spawned server inherits the same env, so any path
under ``/tmp`` or ``/workspaces/`` is accessible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Skip the whole module if playwright is not installed
pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect

# Minimal valid 1x1 PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.slow
@pytest.mark.e2e
def test_existing_folder_path(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """Type a folder path into the path input; JobConfigDialog should open."""
    folder = tmp_path / "scans"
    folder.mkdir()
    (folder / "p.png").write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Fill the path input and press Enter to submit the form
    path_input = page.get_by_test_id("source-picker-path-input")
    path_input.fill(str(folder))
    path_input.press("Enter")

    # JobConfigDialog should open — its run-ocr-button sentinel becomes visible
    expect(page.get_by_test_id("run-ocr-button")).to_be_visible(timeout=10_000)

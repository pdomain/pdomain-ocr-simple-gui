"""5.8 — full click-path: local path input → submit → results populated.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Fills the ``source-picker-path-input`` with a directory that contains a
seeded PNG image (same pattern as ``test_existing_folder_local.py`` but
continues all the way through job submission and result assertion).

The server runs with ``PDOMAIN_OCR_FAKE_DISPATCHER=1`` so the job completes
immediately with deterministic output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

# Minimal valid 1x1 greyscale PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.slow
@pytest.mark.e2e
def test_local_path_input_flow_reaches_results_with_page_rows(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    """Fill local path input with seeded image dir → submit → results has page-row."""
    # Seed a folder with one PNG that the server process can read
    folder = tmp_path / "scans"
    folder.mkdir()
    (folder / "page-001.png").write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # 1. Fill the path input and press Enter (the form submits on Enter)
    path_input = page.get_by_test_id("source-picker-path-input")
    path_input.fill(str(folder))
    path_input.press("Enter")

    # 2. Inline config form appears after path is accepted
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # 3. Submit the job
    page.get_by_test_id("run-ocr-button").click()

    # 4. Results page appears
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)

    # 5. At least one page-row populates once the fake dispatcher completes
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )
    expect(page.get_by_test_id("page-row").first).to_be_visible(timeout=5_000)

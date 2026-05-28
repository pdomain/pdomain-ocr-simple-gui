"""5.7 — full click-path: file-picker upload → submit → results populated.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Uses Playwright's ``set_input_files`` on the hidden ``source-picker-file-pick``
input to simulate the file picker.  After the upload completes the inline
config form appears and the test submits the job then waits for the results
page to show at least one page-row.
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
def test_file_picker_upload_flow_reaches_results_with_page_rows(
    page: Page, live_server_url: str, tmp_path: Path
) -> None:
    """Pick a PNG via file-input → submit job → results page has page-row."""
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # 1. Set files via the hidden file input (simulates the file picker)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))

    # 2. Inline config form appears after upload completes
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)

    # 3. Submit the job
    page.get_by_test_id("run-ocr-button").click()

    # 4. Results page appears
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=10_000)

    # 5. At least one page-row populates
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=15_000,
    )
    expect(page.get_by_test_id("page-row").first).to_be_visible(timeout=5_000)

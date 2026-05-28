"""5.10 — full click-path: download zip and download txt from results / page viewer.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Two sub-tests:
1. From the managed job's ResultsPage, click "Download results (.zip)" and
   assert Playwright expect_download fires for a non-empty .zip file.
2. From the seeded job's PageViewPage, click the "⤓ .txt" button and assert
   expect_download fires for a non-empty file.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_download_zip_from_results_page(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Download results .zip from managed-mode ResultsPage; assert non-empty download."""
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}")
    btn = page.get_by_test_id("download-results-button")
    expect(btn).to_be_visible(timeout=15_000)
    with page.expect_download() as dl_info:
        btn.click()
    download = dl_info.value
    assert download.suggested_filename.endswith(".zip"), (
        f"Expected .zip download, got {download.suggested_filename!r}"
    )
    path = download.path()
    assert path is not None and path.stat().st_size > 0, "Downloaded .zip file is empty"


@pytest.mark.slow
@pytest.mark.e2e
def test_download_txt_from_page_viewer(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Click the .txt download button on PageViewPage; assert non-empty download."""
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    txt_btn = page.get_by_test_id("page-download-text")
    expect(txt_btn).to_be_visible(timeout=5_000)
    with page.expect_download() as dl_info:
        txt_btn.click()
    download = dl_info.value
    path = download.path()
    assert path is not None and path.stat().st_size > 0, "Downloaded .txt file is empty"

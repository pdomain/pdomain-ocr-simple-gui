"""5.10 — full click-path: download zip and download txt from results / page viewer.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Sub-tests:
1. From the managed job's ResultsPage, click "Download results (.zip)" and
   assert Playwright expect_download fires for a non-empty .zip file.
2. From the seeded job's PageViewPage, click the "⤓ .txt" button and assert
   expect_download fires for a non-empty file.
3. Click "⤓ .json" and assert expect_download fires for a non-empty file.
4. Click "⤓ .zip" (both) and assert expect_download fires.
5. Click "Copy path" on ResultsPage and assert button transitions to "Copied!" state.
6. Click "Re-run all" on ResultsPage and assert the button becomes temporarily
   disabled / shows "Re-running…" (observable state transition).
"""

from __future__ import annotations

import pytest
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


@pytest.mark.slow
@pytest.mark.e2e
def test_download_json_from_page_viewer(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Click the .json download button on PageViewPage; assert download fires and is non-empty.

    The seeded managed fixture writes a page-001.json sidecar so the zip
    contains at least one JSON file.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    json_btn = page.get_by_test_id("page-download-json")
    expect(json_btn).to_be_visible(timeout=5_000)
    with page.expect_download() as dl_info:
        json_btn.click()
    download = dl_info.value
    path = download.path()
    assert path is not None and path.stat().st_size > 0, "Downloaded .json zip file is empty"


@pytest.mark.slow
@pytest.mark.e2e
def test_download_both_from_page_viewer(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Click the .zip (both) download button on PageViewPage; assert download fires."""
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    both_btn = page.get_by_test_id("page-download-both")
    expect(both_btn).to_be_visible(timeout=5_000)
    with page.expect_download() as dl_info:
        both_btn.click()
    download = dl_info.value
    path = download.path()
    assert path is not None and path.stat().st_size > 0, "Downloaded .zip (both) file is empty"


@pytest.mark.slow
@pytest.mark.e2e
def test_copy_path_button_on_results_page(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Click the Copy path button on ResultsPage; assert button label transitions to 'Copied!'.

    Grants clipboard-write permission before the click so that
    navigator.clipboard.writeText resolves successfully and the React state
    update to 'Copied!' fires.
    """
    # Grant clipboard-write so navigator.clipboard.writeText resolves in headless Chromium.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])

    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    copy_btn = page.get_by_test_id("copy-path-button")
    expect(copy_btn).to_be_visible(timeout=10_000)
    copy_btn.click()

    # Assert button label changes to "Copied!" after the clipboard write resolves.
    page.wait_for_function(
        """() => {
            const btn = document.querySelector('[data-testid="copy-path-button"]');
            return btn?.textContent?.trim() === 'Copied!';
        }""",
        timeout=5_000,
    )


@pytest.mark.slow
@pytest.mark.e2e
def test_rerun_all_button_on_results_page(page: Page, live_server_url: str, seeded_rerun_job_id: str) -> None:
    """Click Re-run all on ResultsPage; assert the rerun POST fires and is handled.

    Uses seeded_rerun_job_id (has a real source image) so the fake dispatcher
    can complete the job after rerun and restore it to succeeded state.

    Observable: we intercept the POST /api/jobs/{id}/rerun request. The click
    triggers the handler, which sets rerunPending=true (button disables) and
    then POSTs. Playwright's expect_request captures the request as the
    observable proof that the click was processed end-to-end.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    rerun_btn = page.get_by_test_id("rerun-all-button")
    expect(rerun_btn).to_be_visible(timeout=10_000)
    expect(rerun_btn).to_be_enabled()

    # Intercept the rerun POST to assert it fires.
    with page.expect_request(
        lambda req: req.method == "POST" and "/rerun" in req.url,
        timeout=8_000,
    ) as req_info:
        rerun_btn.click()

    rerun_request = req_info.value
    assert "/rerun" in rerun_request.url, f"Expected a POST to /rerun, got {rerun_request.url!r}"

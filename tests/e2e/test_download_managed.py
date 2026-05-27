"""B5.6 — managed-mode results download button.

Navigate to /jobs/<seeded_managed_job_id>, confirm the download button is
visible (the job is in managed mode), click it, and assert the browser
triggers a download of a .zip file.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_download_button_managed(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Download button is visible for a managed job and triggers a .zip download."""
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}")
    btn = page.get_by_test_id("download-results-button")
    expect(btn).to_be_visible(timeout=15_000)
    with page.expect_download() as dl_info:
        btn.click()
    download = dl_info.value
    assert download.suggested_filename.endswith(".zip"), (
        f"Expected .zip download, got {download.suggested_filename!r}"
    )

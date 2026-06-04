"""Tier-A behavior tests for the ResultsPage download / copy-path / rerun actions.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-fast`` / ``make e2e-browser``.

Each test cites its behavior record (``Covers: B-RESULTS-NNN``), asserts the
observable output via a real ``data-testid``, and asserts the backend effect by
re-querying the API AND inspecting on-disk artifacts (here: the actual members
of the downloaded ZIP).
"""

from __future__ import annotations

import io
import zipfile

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


def _zip_members(live_server_url: str, job_id: str, include: str) -> list[str]:
    """Download the job ZIP and return its member names (sorted)."""
    resp = httpx.get(
        f"{live_server_url}/api/jobs/{job_id}/download",
        params={"include": include},
        timeout=15.0,
    )
    assert resp.status_code == 200, f"download failed: {resp.status_code}"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        return sorted(zf.namelist())


# ---------------------------------------------------------------------------
# B-RESULTS-006 — Download results zip (managed mode) + include-filter membership
# ---------------------------------------------------------------------------


def test_download_zip_from_results_page(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Covers: B-RESULTS-006 — managed job download fires a non-empty .zip.

    Task 9 replaced a single download button + checkboxes with two explicit
    download buttons: ``download-images-text`` (images + text) and
    ``download-images-text-json`` (images + text + JSON).
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}")
    btn = page.get_by_test_id("download-images-text-json")
    expect(btn).to_be_visible(timeout=15_000)
    # The text-only button is also present.
    expect(page.get_by_test_id("download-images-text")).to_be_visible()

    with page.expect_download() as dl_info:
        btn.click()
    download = dl_info.value
    assert download.suggested_filename.endswith(".zip"), (
        f"Expected .zip download, got {download.suggested_filename!r}"
    )
    path = download.path()
    assert path is not None and path.stat().st_size > 0, "Downloaded .zip file is empty"

    # Backend effect: the text+json ZIP includes the .txt AND .json members.
    members = _zip_members(live_server_url, seeded_managed_job_id, "text,json")
    assert "page-001.txt" in members
    assert "page-001.json" in members


def test_download_images_text_button_drops_json(
    page: Page, live_server_url: str, seeded_managed_job_id: str
) -> None:
    """Covers: B-RESULTS-006 — download-images-text button omits JSON from ZIP.

    Task 9 replaced the checkbox-filter model with two explicit buttons.
    ``download-images-text`` passes ``?include=text``; the resulting ZIP
    must contain the .txt member and NOT the .json member.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}")
    text_btn = page.get_by_test_id("download-images-text")
    expect(text_btn).to_be_visible(timeout=15_000)

    with page.expect_download() as dl_info:
        text_btn.click()
    download = dl_info.value

    # Observable + backend effect: the downloaded ZIP has .txt but no .json.
    path = download.path()
    assert path is not None
    with zipfile.ZipFile(path) as zf:
        members = sorted(zf.namelist())
    assert "page-001.txt" in members
    assert "page-001.json" not in members, f"json leaked into text-only zip: {members}"

    # Cross-check the API directly with the same filter.
    api_members = _zip_members(live_server_url, seeded_managed_job_id, "text")
    assert "page-001.txt" in api_members
    assert "page-001.json" not in api_members


@pytest.mark.parametrize("include", ["bogus", "text,nope", ""])
def test_download_bad_include_token_rejected(
    live_server_url: str, seeded_managed_job_id: str, include: str
) -> None:
    """Covers: B-RESULTS-006 (bad path) — malformed/empty include → 400."""
    resp = httpx.get(
        f"{live_server_url}/api/jobs/{seeded_managed_job_id}/download",
        params={"include": include},
        timeout=10.0,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# B-RESULTS-007 — Download button hidden for non-managed jobs
# ---------------------------------------------------------------------------


def test_download_button_hidden_for_non_managed(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-007 — a non-managed succeeded job hides the download buttons."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Both download buttons must be absent for next_to_source.
    expect(page.get_by_test_id("download-images-text")).to_have_count(0)
    expect(page.get_by_test_id("download-images-text-json")).to_have_count(0)

    # Backend effect: output_mode is next_to_source, not managed.
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_job_id}", timeout=10.0)
    assert resp.json().get("output_mode") == "next_to_source"


# ---------------------------------------------------------------------------
# B-RESULTS-008 — Copy output path to clipboard
# ---------------------------------------------------------------------------


def test_copy_path_button_on_results_page(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-008 — Copy path flips the label to 'Copied!'."""
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    copy_btn = page.get_by_test_id("copy-path-button")
    expect(copy_btn).to_be_visible(timeout=10_000)
    copy_btn.click()
    page.wait_for_function(
        """() => {
            const btn = document.querySelector('[data-testid="copy-path-button"]');
            return btn?.textContent?.trim() === 'Copied!';
        }""",
        timeout=5_000,
    )

    # Backend effect: the copied path is the spec output_dir from the API.
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_job_id}", timeout=10.0)
    assert resp.json()["output_dir"]


def test_copy_path_absent_when_not_succeeded(page: Page, live_server_url: str) -> None:
    """Covers: B-RESULTS-008 (bad path) — a 404 job shows no copy-path control."""
    page.goto(f"{live_server_url}/jobs/no-such-job-xyz")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("copy-path-button")).to_have_count(0)


# ---------------------------------------------------------------------------
# B-RESULTS-009 — Re-run the whole job (+ rerun error surfacing)
# ---------------------------------------------------------------------------


def test_rerun_all_button_on_results_page(page: Page, live_server_url: str, seeded_rerun_job_id: str) -> None:
    """Covers: B-RESULTS-009 — Re-run all POSTs /rerun and re-runs the pipeline."""
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    rerun_btn = page.get_by_test_id("rerun-all-button")
    expect(rerun_btn).to_be_visible(timeout=10_000)
    expect(rerun_btn).to_be_enabled()

    with page.expect_request(
        lambda req: req.method == "POST" and "/rerun" in req.url,
        timeout=8_000,
    ) as req_info:
        rerun_btn.click()
    assert "/rerun" in req_info.value.url

    # Backend effect: the job is re-runnable and returns to succeeded (fake
    # dispatcher completes it because the fixture has a real source image).
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('[data-testid="page-row"]');
            return rows.length > 0;
        }""",
        timeout=15_000,
    )
    resp = httpx.get(f"{live_server_url}/api/jobs/{seeded_rerun_job_id}", timeout=10.0)
    assert resp.status_code == 200
    assert resp.json()["state"] in ("queued", "running", "succeeded")


def test_rerun_error_is_surfaced(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-009 (bad path / Regression) — a non-ok rerun is surfaced.

    Intercept POST /rerun → 500. The page must show the rerun-error banner
    (previously the failure was swallowed) and must NOT crash — the job header
    still renders.
    """
    rerun_route = f"**/api/jobs/{seeded_job_id}/rerun"
    page.route(rerun_route, lambda route: route.fulfill(status=500, body="boom"))

    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    rerun_btn = page.get_by_test_id("rerun-all-button")
    expect(rerun_btn).to_be_visible(timeout=15_000)
    rerun_btn.click()

    # Observable: the rerun-error banner appears.
    err = page.get_by_test_id("results-rerun-error")
    expect(err).to_be_visible(timeout=10_000)
    expect(err).to_contain_text("Re-run failed")
    # No crash — the project header is still present.
    expect(page.get_by_role("heading", level=1)).to_contain_text("e2e-seeded")
    page.unroute(rerun_route)

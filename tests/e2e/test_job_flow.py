"""Playwright e2e tests: job submission → results page → page view.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

These tests use the API directly (not the full UI drag-and-drop flow)
to create a job, then navigate to the results page and verify rendering.
The UI-driven flow (DropZone drag + JobConfigDialog fill) requires a real
filesystem path that the browser can't introspect, so we POST via the API
and then assert the resulting page loads correctly.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import pytest

# Skip the whole module if playwright is not installed (e.g. in CI without --group e2e)
pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect

_FIXTURE_IMAGE = Path("/workspaces/ocr-container/pdomain-book-tools/tests/ocr-test-image.png")


def _create_job_via_api(base_url: str, source_dir: str, output_dir: str) -> str:
    """POST to /api/jobs and return the project_id."""
    resp = httpx.post(
        f"{base_url}/api/jobs",
        json={
            "name": "e2e-playwright-test",
            "source_path": source_dir,
            "output_dir": output_dir,
            "engine": "doctr",
            "language": "eng",
            "save_json": False,
            "combined_txt": False,
        },
        timeout=10.0,
    )
    assert resp.status_code == 200, f"POST /api/jobs failed: {resp.text}"
    return resp.json()["project_id"]


@pytest.mark.slow
@pytest.mark.e2e
def test_results_page_renders_after_job_creation(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """Create a job via API, navigate to /jobs/<id>, confirm results page renders."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    if _FIXTURE_IMAGE.exists():
        shutil.copy(_FIXTURE_IMAGE, source_dir / _FIXTURE_IMAGE.name)
    else:
        # Create a tiny placeholder so the job has a page to process
        (source_dir / "page0.png").touch()

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    project_id = _create_job_via_api(live_server_url, str(source_dir), str(output_dir))

    page.goto(f"{live_server_url}/jobs/{project_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible()


@pytest.mark.slow
@pytest.mark.e2e
def test_results_page_contains_page_rows(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """Results page shows page rows after a job with at least one image is created."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    # Create a tiny placeholder image so there's at least one page row
    (source_dir / "page0.png").touch()

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    project_id = _create_job_via_api(live_server_url, str(source_dir), str(output_dir))

    page.goto(f"{live_server_url}/jobs/{project_id}")
    # Wait for page to load and poll until rows appear or job settles
    # (the results page polls live, so rows appear once job registers pages)
    expect(page.get_by_test_id("results-page")).to_be_visible()
    # At least one page row should eventually appear (job has 1 image)
    expect(page.get_by_test_id("page-row").first).to_be_visible(timeout=10_000)


@pytest.mark.slow
@pytest.mark.e2e
def test_page_view_opens_from_results_row(page: Page, live_server_url: str, tmp_path: Path) -> None:
    """Click a results-page row → navigate to /jobs/<id>/pages/<idx> → panels visible."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "page0.png").touch()

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    project_id = _create_job_via_api(live_server_url, str(source_dir), str(output_dir))

    page.goto(f"{live_server_url}/jobs/{project_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible()

    # Wait for at least one page-row to appear
    first_row = page.get_by_test_id("page-row").first
    expect(first_row).to_be_visible(timeout=10_000)

    # Click the row → should navigate to PageView
    first_row.click()

    # Confirm navigation to /jobs/<id>/pages/<idx>
    page.wait_for_url(f"**/jobs/{project_id}/pages/**", timeout=5_000)
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=5_000)

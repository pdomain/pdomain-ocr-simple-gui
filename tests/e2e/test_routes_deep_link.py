"""B5.7 — deep-link to /jobs/<id> renders the results page.

This test proves the React Router catch-all works correctly in the
production SPA bundle (served by FastAPI's static file mount):
a direct browser navigation to /jobs/<id> must render the ResultsPage,
not a 404 or blank screen.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_jobs_subpath_renders(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Direct navigation to /jobs/<id> serves the SPA and renders results-page."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

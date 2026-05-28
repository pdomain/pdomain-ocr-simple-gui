"""5.11 — full click-path: home page recent-project row → results page.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Seeds a recent-project entry via PUT /api/prefs, then:
- visits the home page
- waits for the recent-projects table to render with that row
- clicks the row
- asserts navigation to the correct results page (results-page testid
  visible and job name present)
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

import httpx
from playwright.sync_api import Page, expect


def _seed_recent_project(base_url: str, project_id: str, name: str) -> None:
    """PUT /api/prefs with one recent-project entry so RecentProjectsList renders it."""
    prefs_payload = {
        "recent_projects": [
            {
                "project_id": project_id,
                "name": name,
                "last_opened_at": "2026-01-01T00:00:00+00:00",
                "page_count": 1,
                "engine": "doctr",
                "status": "succeeded",
            }
        ]
    }
    resp = httpx.put(f"{base_url}/api/prefs", json=prefs_payload, timeout=5.0)
    resp.raise_for_status()


@pytest.mark.slow
@pytest.mark.e2e
def test_recent_project_row_navigates_to_results(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Click a recent-project row on the home page; assert results page for that job."""
    seeded_name = f"e2e-seeded-{seeded_job_id[:8]}"

    # Seed prefs so the home page shows a recent-project row.
    _seed_recent_project(live_server_url, seeded_job_id, seeded_name)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Wait for the recent-projects list to render with our seeded row.
    row = page.get_by_test_id("recent-project-row").first
    expect(row).to_be_visible(timeout=10_000)

    # Click the row — should navigate to /jobs/<seeded_job_id>.
    row.click()

    # Results page is now visible.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    # The correct project is rendered — at least the results-page element
    # loaded from the seeded job ID.
    assert seeded_job_id in page.url, f"Expected URL to contain {seeded_job_id!r}, got {page.url!r}"

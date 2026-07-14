"""5.11 — full click-path: home page recent-project row → results page.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-012 (recent-projects list renders from prefs; empty state)
Covers: B-HOME-013 (clicking a recent-project row navigates to its results)

Job creation populates recent_projects. This focused screen test seeds a row via
PUT /api/prefs so it can exercise rendering and navigation without creating a
job first. Then:
- visits the home page
- waits for the recent-projects table to render with that row
- clicks the row
- asserts navigation to the correct results page (results-page testid
  visible and job name present)
"""

from __future__ import annotations

import httpx
import pytest
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
    """B-HOME-013: click a recent-project row → navigate to its results page.

    Observable: results-page renders and the URL contains the project id.
    Backend effect: GET /api/jobs/{id} returns that project (the row was seeded
    into prefs via PUT /api/prefs — population is future Projects-page work).
    """
    seeded_name = f"e2e-seeded-{seeded_job_id[:8]}"

    # Seed prefs so the home page shows a recent-project row.
    _seed_recent_project(live_server_url, seeded_job_id, seeded_name)

    # Backend effect: the seeded row is readable back from prefs.
    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    assert any(p.get("project_id") == seeded_job_id for p in prefs.get("recent_projects", [])), prefs

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # B-HOME-012: the recent-projects list renders the seeded row.
    row = page.get_by_test_id("recent-project-row").first
    expect(row).to_be_visible(timeout=10_000)

    # B-HOME-013: click the row — should navigate to /jobs/<seeded_job_id>.
    row.click()

    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    assert seeded_job_id in page.url, f"Expected URL to contain {seeded_job_id!r}, got {page.url!r}"

    # Backend effect: the navigated project is retrievable.
    status = httpx.get(f"{live_server_url}/api/jobs/{seeded_job_id}", timeout=5.0).json()
    assert status["project_id"] == seeded_job_id


@pytest.mark.slow
@pytest.mark.e2e
def test_recent_projects_empty_state(page: Page, live_server_url: str) -> None:
    """B-HOME-012: with no recent projects, the list shows the empty message.

    Resets prefs to an empty recent_projects list (PUT overwrites AppPrefs),
    then asserts the recent-projects container shows 'No recent projects' and
    renders zero rows.
    """
    # Reset prefs so recent_projects is empty for this assertion.
    resp = httpx.put(f"{live_server_url}/api/prefs", json={"recent_projects": []}, timeout=5.0)
    resp.raise_for_status()

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    container = page.get_by_test_id("recent-projects-list")
    expect(container).to_be_visible(timeout=10_000)
    expect(container).to_contain_text("No recent projects", timeout=10_000)
    expect(page.get_by_test_id("recent-project-row")).to_have_count(0)

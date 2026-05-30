"""Browser verification: the served SPA loads, routes, and runs without errors.

Covers: B-SHELL-001 (app loads without console errors)
        B-RESULTS-001 (route renders sub-path content, not a blank/404)

These tests are complementary to the per-screen click-path tests.  The
click-path tests assert DOM state, API responses, and disk artifacts for
individual behaviors.  The smoke tests verify the baseline browser contract:

  1. The SPA initialises in a real browser without any ``console.error`` that
     indicates a broken resource load (``Failed to load``/``404``).
  2. React Router sub-paths are served by the FastAPI catch-all and rendered
     by the router — not a blank page or a raw 404 HTML response.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-fast`` / ``make e2e-browser``.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


# ---------------------------------------------------------------------------
# B-SHELL-001 — App loads without console errors
# ---------------------------------------------------------------------------


def test_app_loads_without_console_errors(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-001 — SPA loads in a real browser with no broken-resource errors.

    Complements ``test_app_shell_loads`` (which asserts shell structure + API
    fields).  This test exclusively checks that no ``console.error`` fires for
    a missing resource (``Failed to load``/``404``), which would indicate the
    Vite build is broken or a static asset is missing from the wheel.
    """
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(live_server_url)
    # Wait for the SPA to fully initialise (home-page testid rendered).
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Filter: only fail on hard resource-load errors (broken chunk / 404 asset).
    # Suppress React/application-level warnings; those are caught by
    # frontend-test (vitest).  The "Failed to load" / "404" pattern signals
    # a genuinely broken static bundle — not a policy warning.
    broken_resource_errors = [e for e in errors if "Failed to load" in e or "404" in e]
    assert broken_resource_errors == [], "SPA loaded with broken-resource console errors:\n" + "\n".join(
        broken_resource_errors
    )


# ---------------------------------------------------------------------------
# B-RESULTS-001 — React Router sub-path renders non-home content
# ---------------------------------------------------------------------------


def test_router_subpath_renders(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-RESULTS-001 — /jobs/:id is served by the FastAPI catch-all and
    rendered by React Router, not a raw 404 or blank page.

    Complements ``test_results_page_loads_name_and_pip`` (which asserts the
    project name, status pip, and disk artifact).  This test exclusively
    verifies the *routing contract*: the sub-path must NOT render the home
    page, and the document title must be non-empty (the SPA has initialised
    and mounted its page title).
    """
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")

    # Observable: the results page renders, not the home page.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("home-page")).to_have_count(0)

    # Observable: the document title is non-empty (SPA has mounted + set title).
    title = page.title()
    assert title != "", "Expected a non-empty page title after routing to /jobs/:id"

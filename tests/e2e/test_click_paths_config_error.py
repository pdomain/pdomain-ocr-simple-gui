"""Click-path: /api/config failure surfaces an error + retry (no infinite load).

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

Covers: B-HOME-014 (config-load failure → error UI + retry, not "Loading…")

The live server always returns 200 for /api/config, so the bad path is driven
by intercepting the route with Playwright (faking the dependency — a valid
Tier-A technique). The good-path recovery is then proven by unrouting and
clicking Retry, which re-fetches the real (200) config and renders HomePage.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_config_failure_shows_error_then_retry_recovers(page: Page, live_server_url: str) -> None:
    """B-HOME-014 (Regression): a failed /api/config shows error + retry, then recovers.

    Bad path: intercept /api/config → 500. HomePage renders the
    home-config-error alert + home-config-retry button (NOT a stuck "Loading…").
    Good path: stop intercepting, click Retry → the real config loads and the
    home-page renders.
    """
    # Bad path: force /api/config to fail.
    fail_route = "**/api/config"
    page.route(fail_route, lambda route: route.fulfill(status=500, body="boom"))

    page.goto(live_server_url)

    # Observable (bad path): error alert + retry button, no infinite loading.
    expect(page.get_by_test_id("home-config-error")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("home-config-retry")).to_be_visible()
    # The picker is NOT rendered while config failed.
    expect(page.get_by_test_id("source-picker-drop")).to_be_hidden()

    # Good path: stop failing the route, click Retry → real config loads.
    page.unroute(fail_route)
    page.get_by_test_id("home-config-retry").click()

    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("home-config-error")).to_be_hidden()
    # A picker renders once config resolves (local or managed mode).
    expect(page.get_by_test_id("source-picker-drop")).to_be_visible(timeout=10_000)

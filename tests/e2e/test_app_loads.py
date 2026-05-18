"""Playwright smoke test: app loads and home page is visible.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.
"""

from __future__ import annotations

import pytest

# Skip the whole module if playwright is not installed (e.g. in CI without --group e2e)
playwright = pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect  # noqa: E402


@pytest.mark.slow
@pytest.mark.e2e
def test_home_page_loads(page: Page, live_server_url: str) -> None:
    """Navigate to / and confirm the home page data-testid is visible."""
    console_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible()

    # No JS console errors should appear on initial load
    assert console_errors == [], f"Console errors on load: {console_errors}"

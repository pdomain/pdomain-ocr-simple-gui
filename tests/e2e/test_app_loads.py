"""Playwright smoke test: app loads and home page is visible.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.
"""

from __future__ import annotations

import pytest

# Skip the whole module if playwright is not installed (e.g. in CI without --group e2e)
pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_home_page_loads(page: Page, live_server_url: str) -> None:
    """Navigate to / and confirm the home page data-testid is visible within 10 s."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    assert not errors, f"JS errors on load: {errors}"

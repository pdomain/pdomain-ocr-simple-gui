"""5.12 — full click-path: results → page-view → zoom controls + word overlays.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

From the seeded job's ResultsPage:
1. Clicks the first page-row to open PageViewPage.
2. Asserts page-view-page is visible.
3. Exercises zoom-in / zoom-out / fit-screen buttons and asserts the
   data-zoom / data-auto-fit attributes change on the viewport element.
4. Exercises prev-page / next-page buttons (seeded job has 1 page, so
   both should remain disabled — we assert their disabled state).
5. Asserts word overlays render: the page-image-canvas wrapper reports
   data-word-count >= 1 (the seeded sidecar has 2 words).

Word-overlay approach: PageViewPage wraps ArtifactViewer (Konva) in a
plain <div data-testid="page-image-canvas" data-word-count="N"> so we
read the attribute without reaching into Konva internals.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_page_viewer_zoom_and_word_overlays(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Click a page-row, zoom in/out/fit, assert viewport state + word overlays."""
    # --- Navigate to ResultsPage for the seeded job ---
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    # --- Click the first page-row to open PageViewPage ---
    page_row = page.get_by_test_id("page-row").first
    expect(page_row).to_be_visible(timeout=10_000)
    page_row.click()

    # --- PageViewPage is now visible ---
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=10_000)

    # --- Word overlays: canvas wrapper reports >= 1 word ---
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    word_count = canvas.get_attribute("data-word-count")
    assert word_count is not None, "data-word-count attribute missing"
    assert int(word_count) >= 1, f"Expected >= 1 word overlay, got {word_count!r}"

    # --- Zoom-in: click + and assert data-zoom increased ---
    zoom_before_str = viewport.get_attribute("data-zoom")
    assert zoom_before_str is not None, "data-zoom attribute missing"
    zoom_before = float(zoom_before_str)

    zoom_in_btn = page.get_by_test_id("page-zoom-in")
    expect(zoom_in_btn).to_be_visible(timeout=5_000)
    zoom_in_btn.click()

    # Poll until data-zoom changes
    page.wait_for_function(
        f"""() => {{
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            if (!el) return false;
            return parseFloat(el.getAttribute('data-zoom') || '0') > {zoom_before};
        }}""",
        timeout=5_000,
    )
    zoom_after_in = float(viewport.get_attribute("data-zoom") or "0")
    assert zoom_after_in > zoom_before, (
        f"Zoom-in did not increase zoom: before={zoom_before}, after={zoom_after_in}"
    )

    # --- Zoom-out: click - and assert data-zoom decreased from current ---
    zoom_in_again_val = zoom_after_in
    zoom_out_btn = page.get_by_test_id("page-zoom-out")
    expect(zoom_out_btn).to_be_visible(timeout=5_000)
    zoom_out_btn.click()

    page.wait_for_function(
        f"""() => {{
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            if (!el) return false;
            return parseFloat(el.getAttribute('data-zoom') || '999') < {zoom_in_again_val};
        }}""",
        timeout=5_000,
    )
    zoom_after_out = float(viewport.get_attribute("data-zoom") or "0")
    assert zoom_after_out < zoom_in_again_val, (
        f"Zoom-out did not decrease zoom: before={zoom_in_again_val}, after={zoom_after_out}"
    )

    # --- Fit-screen: click Fit and assert data-auto-fit becomes "true" ---
    fit_btn = page.get_by_test_id("page-zoom-fit")
    expect(fit_btn).to_be_visible(timeout=5_000)
    fit_btn.click()

    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el?.getAttribute('data-auto-fit') === 'true';
        }""",
        timeout=5_000,
    )
    assert viewport.get_attribute("data-auto-fit") == "true", (
        "data-auto-fit should be 'true' after clicking Fit"
    )

    # --- Prev/next page: seeded job has 1 page so both buttons are disabled ---
    prev_btn = page.get_by_test_id("page-prev-button")
    next_btn = page.get_by_test_id("page-next-button")
    expect(prev_btn).to_be_visible(timeout=5_000)
    expect(next_btn).to_be_visible(timeout=5_000)
    expect(prev_btn).to_be_disabled()
    expect(next_btn).to_be_disabled()

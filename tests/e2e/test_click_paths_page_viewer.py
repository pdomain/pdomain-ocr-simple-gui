"""5.12 — full click-path: results → page-view → zoom controls + word overlays.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

From the seeded job's ResultsPage:
1. Clicks the first page-row to open PageViewPage.
2. Asserts page-view-page is visible.
3. Exercises zoom-in / zoom-out / fit-screen / 100% buttons and asserts the
   data-zoom / data-auto-fit attributes change on the viewport element.
4. Exercises prev-page / next-page buttons:
   - single-page job: both disabled (disabled-state assertion).
   - 2-page job: click NEXT → page index advances; click PREV → goes back.
5. Asserts word overlays render: the page-image-canvas wrapper reports
   data-word-count >= 1 (the seeded sidecar has 2 words).
6. Exercises Save text button: edits text in textarea, clicks Save, asserts
   success toast or status change (observable).
7. Exercises Re-run DocTR and Re-run Tesseract buttons: click each, assert
   observable effect (toast appears).

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

    # --- 100% zoom: click 100% and assert data-zoom becomes 1.0 ---
    # First zoom in to a non-1.0 state so 100% is meaningful.
    zoom_in_btn.click()
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el !== null && parseFloat(el.getAttribute('data-zoom') || '1') !== 1;
        }""",
        timeout=5_000,
    )

    zoom_100_btn = page.get_by_test_id("page-zoom-100")
    expect(zoom_100_btn).to_be_visible(timeout=5_000)
    zoom_100_btn.click()

    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            if (!el) return false;
            return parseFloat(el.getAttribute('data-zoom') || '0') === 1.0;
        }""",
        timeout=5_000,
    )
    zoom_at_100 = float(viewport.get_attribute("data-zoom") or "0")
    assert abs(zoom_at_100 - 1.0) < 0.001, f"Expected zoom=1.0 after clicking 100%, got {zoom_at_100}"

    # --- Prev/next page: seeded job has 1 page so both buttons are disabled ---
    prev_btn = page.get_by_test_id("page-prev-button")
    next_btn = page.get_by_test_id("page-next-button")
    expect(prev_btn).to_be_visible(timeout=5_000)
    expect(next_btn).to_be_visible(timeout=5_000)
    expect(prev_btn).to_be_disabled()
    expect(next_btn).to_be_disabled()


@pytest.mark.slow
@pytest.mark.e2e
def test_page_viewer_prev_next_navigation(page: Page, live_server_url: str, seeded_2page_job_id: str) -> None:
    """Multi-page job: click NEXT to advance page index, click PREV to go back.

    Requires a 2-page seeded job (seeded_2page_job_id fixture).
    Uses URL change as the observable effect: navigating to /pages/1 then /pages/0.
    """
    # --- Navigate directly to page 0 of the 2-page job ---
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Wait until page data loads (prev disabled on page 0, next enabled)
    prev_btn = page.get_by_test_id("page-prev-button")
    next_btn = page.get_by_test_id("page-next-button")
    expect(prev_btn).to_be_visible(timeout=10_000)
    expect(next_btn).to_be_visible(timeout=10_000)

    # On page 0: prev is disabled, next is enabled
    expect(prev_btn).to_be_disabled()
    expect(next_btn).not_to_be_disabled()

    # --- Click NEXT → URL advances to /pages/1 ---
    next_btn.click()

    page.wait_for_function(
        f"""() => window.location.href.includes('/jobs/{seeded_2page_job_id}/pages/1')""",
        timeout=5_000,
    )
    assert "/pages/1" in page.url, f"Expected URL to contain /pages/1 after next, got {page.url!r}"

    # On page 1 of 2: next is disabled, prev is enabled
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    prev_btn2 = page.get_by_test_id("page-prev-button")
    next_btn2 = page.get_by_test_id("page-next-button")
    expect(prev_btn2).to_be_visible(timeout=10_000)
    expect(next_btn2).to_be_visible(timeout=10_000)
    expect(next_btn2).to_be_disabled()
    expect(prev_btn2).not_to_be_disabled()

    # --- Click PREV → URL goes back to /pages/0 ---
    prev_btn2.click()

    page.wait_for_function(
        f"""() => window.location.href.includes('/jobs/{seeded_2page_job_id}/pages/0')""",
        timeout=5_000,
    )
    assert "/pages/0" in page.url, f"Expected URL to contain /pages/0 after prev, got {page.url!r}"


@pytest.mark.slow
@pytest.mark.e2e
def test_page_viewer_save_text(page: Page, live_server_url: str, seeded_rerun_job_id: str) -> None:
    """Edit text in textarea, click Save; assert success toast appears.

    Uses seeded_rerun_job_id (isolated from other tests) to avoid state
    corruption from the rerun tests.

    Observable effect: sonner toast with "Saved" appears in the DOM after PUT /api/pages/.../text.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Wait for page data to load (textarea enabled)
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_visible(timeout=10_000)
    expect(textarea).to_be_enabled(timeout=10_000)

    # Edit the text (select all + fill to replace content)
    textarea.click(click_count=3)
    textarea.fill("Edited by e2e test")

    # Click Save
    save_btn = page.get_by_test_id("page-save-button")
    expect(save_btn).to_be_visible(timeout=5_000)
    save_btn.click()

    # Assert success toast appears ("Saved" text in the sonner toaster)
    page.wait_for_function(
        """() => {
            const toasts = document.querySelectorAll('[data-sonner-toast]');
            return Array.from(toasts).some(
                t => t.textContent?.includes('Saved')
            );
        }""",
        timeout=8_000,
    )


@pytest.mark.slow
@pytest.mark.e2e
def test_page_viewer_rerun_doctr(page: Page, live_server_url: str, seeded_rerun_job_id: str) -> None:
    """Click Re-run DocTR; assert observable effect (success or failure toast appears).

    Uses seeded_rerun_job_id so the per-page rerun has an isolated job to mutate.
    The fake dispatcher implements per-page rerun via the pages route.
    A toast (success OR error) is the observable: the click reached the handler
    + the POST was attempted and the UI responded.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Wait for page data to load so buttons are enabled
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=10_000)

    rerun_doctr_btn = page.get_by_test_id("page-rerun-doctr")
    expect(rerun_doctr_btn).to_be_visible(timeout=5_000)
    expect(rerun_doctr_btn).to_be_enabled()
    rerun_doctr_btn.click()

    # Assert a sonner toast appears (success "Re-run complete" or error "Re-run failed")
    page.wait_for_function(
        """() => {
            const toasts = document.querySelectorAll('[data-sonner-toast]');
            return Array.from(toasts).some(
                t => t.textContent?.includes('Re-run')
            );
        }""",
        timeout=10_000,
    )


@pytest.mark.slow
@pytest.mark.e2e
def test_page_viewer_rerun_tesseract(page: Page, live_server_url: str, seeded_rerun_job_id: str) -> None:
    """Click Re-run Tesseract; assert observable effect (toast appears).

    Uses seeded_rerun_job_id so state mutations are isolated.
    Same pattern as DocTR — click triggers POST, UI toasts the outcome.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=10_000)

    rerun_tess_btn = page.get_by_test_id("page-rerun-tesseract")
    expect(rerun_tess_btn).to_be_visible(timeout=5_000)
    expect(rerun_tess_btn).to_be_enabled()
    rerun_tess_btn.click()

    page.wait_for_function(
        """() => {
            const toasts = document.querySelectorAll('[data-sonner-toast]');
            return Array.from(toasts).some(
                t => t.textContent?.includes('Re-run')
            );
        }""",
        timeout=10_000,
    )

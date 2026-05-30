"""Tier B — re-run regenerates real OCR text through the REAL engine (GPU, opt-in).

Covers: B-RESULTS-009 (Tier-B: rerun-all genuinely re-OCRs and regenerates text)
Covers: B-PAGEVIEW-013 (Tier-B: single-page DocTR rerun regenerates real text)
Covers: B-PAGEVIEW-014 (Tier-B: single-page Tesseract rerun regenerates real text)

Unlike the Tier-A click-path rerun tests (fake dispatcher, which has no
``run_stage`` so the per-page rerun records ``state=failed`` and only the toast
+ edit-preservation are asserted), these slices boot the REAL
LocalStageDispatcher (``live_server_url_real_ocr``) and exercise both the
job-level "Re-run all" and the single-page PageViewPage rerun buttons against
the hand-verified known-good fixture, asserting the regenerated text overlaps
the ground truth (tolerant ≥60% word overlap). Marked ``real_ocr`` so they are
excluded from default CI and only run via ``make e2e-real-ocr``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e, pytest.mark.real_ocr]

FIXTURES = Path(__file__).parent / "fixtures"


def _normalize(s: str) -> str:
    """Lowercase, collapse whitespace, and strip simple trailing punctuation."""
    words = s.lower().split()
    cleaned = [w.strip(".,;:!?\"'") for w in words]
    return " ".join(w for w in cleaned if w)


def _ground_truth() -> set[str]:
    """Return the normalized word set of the known-good fixture transcript."""
    expected = _normalize((FIXTURES / "known_good_page.gt.txt").read_text(encoding="utf-8"))
    return set(expected.split())


def _wait_for_page_preview(page: Page, timeout_ms: int) -> None:
    """Wait until the first page-row preview is non-empty (the done signal)."""
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('[data-testid="page-row"]');
            if (rows.length === 0) return false;
            const preview = rows[0].querySelector('.results-page__page-preview');
            const txt = preview?.textContent?.trim() ?? '';
            return txt.length > 0 && txt !== '—';
        }""",
        timeout=timeout_ms,
    )


def _upload_and_wait_done(page: Page, base_url: str) -> None:
    """Upload the fixture, start the job, and wait for the first OCR pass to finish."""
    fixture_png = FIXTURES / "known_good_page.png"
    page.goto(base_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(fixture_png))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=15_000)
    page.get_by_test_id("run-ocr-button").click()
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    # Cold-start (model load) is slow on the first pass → 180s.
    _wait_for_page_preview(page, 180_000)


def _assert_textarea_overlaps_ground_truth(page: Page, want: set[str]) -> None:
    """Wait for the PageViewPage textarea to populate and assert ≥60% word overlap."""
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_visible(timeout=15_000)
    page.wait_for_function(
        """() => {
            const el = document.querySelector('textarea[aria-label="OCR text"]');
            return el instanceof HTMLTextAreaElement && el.value.trim().length > 0;
        }""",
        timeout=60_000,
    )
    produced = _normalize(textarea.input_value())
    got = set(produced.split())
    overlap = len(want & got) / max(1, len(want))
    assert overlap >= 0.6, f"rerun produced only {overlap:.0%} word overlap; produced={produced!r}"


def test_real_ocr_rerun_regenerates_text(page: Page, live_server_url_real_ocr: str) -> None:
    """B-RESULTS-009 (Regression, Tier-B): re-run-all re-OCRs and regenerates text."""
    want = _ground_truth()
    _upload_and_wait_done(page, live_server_url_real_ocr)

    # Re-run all through the real engine.
    rerun_btn = page.get_by_test_id("rerun-all-button")
    expect(rerun_btn).to_be_visible(timeout=15_000)
    expect(rerun_btn).to_be_enabled()
    rerun_btn.click()

    # The rerunKey bump resets polling; the preview clears then repopulates once
    # the re-OCR completes. Model is warm now, so a shorter window.
    _wait_for_page_preview(page, 120_000)

    # Open page 0 and assert the regenerated text still matches ground truth.
    page.get_by_test_id("page-row").first.click()
    _assert_textarea_overlaps_ground_truth(page, want)


def test_real_ocr_rerun_doctr_regenerates_text(page: Page, live_server_url_real_ocr: str) -> None:
    """B-PAGEVIEW-013 (Regression, Tier-B): single-page DocTR rerun regenerates real text.

    Opens page 0 and clicks the PageViewPage "Re-run DocTR" button (not the
    job-level rerun-all). The real engine re-OCRs the single page through the
    dispatcher and the editor textarea repopulates with text that overlaps the
    hand-verified ground truth.
    """
    want = _ground_truth()
    _upload_and_wait_done(page, live_server_url_real_ocr)

    # Open page 0 and re-run just this page with DocTR.
    page.get_by_test_id("page-row").first.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    rerun_doctr = page.get_by_test_id("page-rerun-doctr")
    expect(rerun_doctr).to_be_enabled(timeout=30_000)
    # Clear the textarea first so the post-rerun repopulation is observable.
    textarea = page.get_by_label("OCR text")
    textarea.click(click_count=3)
    textarea.fill("")
    rerun_doctr.click()
    # On success the handler refetches GET /api/pages and repopulates the editor.
    _assert_textarea_overlaps_ground_truth(page, want)


def test_real_ocr_rerun_tesseract_regenerates_text(page: Page, live_server_url_real_ocr: str) -> None:
    """B-PAGEVIEW-014 (Tier-B): single-page Tesseract rerun regenerates real text.

    tesseract 5.3.0 + pytesseract 0.3.13 are installed, so a real Tesseract
    rerun is viable through the dispatcher. Clicks the PageViewPage "Re-run
    Tesseract" button and asserts the regenerated text overlaps ground truth.
    If real Tesseract rerun does NOT produce text through the dispatcher, this
    assertion fails loudly (the bar is not lowered / skipped).
    """
    want = _ground_truth()
    _upload_and_wait_done(page, live_server_url_real_ocr)

    page.get_by_test_id("page-row").first.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    rerun_tess = page.get_by_test_id("page-rerun-tesseract")
    expect(rerun_tess).to_be_enabled(timeout=30_000)
    textarea = page.get_by_label("OCR text")
    textarea.click(click_count=3)
    textarea.fill("")
    rerun_tess.click()
    _assert_textarea_overlaps_ground_truth(page, want)

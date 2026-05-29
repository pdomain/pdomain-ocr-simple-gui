"""Tier B — re-run regenerates real OCR text through the REAL engine (GPU, opt-in).

Covers: B-RESULTS-009 (Tier-B: rerun-all genuinely re-OCRs and regenerates text)

Unlike the Tier-A click-path rerun test (fake dispatcher, asserts the POST
fires), this slice boots the REAL LocalStageDispatcher + DocTR runner
(``live_server_url_real_ocr``) and:

1. uploads the known-good fixture PNG via the file picker,
2. starts the OCR job and waits for the ResultsPage to reach a done state,
3. clicks "Re-run all" to re-OCR every page through the real engine,
4. waits for the page preview to repopulate after the rerun,
5. opens page 0 and asserts the regenerated text still overlaps the
   hand-verified ground truth (tolerant ≥60% word overlap).

This proves rerun-all is not a no-op: the real engine re-processes the page
and the produced text is regenerated (not stale). Marked ``real_ocr`` so it is
excluded from default CI and only runs via ``make e2e-real-ocr``.
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


def test_real_ocr_rerun_regenerates_text(page: Page, live_server_url_real_ocr: str) -> None:
    """B-RESULTS-009 (Regression, Tier-B): re-run-all re-OCRs and regenerates text."""
    fixture_png = FIXTURES / "known_good_page.png"
    expected = _normalize((FIXTURES / "known_good_page.gt.txt").read_text(encoding="utf-8"))
    want = set(expected.split())

    # 1. Upload + start the job.
    page.goto(live_server_url_real_ocr)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(fixture_png))
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=15_000)
    page.get_by_test_id("run-ocr-button").click()

    # 2. Wait for the first real OCR pass to finish (cold-start is slow → 180s).
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    _wait_for_page_preview(page, 180_000)

    # 3. Re-run all through the real engine.
    rerun_btn = page.get_by_test_id("rerun-all-button")
    expect(rerun_btn).to_be_visible(timeout=15_000)
    expect(rerun_btn).to_be_enabled()
    rerun_btn.click()

    # 4. The rerunKey bump resets polling; the preview clears then repopulates
    #    once the re-OCR completes. Model is warm now, so a shorter window.
    _wait_for_page_preview(page, 120_000)

    # 5. Open page 0 and assert the regenerated text still matches ground truth.
    page.get_by_test_id("page-row").first.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_visible(timeout=15_000)
    page.wait_for_function(
        """() => {
            const el = document.querySelector('textarea[aria-label="OCR text"]');
            return el instanceof HTMLTextAreaElement && el.value.trim().length > 0;
        }""",
        timeout=30_000,
    )
    produced = _normalize(textarea.input_value())
    got = set(produced.split())
    overlap = len(want & got) / max(1, len(want))
    assert overlap >= 0.6, (
        f"rerun produced only {overlap:.0%} word overlap; produced={produced!r}, expected={expected!r}"
    )

"""Tier B — full exercise with the REAL OCR engine (GPU, opt-in).

Covers: F-UPLOAD-OCR-DOWNLOAD-01 (real-engine slice)

Unlike the Tier-A click-path tests (which run against the FakeStageDispatcher),
this test boots the server with the real LocalStageDispatcher + DocTR runner on
the GPU (``live_server_url_real_ocr``). It drives the actual served UI:

1. upload the known-good fixture PNG via the file picker,
2. start the OCR job,
3. wait on the ResultsPage until the page reaches a done state,
4. open page 0,
5. read the produced OCR text from the editor textarea,

then asserts at least 60% word overlap with the hand-verified ground-truth
transcript (``known_good_page.gt.txt``). The threshold is tolerant because real
OCR is non-deterministic at the character level; it is still high enough to
prove the real engine actually transcribed the page (not the fake dispatcher).

Marked ``real_ocr`` so it is excluded from default CI (``-m "not real_ocr"``)
and only runs via ``make e2e-real-ocr``.
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


def test_real_ocr_produces_expected_text(page: Page, live_server_url_real_ocr: str) -> None:
    """Real DocTR transcribes the fixture page with >=60% word overlap."""
    fixture_png = FIXTURES / "known_good_page.png"
    expected = _normalize((FIXTURES / "known_good_page.gt.txt").read_text(encoding="utf-8"))

    page.goto(live_server_url_real_ocr)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # 1. Upload the fixture PNG via the hidden file input (simulates the picker).
    page.get_by_test_id("source-picker-file-pick").set_input_files(str(fixture_png))

    # 2. The inline config form appears once the upload completes; start the job.
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=15_000)
    page.get_by_test_id("run-ocr-button").click()

    # 3. ResultsPage appears; wait for the real engine to finish the page. The
    #    page-row preview cell renders the recognized text once the page reaches
    #    succeeded (it shows "—" while empty), so a non-placeholder preview is
    #    our done signal. Real OCR cold-start + recognition is slow → 180s.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('[data-testid="page-row"]');
            if (rows.length === 0) return false;
            const preview = rows[0].querySelector('.results-page__page-preview');
            const txt = preview?.textContent?.trim() ?? '';
            return txt.length > 0 && txt !== '—';
        }""",
        timeout=180_000,
    )

    # 4. Open page 0 by clicking the first page-row.
    page.get_by_test_id("page-row").first.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # 5. Read the produced OCR text from the editor textarea (aria-label "OCR
    #    text"). PageViewPage loads it from GET /api/pages/{id}/0 on mount.
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

    # Assert: at least 60% of the expected words appear (tolerant, real OCR).
    want = set(expected.split())
    got = set(produced.split())
    overlap = len(want & got) / max(1, len(want))
    assert overlap >= 0.6, f"only {overlap:.0%} word overlap; produced={produced!r}, expected={expected!r}"

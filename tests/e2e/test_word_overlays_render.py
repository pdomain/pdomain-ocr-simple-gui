"""B5.5 — word overlays render on PageViewPage.

Navigate to /jobs/<seeded_job_id>/pages/0 and confirm:
- the page-image-canvas wrapper is visible
- data-word-count >= 1 (the seeded sidecar has 2 words)

The ``page-image-canvas`` testid is on a *wrapper* div, not the Konva
canvas itself — PageViewPage wraps PageImageCanvas in a div that carries
both ``data-testid`` and ``data-word-count`` so these are observable
without reaching into Konva internals.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="playwright not installed; run: uv sync --group e2e")

from playwright.sync_api import Page, expect


@pytest.mark.slow
@pytest.mark.e2e
def test_word_overlay_count(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """page-image-canvas wrapper is visible and reports at least 1 word."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    word_count_attr = canvas.get_attribute("data-word-count")
    assert word_count_attr is not None, "data-word-count attribute missing on page-image-canvas"
    assert int(word_count_attr) >= 1, f"Expected >= 1 word, got data-word-count={word_count_attr!r}"

"""Tier-A behavior tests for PageViewPage (`/jobs/:id/pages/:idx`).

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-fast`` / ``make e2e-browser``.

Every test cites its behavior record (``Covers: B-PAGEVIEW-NNN``), asserts the
observable output via a real selector (the textarea has NO testid → selected by
``get_by_label("OCR text")``; zoom state via ``page-zoom-viewport``
``data-zoom`` / ``data-auto-fit``; overlays via ``page-image-canvas``
``data-word-count``), and where there is a backend effect re-queries the API AND
inspects on-disk artifacts under ``e2e_data_root`` (save → sidecar
``pages/<name>.json`` ``edited_text`` + per-page ``.txt``; rerun → edited_text
PRESERVED). Each record has a good path and at least one bad path.

The fake dispatcher backs the live server, so OCR output is deterministic. NOTE
on rerun under Tier A: the fake dispatcher has no ``run_stage`` method, so the
single-page rerun records ``state="failed"`` internally and returns 200 (the UI
toasts "Re-run complete" on any 2xx). The genuine real-text-regeneration +
edit-preservation is the Tier-B slice in ``test_real_ocr_rerun.py``; here we
assert the click-path observable AND that a rerun never clobbers a saved edit.

Seeded sidecar/txt filenames derive from the page_name (``page-001``), so the
canonical artifacts are ``projects/<id>/pages/page-001.json`` + ``.txt``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


def _toast_with(page: Page, fragment: str, timeout_ms: int = 8_000) -> None:
    """Wait until a sonner toast containing *fragment* is in the DOM."""
    page.wait_for_function(
        """(frag) => {
            const toasts = document.querySelectorAll('[data-sonner-toast]');
            return Array.from(toasts).some(t => t.textContent?.includes(frag));
        }""",
        arg=fragment,
        timeout=timeout_ms,
    )


# ---------------------------------------------------------------------------
# B-PAGEVIEW-001 — Page view loads (image canvas + editor + nav toolbar)
# ---------------------------------------------------------------------------


def test_page_view_loads_canvas_editor_and_indicator(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-001 — page renders canvas + editor + page indicator."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Observable: the canvas wrapper and the OCR-text editor both render.
    expect(page.get_by_test_id("page-image-canvas")).to_be_visible(timeout=15_000)
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_visible(timeout=10_000)
    expect(textarea).to_be_enabled(timeout=10_000)
    # Observable: the nav toolbar shows the "<name> (n / total)" indicator.
    expect(page.get_by_text("page-001 (1 / 1)")).to_be_visible(timeout=10_000)

    # Backend effect: the page fetch returns 200 with the page metadata.
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_job_id}/0", timeout=10.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body["page_idx"] == 0
    assert body["page_name"] == "page-001"

    # On-disk: the canonical project + page sidecar exist.
    assert (e2e_data_root / "projects" / seeded_job_id / "project.json").exists()
    assert (e2e_data_root / "projects" / seeded_job_id / "pages" / "page-001.json").exists()


def test_page_view_malformed_id_does_not_crash(page: Page, live_server_url: str) -> None:
    """Covers: B-PAGEVIEW-001 (bad path) — a malformed project id 400s on the API.

    A single-segment id containing a banned character (a dot) trips
    validate_project_id at the API boundary and returns 400, not a 500 crash.
    """
    resp = httpx.get(f"{live_server_url}/api/pages/bad.id/0", timeout=10.0)
    assert resp.status_code == 400
    _ = page  # API-level assertion; page fixture kept for parity


# ---------------------------------------------------------------------------
# B-PAGEVIEW-002 — Word overlays render from the sidecar
# ---------------------------------------------------------------------------


def test_word_overlays_render_from_sidecar(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-002 — the canvas reports data-word-count >= 1."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    word_count = canvas.get_attribute("data-word-count")
    assert word_count is not None
    assert int(word_count) >= 1, f"expected >= 1 word overlay, got {word_count!r}"

    # Backend effect: the words endpoint returns the normalized word list.
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_job_id}/0/words", timeout=10.0)
    assert resp.status_code == 200
    words = resp.json()["words"]
    assert len(words) >= 1
    assert "bbox" in words[0]


def test_word_overlays_empty_when_words_404(page: Page, live_server_url: str) -> None:
    """Covers: B-PAGEVIEW-002 (bad path) — a 404 words fetch degrades to count 0.

    Intercept only the /words call → 404 so the overlay fetch fails while the
    page itself still loads. The canvas renders with data-word-count="0" (the
    overlay is non-critical and silently degrades).
    """
    project_id = "e2enowords-" + uuid.uuid4().hex[:12]
    words_route = f"**/api/pages/{project_id}/0/words"
    page.route(words_route, lambda route: route.fulfill(status=404, body='{"detail":"page not found"}'))
    # Fulfil the page + job fetches so the canvas renders.
    page.route(
        f"**/api/pages/{project_id}/0",
        lambda route: route.fulfill(
            status=200,
            body=json.dumps(
                {
                    "page_idx": 0,
                    "page_name": "p",
                    "state": "succeeded",
                    "text": "hi",
                    "width": 800,
                    "height": 1200,
                }
            ),
        ),
    )
    page.route(
        f"**/api/jobs/{project_id}",
        lambda route: route.fulfill(
            status=200,
            body=json.dumps({"project_id": project_id, "name": "n", "state": "succeeded", "page_count": 1}),
        ),
    )
    page.goto(f"{live_server_url}/jobs/{project_id}/pages/0")
    canvas = page.get_by_test_id("page-image-canvas")
    expect(canvas).to_be_visible(timeout=15_000)
    assert canvas.get_attribute("data-word-count") == "0"
    page.unroute(words_route)


# ---------------------------------------------------------------------------
# B-PAGEVIEW-003 / 004 / 005 / 006 / 007 — Zoom controls
# ---------------------------------------------------------------------------


def test_zoom_in_increases_zoom_and_disables_auto_fit(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-003 — zoom-in raises data-zoom and clears auto-fit."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    before = float(viewport.get_attribute("data-zoom") or "0")
    page.get_by_test_id("page-zoom-in").click()
    page.wait_for_function(
        f"""() => {{
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el && parseFloat(el.getAttribute('data-zoom') || '0') > {before}
                && el.getAttribute('data-auto-fit') === 'false';
        }}""",
        timeout=5_000,
    )
    after = float(viewport.get_attribute("data-zoom") or "0")
    assert after > before
    # No backend effect — zoom is a client-only CSS transform.


def test_zoom_in_clamps_at_ceiling(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-003 (bad path) — zoom never exceeds the 4.0 ceiling."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    zoom_in = page.get_by_test_id("page-zoom-in")
    for _ in range(20):  # spam well past the 4.0 ceiling
        zoom_in.click()
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el && parseFloat(el.getAttribute('data-zoom') || '0') >= 3.9;
        }""",
        timeout=5_000,
    )
    assert float(viewport.get_attribute("data-zoom") or "0") <= 4.0001


def test_zoom_out_decreases_zoom(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-004 — zoom-out lowers data-zoom and clears auto-fit."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    # Zoom in first so there is room to go down.
    page.get_by_test_id("page-zoom-in").click()
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el && el.getAttribute('data-auto-fit') === 'false';
        }""",
        timeout=5_000,
    )
    mid = float(viewport.get_attribute("data-zoom") or "0")
    page.get_by_test_id("page-zoom-out").click()
    page.wait_for_function(
        f"""() => {{
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el && parseFloat(el.getAttribute('data-zoom') || '999') < {mid};
        }}""",
        timeout=5_000,
    )
    assert float(viewport.get_attribute("data-zoom") or "0") < mid


def test_zoom_out_clamps_at_floor(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-004 (bad path) — zoom never drops below the 0.1 floor."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    zoom_out = page.get_by_test_id("page-zoom-out")
    for _ in range(40):
        zoom_out.click()
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el && parseFloat(el.getAttribute('data-zoom') || '9') <= 0.2;
        }""",
        timeout=5_000,
    )
    assert float(viewport.get_attribute("data-zoom") or "0") >= 0.0999


def test_fit_engages_auto_fit(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-005 — Fit sets data-auto-fit to 'true'."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    # Break auto-fit first.
    page.get_by_test_id("page-zoom-in").click()
    page.wait_for_function(
        """() => document.querySelector('[data-testid="page-zoom-viewport"]')
                 ?.getAttribute('data-auto-fit') === 'false'""",
        timeout=5_000,
    )
    page.get_by_test_id("page-zoom-fit").click()
    page.wait_for_function(
        """() => document.querySelector('[data-testid="page-zoom-viewport"]')
                 ?.getAttribute('data-auto-fit') === 'true'""",
        timeout=5_000,
    )
    assert viewport.get_attribute("data-auto-fit") == "true"


def test_fit_is_bad_path_safe_with_no_prior_zoom(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-005 (bad path) — Fit before any manual zoom is a no-op-safe."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    page.get_by_test_id("page-zoom-fit").click()
    # Still auto-fit, still a finite positive zoom (no crash / NaN).
    assert viewport.get_attribute("data-auto-fit") == "true"
    assert float(viewport.get_attribute("data-zoom") or "0") > 0


def test_reset_100_sets_zoom_to_one(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-006 — 100% sets data-zoom to exactly 1.0, auto-fit false."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    page.get_by_test_id("page-zoom-in").click()  # leave the default fit
    page.get_by_test_id("page-zoom-100").click()
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="page-zoom-viewport"]');
            return el && parseFloat(el.getAttribute('data-zoom') || '0') === 1.0
                && el.getAttribute('data-auto-fit') === 'false';
        }""",
        timeout=5_000,
    )
    assert abs(float(viewport.get_attribute("data-zoom") or "0") - 1.0) < 0.001


def test_reset_100_is_idempotent(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-006 (bad path) — clicking 100% twice stays at 1.0."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    page.get_by_test_id("page-zoom-100").click()
    page.get_by_test_id("page-zoom-100").click()
    page.wait_for_function(
        """() => parseFloat(
            document.querySelector('[data-testid="page-zoom-viewport"]')
                ?.getAttribute('data-zoom') || '0') === 1.0""",
        timeout=5_000,
    )
    assert abs(float(viewport.get_attribute("data-zoom") or "0") - 1.0) < 0.001


def test_default_auto_fit_on_load(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-007 — the viewport starts in auto-fit on first load."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    assert viewport.get_attribute("data-auto-fit") == "true"


def test_zoom_resets_to_auto_fit_on_navigation(
    page: Page, live_server_url: str, seeded_2page_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-007 (bad path) — zoom is NOT persisted across page nav.

    Manually zoom on page 0 (auto-fit false), navigate to page 1, and assert the
    remounted viewport is back in auto-fit (zoom state does not carry over).
    """
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}/pages/0")
    viewport = page.get_by_test_id("page-zoom-viewport")
    expect(viewport).to_be_visible(timeout=15_000)
    page.get_by_test_id("page-zoom-in").click()
    page.wait_for_function(
        """() => document.querySelector('[data-testid="page-zoom-viewport"]')
                 ?.getAttribute('data-auto-fit') === 'false'""",
        timeout=5_000,
    )
    page.get_by_test_id("page-next-button").click()
    page.wait_for_function(
        f"""() => window.location.href.includes('/jobs/{seeded_2page_job_id}/pages/1')""",
        timeout=5_000,
    )
    # New page remounts the viewport at auto-fit.
    page.wait_for_function(
        """() => document.querySelector('[data-testid="page-zoom-viewport"]')
                 ?.getAttribute('data-auto-fit') === 'true'""",
        timeout=10_000,
    )
    assert page.get_by_test_id("page-zoom-viewport").get_attribute("data-auto-fit") == "true"


# ---------------------------------------------------------------------------
# B-PAGEVIEW-008 / 009 — Page navigation
# ---------------------------------------------------------------------------


def test_next_page_navigates_and_refetches(
    page: Page, live_server_url: str, seeded_2page_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-008 — Next advances the route + refetches the new page."""
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    next_btn = page.get_by_test_id("page-next-button")
    expect(next_btn).to_be_enabled(timeout=10_000)
    next_btn.click()
    page.wait_for_function(
        f"""() => window.location.href.includes('/jobs/{seeded_2page_job_id}/pages/1')""",
        timeout=5_000,
    )
    assert "/pages/1" in page.url
    # Observable: the indicator updates to page 2 of 2.
    expect(page.get_by_text("page-002 (2 / 2)")).to_be_visible(timeout=10_000)

    # Backend effect: page 1 metadata is fetchable.
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_2page_job_id}/1", timeout=10.0)
    assert resp.status_code == 200
    assert resp.json()["page_name"] == "page-002"


def test_next_disabled_on_last_page(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-008 (bad path) — Next is disabled on the only/last page."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("page-next-button")).to_be_disabled()


def test_prev_page_navigates_back(page: Page, live_server_url: str, seeded_2page_job_id: str) -> None:
    """Covers: B-PAGEVIEW-009 — Prev returns the route to the previous index."""
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}/pages/1")
    prev_btn = page.get_by_test_id("page-prev-button")
    expect(prev_btn).to_be_visible(timeout=15_000)
    expect(prev_btn).to_be_enabled(timeout=10_000)
    prev_btn.click()
    page.wait_for_function(
        f"""() => window.location.href.includes('/jobs/{seeded_2page_job_id}/pages/0')""",
        timeout=5_000,
    )
    assert "/pages/0" in page.url


def test_prev_disabled_on_first_page(page: Page, live_server_url: str, seeded_2page_job_id: str) -> None:
    """Covers: B-PAGEVIEW-009 (bad path) — Prev is disabled on page 0."""
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("page-prev-button")).to_be_disabled()


# ---------------------------------------------------------------------------
# B-PAGEVIEW-010 / 011 — Save edited text (button + mod+s)
# ---------------------------------------------------------------------------


def test_save_button_persists_edit_to_sidecar_and_txt(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-010 — Save persists edited_text to the sidecar + per-page .txt."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=15_000)
    new_text = "corrected by B-PAGEVIEW-010"
    textarea.click(click_count=3)
    textarea.fill(new_text)
    page.get_by_test_id("page-save-button").click()

    # Observable: the "Saved" toast appears.
    _toast_with(page, "Saved")

    # Backend effect: GET returns the edited text (edited_text wins).
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_job_id}/0", timeout=10.0)
    assert resp.status_code == 200
    assert resp.json()["text"] == new_text

    # On-disk: the sidecar carries edited_text AND the per-page .txt is rewritten.
    pages_dir = e2e_data_root / "projects" / seeded_job_id / "pages"
    sidecar = json.loads((pages_dir / "page-001.json").read_text())
    assert sidecar["edited_text"] == new_text
    assert (pages_dir / "page-001.txt").read_text() == new_text


def test_save_bad_index_returns_404_no_write(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-010 (bad path) — saving an out-of-range index 404s, no write.

    See also B-PAGEVIEW-012 — this is the same guard, asserted at the API layer
    (the UI never lets you reach an out-of-range index from a valid job).
    """
    resp = httpx.put(
        f"{live_server_url}/api/pages/{seeded_job_id}/9999/text",
        json={"text": "must not persist"},
        timeout=10.0,
    )
    assert resp.status_code == 404
    pages_dir = e2e_data_root / "projects" / seeded_job_id / "pages"
    if pages_dir.exists():
        assert not list(pages_dir.glob("*9999*")), "out-of-range save wrote a stray artifact"
    _ = page


def test_save_via_mod_s_persists_edit(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_2page_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-011 — mod+s saves (browser save dialog suppressed).

    Uses page 1 of the 2-page job so this save is isolated from the page-0
    button-save test's artifacts.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_2page_job_id}/pages/1")
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=15_000)
    new_text = "saved via keyboard B-PAGEVIEW-011"
    textarea.click(click_count=3)
    textarea.fill(new_text)
    # The shortcut handler intercepts mod+s; the native dialog never opens.
    page.keyboard.press("Control+s")

    _toast_with(page, "Saved")

    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_2page_job_id}/1", timeout=10.0)
    assert resp.status_code == 200
    assert resp.json()["text"] == new_text

    sidecar = json.loads(
        (e2e_data_root / "projects" / seeded_2page_job_id / "pages" / "page-002.json").read_text()
    )
    assert sidecar["edited_text"] == new_text


def test_save_failure_toasts_save_failed(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-011 (bad path) — a non-ok save toasts 'Save failed'.

    Intercept the PUT → 500 so the client save path fails; the editor stays put.
    """
    save_route = f"**/api/pages/{seeded_job_id}/0/text"
    page.route(save_route, lambda route: route.fulfill(status=500, body="boom"))
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=15_000)
    textarea.click(click_count=3)
    textarea.fill("will fail")
    page.get_by_test_id("page-save-button").click()
    _toast_with(page, "Save failed")
    page.unroute(save_route)


# ---------------------------------------------------------------------------
# B-PAGEVIEW-012 — Save bad-state (out-of-range index → clean 404)  [Regression]
# ---------------------------------------------------------------------------


def test_out_of_range_save_is_clean_404(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-012 (Regression) — out-of-range save → 404, not 500, no write.

    Regression fixed in commit 0adf03e: put_page_text now resolves the page
    index against the project's pages list and returns a clean 404 before any
    disk mutation (previously an uncaught FileNotFoundError surfaced as 500).
    """
    resp = httpx.put(
        f"{live_server_url}/api/pages/{seeded_job_id}/4242/text",
        json={"text": "x"},
        timeout=10.0,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
    # No stray sidecar/txt for the bad index.
    pages_dir = e2e_data_root / "projects" / seeded_job_id / "pages"
    if pages_dir.exists():
        assert not list(pages_dir.glob("*4242*"))
    _ = page


def test_save_missing_project_returns_404(page: Page, live_server_url: str) -> None:
    """Covers: B-PAGEVIEW-012 (bad path) — saving to an unknown project 404s."""
    resp = httpx.put(
        f"{live_server_url}/api/pages/ghost-{uuid.uuid4().hex[:8]}/0/text",
        json={"text": "x"},
        timeout=10.0,
    )
    assert resp.status_code == 404
    _ = page


# ---------------------------------------------------------------------------
# B-PAGEVIEW-013 — Re-run single page (DocTR)  [Regression: preserves edit]
# ---------------------------------------------------------------------------


def test_rerun_doctr_toasts_and_preserves_saved_edit(
    page: Page, live_server_url: str, e2e_data_root: Path, seeded_rerun_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-013 (Regression) — a rerun never clobbers a saved edit.

    Regression fixed in commit d0edd9d: rerun_page now carries edited_text over
    from the prior sidecar. Tier A asserts the observable rerun toast AND that
    the user's saved edit survives the rerun on disk + via the API. (The genuine
    real-text regeneration is the Tier-B slice in test_real_ocr_rerun.py, which
    also cites B-PAGEVIEW-013.)
    """
    # 1. Save an edit first.
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}/pages/0")
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=15_000)
    edit = "hand edit that must survive a rerun"
    textarea.click(click_count=3)
    textarea.fill(edit)
    page.get_by_test_id("page-save-button").click()
    _toast_with(page, "Saved")

    # 2. Re-run DocTR (observable: a "Re-run" toast appears on the 2xx).
    rerun_btn = page.get_by_test_id("page-rerun-doctr")
    expect(rerun_btn).to_be_enabled(timeout=10_000)
    rerun_btn.click()
    _toast_with(page, "Re-run", timeout_ms=10_000)

    # 3. Backend effect: the edit is preserved (GET returns it; sidecar keeps it).
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_rerun_job_id}/0", timeout=10.0)
    assert resp.status_code == 200
    assert resp.json()["text"] == edit
    sidecar = json.loads(
        (e2e_data_root / "projects" / seeded_rerun_job_id / "pages" / "page-001.json").read_text()
    )
    assert sidecar["edited_text"] == edit


def test_rerun_doctr_missing_project_404(page: Page, live_server_url: str) -> None:
    """Covers: B-PAGEVIEW-013 (bad path) — rerun on an unknown project 404s."""
    resp = httpx.post(
        f"{live_server_url}/api/pages/ghost-{uuid.uuid4().hex[:8]}/0/rerun",
        json={"engine": "doctr"},
        timeout=10.0,
    )
    assert resp.status_code == 404
    _ = page


# ---------------------------------------------------------------------------
# B-PAGEVIEW-014 — Re-run single page (Tesseract)
# ---------------------------------------------------------------------------


def test_rerun_tesseract_toasts(page: Page, live_server_url: str, seeded_rerun_job_id: str) -> None:
    """Covers: B-PAGEVIEW-014 — clicking Re-run Tesseract triggers the POST + toast."""
    page.goto(f"{live_server_url}/jobs/{seeded_rerun_job_id}/pages/0")
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=15_000)
    rerun_tess = page.get_by_test_id("page-rerun-tesseract")
    expect(rerun_tess).to_be_enabled(timeout=10_000)
    rerun_tess.click()
    _toast_with(page, "Re-run", timeout_ms=10_000)


def test_rerun_tesseract_out_of_range_404(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-014 (bad path) — rerun on an out-of-range index 404s."""
    resp = httpx.post(
        f"{live_server_url}/api/pages/{seeded_job_id}/777/rerun",
        json={"engine": "tesseract"},
        timeout=10.0,
    )
    assert resp.status_code == 404
    _ = page


# ---------------------------------------------------------------------------
# B-PAGEVIEW-015 — Page-fetch failure surfaces a not-found / error block [Regression]
# ---------------------------------------------------------------------------


def test_page_fetch_404_shows_not_found_block(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-PAGEVIEW-015 (Regression) — a 404 page fetch shows page-not-found.

    Regression fixed in commit f9b8621: a failed page fetch used to leave the
    screen stuck loading on a blank shell. An out-of-range index (valid project,
    bad page) now surfaces the dedicated page-not-found block and renders no
    canvas.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/9999")
    nf = page.get_by_test_id("page-not-found")
    expect(nf).to_be_visible(timeout=15_000)
    expect(nf).to_contain_text("Page not found")
    expect(page.get_by_test_id("page-image-canvas")).to_have_count(0)
    expect(page.get_by_test_id("page-error")).to_have_count(0)

    # Backend effect: the page fetch genuinely 404s.
    resp = httpx.get(f"{live_server_url}/api/pages/{seeded_job_id}/9999", timeout=10.0)
    assert resp.status_code == 404


def test_page_fetch_error_shows_error_block(page: Page, live_server_url: str) -> None:
    """Covers: B-PAGEVIEW-015 (bad path) — a non-404 page fetch shows page-error.

    Intercept the page fetch → 500 so the client takes the generic-error branch
    (distinct from the 404 not-found block), rendering no canvas.
    """
    project_id = "e2eerr-" + uuid.uuid4().hex[:12]
    page_route = f"**/api/pages/{project_id}/0"
    page.route(page_route, lambda route: route.fulfill(status=500, body="boom"))
    page.route(
        f"**/api/jobs/{project_id}",
        lambda route: route.fulfill(
            status=200,
            body=json.dumps({"project_id": project_id, "name": "n", "state": "succeeded", "page_count": 1}),
        ),
    )
    page.goto(f"{live_server_url}/jobs/{project_id}/pages/0")
    err = page.get_by_test_id("page-error")
    expect(err).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("page-not-found")).to_have_count(0)
    expect(page.get_by_test_id("page-image-canvas")).to_have_count(0)
    page.unroute(page_route)


# ---------------------------------------------------------------------------
# B-PAGEVIEW-016 — Download from the page (txt / json / zip)
# ---------------------------------------------------------------------------


def test_page_download_triggers_job_zip(page: Page, live_server_url: str, seeded_managed_job_id: str) -> None:
    """Covers: B-PAGEVIEW-016 — a per-page download button triggers the job ZIP.

    The per-page buttons hit the job-level GET /api/jobs/{id}/download?include=…
    (same contract as B-RESULTS-006/007 + the download-model stub at
    docs/specs/2026-05-29-download-model.md). We assert the click triggers the
    download (Playwright download event) rather than re-asserting ZIP membership.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=15_000)
    with page.expect_download(timeout=10_000) as dl_info:
        page.get_by_test_id("page-download-text").click()
    download = dl_info.value
    assert download.url.endswith("/download?include=text")

    # Backend effect: the underlying job-level download endpoint serves a ZIP.
    resp = httpx.get(
        f"{live_server_url}/api/jobs/{seeded_managed_job_id}/download?include=text", timeout=10.0
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # ZIP magic


def test_page_download_unknown_token_400(
    page: Page, live_server_url: str, seeded_managed_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-016 (bad path) — an unknown include token 400s on the API."""
    resp = httpx.get(
        f"{live_server_url}/api/jobs/{seeded_managed_job_id}/download?include=bogus", timeout=10.0
    )
    assert resp.status_code == 400
    _ = page


# ---------------------------------------------------------------------------
# B-PAGEVIEW-017 — Job-progress message while a job is still running
# ---------------------------------------------------------------------------


def test_progress_message_renders_for_running_job(page: Page, live_server_url: str) -> None:
    """Covers: B-PAGEVIEW-017 — a running job with a message renders it in the toolbar.

    Intercept the single job fetch (PageViewPage does NOT poll) so the job is
    held in a running state carrying a progress_message; the page fetch is also
    fulfilled so the editor renders.
    """
    project_id = "e2epvprog-" + uuid.uuid4().hex[:12]
    msg = "Loading OCR engine — first run may download ~200 MB…"
    page.route(
        f"**/api/jobs/{project_id}",
        lambda route: route.fulfill(
            status=200,
            body=json.dumps(
                {
                    "project_id": project_id,
                    "name": "running",
                    "state": "running",
                    "page_count": 1,
                    "progress_message": msg,
                }
            ),
        ),
    )
    page.route(
        f"**/api/pages/{project_id}/0",
        lambda route: route.fulfill(
            status=200,
            body=json.dumps(
                {
                    "page_idx": 0,
                    "page_name": "p",
                    "state": "running",
                    "text": "",
                    "width": 800,
                    "height": 1200,
                }
            ),
        ),
    )
    page.route(f"**/api/pages/{project_id}/0/words", lambda route: route.fulfill(status=404, body="{}"))
    page.goto(f"{live_server_url}/jobs/{project_id}/pages/0")
    line = page.get_by_test_id("page-progress-message")
    expect(line).to_be_visible(timeout=15_000)
    expect(line).to_contain_text("Loading OCR engine")


def test_progress_message_absent_for_succeeded_job(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-PAGEVIEW-017 (bad path) — a succeeded job shows no progress line."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=10_000)
    expect(page.get_by_test_id("page-progress-message")).to_have_count(0)

"""Browser verification: PageViewPage download buttons, OCR text height fill,
and jobs-dock pinning toolbar reflow.

Tasks covered:
  TASK 16 — no checkbox, both download buttons visible; download URLs correct;
             ocr-text fills height; pinned dock narrows toolbar width.

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser``.

The toolbar-reflow assertion (Task 16 pin test) is the critical check that
cannot be done in jsdom: we measure the bounding-box width of the toolbar
area BEFORE and AFTER pinning the utility dock, confirming the main content
area narrows when the dock is pinned.
"""

from __future__ import annotations

import re

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


# ---------------------------------------------------------------------------
# TASK 16 — No checkbox role; both download buttons visible
# ---------------------------------------------------------------------------


def test_page_view_has_no_checkboxes(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Task 16: the PageView toolbar / editor has no checkbox role element.

    Task 9 replaced the checkbox-based download filter with two explicit
    buttons.  No checkbox must exist anywhere on the page.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=10_000)

    # Observable: no checkbox role on the page.
    checkbox_count = page.get_by_role("checkbox").count()
    assert checkbox_count == 0, f"Expected no checkboxes on PageView, found {checkbox_count}"


def test_page_view_shows_both_download_buttons(
    page: Page, live_server_url: str, seeded_managed_job_id: str
) -> None:
    """Task 16: both download buttons are visible on the PageView toolbar.

    Task 9 added 'download-images-text' and 'download-images-text-json'
    to the PageView toolbar (same two buttons as ResultsPage).
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=10_000)

    expect(page.get_by_test_id("download-images-text")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("download-images-text-json")).to_be_visible(timeout=10_000)


# ---------------------------------------------------------------------------
# TASK 16 — Download button network requests use correct ?include= parameter
# ---------------------------------------------------------------------------


def test_download_images_text_request_url(
    page: Page, live_server_url: str, seeded_managed_job_id: str
) -> None:
    """Task 16: 'download-images-text' fires a request with ?include=text.

    Intercepts the download network request and asserts the URL contains
    ``include=text`` (not json) AND the response is 200.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=15_000)

    btn = page.get_by_test_id("download-images-text")
    expect(btn).to_be_visible(timeout=10_000)

    # Intercept the download request before clicking.
    with page.expect_request(
        lambda req: "/download" in req.url and req.method in ("GET", "HEAD"),
        timeout=8_000,
    ) as req_info:
        btn.click()

    req = req_info.value
    assert "include=text" in req.url, f"Expected ?include=text in URL, got {req.url!r}"
    # 'text,json' must NOT appear in the text-only download URL.
    assert "json" not in req.url.split("include=")[-1].split("&")[0], (
        f"json appeared in text-only download URL: {req.url!r}"
    )

    # Backend effect: the API responds with a valid ZIP.
    resp = httpx.get(
        f"{live_server_url}/api/jobs/{seeded_managed_job_id}/download?include=text",
        timeout=10.0,
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK", "Expected ZIP magic bytes PK"


def test_download_images_text_json_request_url(
    page: Page, live_server_url: str, seeded_managed_job_id: str
) -> None:
    """Task 16: 'download-images-text-json' fires a request with ?include=text,json.

    Intercepts the download network request and asserts the URL contains
    ``include=text%2Cjson`` or ``include=text,json`` AND the response is 200.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}/pages/0")
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=15_000)

    btn = page.get_by_test_id("download-images-text-json")
    expect(btn).to_be_visible(timeout=10_000)

    with page.expect_request(
        lambda req: "/download" in req.url and req.method in ("GET", "HEAD"),
        timeout=8_000,
    ) as req_info:
        btn.click()

    req = req_info.value
    # URL may encode the comma: text%2Cjson or text,json.
    decoded_url = req.url.replace("%2C", ",")
    assert "include=text,json" in decoded_url, f"Expected ?include=text,json in URL, got {req.url!r}"

    # Backend effect: the API responds with 200 and a valid ZIP.
    resp = httpx.get(
        f"{live_server_url}/api/jobs/{seeded_managed_job_id}/download",
        params={"include": "text,json"},
        timeout=10.0,
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK", "Expected ZIP magic bytes PK"


# ---------------------------------------------------------------------------
# TASK 16 — OCR text box height approximates image panel height (Task 10)
# ---------------------------------------------------------------------------


def test_ocr_text_fills_panel_height(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Task 16: the ocr-text textarea fills the editor panel height (Task 10).

    Task 10 removed rows={40} from the Textarea so it fills the PageSplitView
    editor slot instead of having a fixed row count.  We assert the textarea
    height is within 40% of the image canvas height — the two panels are
    side-by-side and should be comparable in height.  A much shorter textarea
    would indicate rows={40} (or equivalent) is still constraining it.
    """
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=10_000)

    # Allow the layout to settle after React renders.
    page.wait_for_timeout(300)

    canvas_box = page.get_by_test_id("page-image-canvas").bounding_box()
    text_box = page.get_by_test_id("ocr-text").bounding_box()

    assert canvas_box is not None, "page-image-canvas not found or has no bounding box"
    assert text_box is not None, "ocr-text not found or has no bounding box"

    canvas_height = canvas_box["height"]
    text_height = text_box["height"]

    # The textarea must be at least 40% of the canvas panel height.
    # A fixed rows={40} textarea is typically ~700px; in fill mode it matches
    # the panel (~400-600px on a standard viewport).
    tolerance = 0.40
    assert text_height >= canvas_height * tolerance, (
        f"ocr-text height {text_height:.0f}px is less than "
        f"{tolerance:.0%} of canvas height {canvas_height:.0f}px — "
        "the textarea may be fixed-size rather than filling the panel"
    )


# ---------------------------------------------------------------------------
# TASK 16 — Pinning the jobs dock narrows the toolbar (Task 11 reflow)
# ---------------------------------------------------------------------------


def test_pinned_dock_narrows_toolbar_width(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Task 16: pinning the jobs dock makes the toolbar above the text narrower.

    Task 11 wired the utility dock pin to a CSS variable that narrows the main
    content area when the dock is pinned.  This test measures the bounding-box
    width of the PageView toolbar BEFORE and AFTER pinning the dock, asserting
    that the toolbar is narrower in the pinned state.

    This assertion is impossible in jsdom (no layout engine); it requires a
    real browser with Playwright.
    """
    import json as _json

    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=10_000)

    # Allow layout to stabilise.
    page.wait_for_timeout(300)

    # Measure the PageView toolbar width BEFORE pinning.
    # The toolbar is the outermost div of class page-split-view__toolbar.
    toolbar_locator = page.locator(".page-split-view__toolbar").first
    before_box = toolbar_locator.bounding_box()
    assert before_box is not None, "page-split-view__toolbar not found (unpinned)"
    before_width = before_box["width"]

    # Open the jobs dock: inject a running job to make the pill appear.
    page.route(
        "**/api/jobs",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=_json.dumps(
                [
                    {
                        "project_id": "fake-pin-job",
                        "name": "Fake Running Job",
                        "state": "running",
                        "progress_message": None,
                        "page_count": 1,
                        "pages_done": 0,
                        "pages": [],
                        "output_dir": "",
                        "output_mode": None,
                        "error": None,
                    }
                ]
            ),
        ),
    )

    # The jobs pill appears when a job is in-flight.  But we're on a subpage
    # (/pages/0), so we need the pill to have appeared since the app started.
    # Force a refresh to let the intercept take effect.
    page.reload()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)
    expect(page.get_by_label("OCR text")).to_be_enabled(timeout=10_000)
    page.wait_for_timeout(300)

    # Re-measure before-pin width on the reloaded page.
    before_box = toolbar_locator.bounding_box()
    assert before_box is not None, "page-split-view__toolbar not found after reload"
    before_width = before_box["width"]

    # Wait for the jobs-pill-count badge (driven by intercepted running job).
    expect(page.get_by_test_id("jobs-pill-count")).to_be_visible(timeout=10_000)

    # Open the dock via the Jobs button.
    jobs_button = page.get_by_role("button", name=re.compile("Jobs"))
    jobs_button.click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Pin the dock.
    pin_button = page.get_by_test_id("slide-over-panel-pin")
    expect(pin_button).to_be_visible(timeout=5_000)
    pin_button.click()

    # Allow layout to reflow after pin.
    page.wait_for_timeout(500)

    # Measure toolbar width AFTER pinning.
    after_box = toolbar_locator.bounding_box()
    assert after_box is not None, "page-split-view__toolbar not found (pinned)"
    after_width = after_box["width"]

    # Observable: pinning the dock narrows the toolbar.
    # The pinned dock panel takes up space in the viewport, reducing available
    # width for the main content area (including the PageView toolbar).
    assert after_width < before_width, (
        f"Expected toolbar to narrow when dock is pinned, but "
        f"before={before_width:.0f}px, after={after_width:.0f}px. "
        "The jobs-dock pin may not be causing a layout reflow."
    )

    # Unpin to clean up (so the dock doesn't persist into other tests).
    pin_button.click()
    page.unroute("**/api/jobs")

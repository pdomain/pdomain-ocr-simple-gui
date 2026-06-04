"""Tier-A cross-screen flow tests (Milestone 7).

Each test drives a multi-unit sequence through the real SPA (FakeStageDispatcher)
and asserts both on-screen DOM state and on-disk / API backend effects.

Tier-B slice note:
  The flagship upload→real-OCR→download flow (Tier B) already lives in
  test_real_ocr_pipeline.py and cites F-UPLOAD-OCR-DOWNLOAD-01.  Do NOT
  duplicate it here.

Flagship Tier-A download leg:
  The upload→FakeDispatcher→managed-download sequence is split into two
  logical sub-legs because the FakeStageDispatcher writes jobs with
  output_mode=None (no managed mode) — the upload API creates an
  output_mode based on the job's OutputConfig, which requires UI interaction
  with the OutputConfigPanel radio group to select "managed".  Driving that
  radio group is fragile and couples the flow test to internal UI layout.
  Instead the Tier-A test:
    1. Drives the full upload→OCR→results→page-edit chain via a fresh
       file-picker upload (FakeStageDispatcher; completes in <15 s in CI).
    2. For the download assertion, navigates to the pre-seeded managed job
       (seeded_managed_job_id) and asserts the download button and ZIP.
  This is the documented approach when the download leg cannot be reached
  faithfully from a Fake dispatcher upload.  The Tier-B test covers the
  full chain end-to-end with the real engine.

Marked ``slow`` and ``e2e`` so they are excluded from ``make test`` and
included in ``make e2e-browser`` / ``make e2e-fast``.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]

# Minimal valid 1x1 greyscale PNG
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


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


def _read_prefs_file(e2e_data_root: Path) -> dict:
    """Read ui-prefs.json; return empty dict if absent."""
    p = e2e_data_root / "suite_data" / "ui-prefs.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# F-UPLOAD-OCR-DOWNLOAD-01 — Upload, run OCR, review results, edit, download
# ---------------------------------------------------------------------------


def test_upload_ocr_download_flow(
    page: Page,
    live_server_url: str,
    e2e_data_root: Path,
    seeded_managed_job_id: str,
    tmp_path: Path,
) -> None:
    """Covers: F-UPLOAD-OCR-DOWNLOAD-01

    Flagship happy path: upload → OCR (FakeStageDispatcher) → results page
    → open page → edit text → save → return to results → assert job state on
    disk.  Download assertion uses seeded_managed_job_id (see module docstring
    for why the upload leg cannot drive a managed-mode job via Fake dispatcher
    without coupling to OutputConfigPanel internals).

    Steps: B-HOME-002 → B-HOME-011 → B-RESULTS-002 → B-RESULTS-003 →
           B-RESULTS-010 → B-PAGEVIEW-010 → B-RESULTS-006

    End state (Tier A):
    - ResultsPage succeeded + page-row visible for the uploaded image.
    - Sidecar pages/<name>.json has edited_text after save.
    - API GET /api/pages/{id}/0 returns the edited text.
    - Managed-mode job (seeded_managed_job_id): download ZIP non-empty.
    """
    # --- Leg 1: Upload → OCR → results (B-HOME-002, B-HOME-011) ---
    img = tmp_path / "scan.png"
    img.write_bytes(_PNG_1X1)

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # B-HOME-002: pick a file via the hidden file input.
    with page.expect_response(lambda r: "/api/uploads" in r.url and r.request.method == "POST") as resp_info:
        page.get_by_test_id("source-picker-file-pick").set_input_files(str(img))
    upload_resp = resp_info.value
    assert upload_resp.status == 200, f"upload failed: {upload_resp.status}"

    # B-HOME-011: submit the job.
    expect(page.get_by_test_id("job-config-inline")).to_be_visible(timeout=10_000)
    page.get_by_test_id("run-ocr-button").click()

    # B-RESULTS-002 / B-RESULTS-003: results page appears and reaches succeeded.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        """() => document.querySelectorAll('[data-testid="page-row"]').length > 0""",
        timeout=20_000,
    )
    expect(page.get_by_test_id("page-row").first).to_be_visible()

    # Extract the project_id from the URL.
    project_id = page.url.rstrip("/").split("/jobs/")[-1].split("/")[0]

    # On-disk: project.json exists.
    proj_dir = e2e_data_root / "projects" / project_id
    assert (proj_dir / "project.json").exists(), f"project.json missing at {proj_dir}"

    # API: job retrievable with succeeded state.
    status = httpx.get(f"{live_server_url}/api/jobs/{project_id}", timeout=10.0).json()
    assert status["state"] == "succeeded", f"expected succeeded, got: {status.get('state')!r}"
    assert status["project_id"] == project_id

    # --- Leg 2: Open page → edit → save (B-RESULTS-010, B-PAGEVIEW-010) ---
    page.get_by_test_id("page-row").first.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=10_000)

    # B-PAGEVIEW-010: edit the text and save.
    edited_text = "flow-edit by F-UPLOAD-OCR-DOWNLOAD-01"
    textarea.click(click_count=3)
    textarea.fill(edited_text)
    page.get_by_test_id("page-save-button").click()
    _toast_with(page, "Saved")

    # API: GET /api/pages returns the edited text.
    page_resp = httpx.get(f"{live_server_url}/api/pages/{project_id}/0", timeout=10.0)
    assert page_resp.status_code == 200
    assert page_resp.json()["text"] == edited_text, (
        f"Expected edited text in API response; got: {page_resp.json()!r}"
    )

    # On-disk: the sidecar has edited_text set.
    pages_dir = proj_dir / "pages"
    sidecars = list(pages_dir.glob("*.json")) if pages_dir.exists() else []
    assert sidecars, f"No sidecar found under {pages_dir}"
    sidecar_data = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert sidecar_data.get("edited_text") == edited_text, (
        f"expected edited_text in sidecar; got: {sidecar_data!r}"
    )

    # --- Leg 3: Download (B-RESULTS-006) — seeded managed job ---
    # (See module docstring: FakeDispatcher does not produce managed-mode jobs
    # from a file-picker upload without UI interaction with OutputConfigPanel.)
    # Task 9: replaced single download-results-button + checkboxes with two
    # explicit buttons.  Use download-images-text-json (images + text + JSON).
    page.goto(f"{live_server_url}/jobs/{seeded_managed_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    btn = page.get_by_test_id("download-images-text-json")
    expect(btn).to_be_visible(timeout=10_000)

    with page.expect_download(timeout=10_000) as dl_info:
        btn.click()
    download = dl_info.value
    assert download.suggested_filename.endswith(".zip"), (
        f"Expected .zip download, got {download.suggested_filename!r}"
    )
    path = download.path()
    assert path is not None and path.stat().st_size > 0, "Downloaded .zip is empty"

    # API: the managed-mode output root contains expected artifacts.
    members_resp = httpx.get(
        f"{live_server_url}/api/jobs/{seeded_managed_job_id}/download",
        params={"include": "text,json"},
        timeout=15.0,
    )
    assert members_resp.status_code == 200


# ---------------------------------------------------------------------------
# F-RERUN-01 — Single-page rerun preserves prior edit
# ---------------------------------------------------------------------------


def test_rerun_preserves_edit_flow(
    page: Page,
    live_server_url: str,
    e2e_data_root: Path,
    seeded_flow_rerun_job_id: str,
) -> None:
    """Covers: F-RERUN-01

    Flow: results-page row-click → page-view → save edit → rerun DocTR →
    assert edited_text survives the rerun (B-PAGEVIEW-013 regression guard).

    Steps: B-RESULTS-010 → B-PAGEVIEW-010 → B-PAGEVIEW-013 → B-PAGEVIEW-010 (verify)

    Regression: yes (B-PAGEVIEW-013 is regression-tagged; commit d0edd9d
    fixed rerun silently discarding edited_text).

    Uses seeded_flow_rerun_job_id (isolated from seeded_rerun_job_id used by
    per-unit tests) to avoid xdist parallel write contamination.

    End state:
    - Toast "Re-run" visible after POST /api/pages/{id}/0/rerun.
    - API GET /api/pages/{id}/0 returns the pre-rerun edited_text.
    - On-disk sidecar still has edited_text set.

    Bad-state: tested via direct API call (missing project → 404).
    """
    # --- Step 1: open page view (B-RESULTS-010) ---
    page.goto(f"{live_server_url}/jobs/{seeded_flow_rerun_job_id}")
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)

    row = page.get_by_test_id("page-row").first
    expect(row).to_be_visible(timeout=10_000)
    row.click()
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # --- Step 2: save an edit (B-PAGEVIEW-010) ---
    textarea = page.get_by_label("OCR text")
    expect(textarea).to_be_enabled(timeout=10_000)
    edit = "rerun-flow edit — must survive a rerun"
    textarea.click(click_count=3)
    textarea.fill(edit)
    page.get_by_test_id("page-save-button").click()
    _toast_with(page, "Saved")

    # Verify on-disk: sidecar has edited_text.
    pages_dir = e2e_data_root / "projects" / seeded_flow_rerun_job_id / "pages"
    sidecar_path = pages_dir / "page-001.json"
    assert sidecar_path.exists(), f"sidecar missing at {sidecar_path}"
    sidecar_before = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar_before.get("edited_text") == edit, (
        f"edited_text not persisted before rerun: {sidecar_before!r}"
    )

    # --- Step 3: rerun DocTR (B-PAGEVIEW-013 regression) ---
    rerun_btn = page.get_by_test_id("page-rerun-doctr")
    expect(rerun_btn).to_be_enabled(timeout=10_000)
    rerun_btn.click()
    _toast_with(page, "Re-run", timeout_ms=10_000)

    # --- Step 4: verify edited_text is preserved (B-PAGEVIEW-010 verify) ---
    # API: GET /api/pages/{id}/0 must still return the saved edit.
    page_resp = httpx.get(f"{live_server_url}/api/pages/{seeded_flow_rerun_job_id}/0", timeout=10.0)
    assert page_resp.status_code == 200
    assert page_resp.json()["text"] == edit, (
        f"Rerun clobbered edited_text — regression! API returned: {page_resp.json()!r}"
    )

    # On-disk: sidecar still carries edited_text.
    sidecar_after = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar_after.get("edited_text") == edit, f"Rerun clobbered edited_text on disk: {sidecar_after!r}"

    # Bad-state: rerun on a missing project → 404.
    bad_resp = httpx.post(
        f"{live_server_url}/api/pages/no-such-project-xyz/0/rerun",
        json={"engine": "doctr"},
        timeout=10.0,
    )
    assert bad_resp.status_code == 404


# ---------------------------------------------------------------------------
# F-PREFS-ROUNDTRIP-01 — Prefs round-trip across reload
# ---------------------------------------------------------------------------


def test_prefs_roundtrip_flow(
    page: Page,
    live_server_url: str,
    e2e_data_root: Path,
) -> None:
    """Covers: F-PREFS-ROUNDTRIP-01

    Flow: open settings modal → click Light theme → click Compact density →
    close modal → reload page → assert theme + density persisted and applied.

    Steps: B-SHELL-006 → B-SHELL-008 → B-SHELL-009 → B-SHELL-007 → B-SHELL-011

    Regression: yes — B-SHELL-008 and B-SHELL-009 are both regression-tagged
    (prior persistCommon had silent catch {}; fix adds onPersistError toast).
    This flow catches cross-step prefs bleed where one PUT overwrites a prior
    setting.  fontScale excluded (fragile Playwright drag, per M6 precedent).

    End state:
    - data-theme="light" on documentElement after reload.
    - data-density="compact" on app-shell element after reload.
    - ui-prefs.json on disk has apps.pdomain-ocr-simple-gui.ui_prefs.theme="light"
      and ...density="compact".
    - Settings modal is closed; no toast error.

    Bad-state: PUT /api/prefs 500 → sonner toast (tested in test_click_paths_app_shell).
    """
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # B-SHELL-006: open settings modal.
    trigger = page.get_by_test_id("settings-slot-trigger")
    expect(trigger).to_be_visible(timeout=5_000)
    trigger.click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # B-SHELL-008: click Light theme.
    page.get_by_test_id("settings-appearance-theme-light").click()
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') === 'light'",
        timeout=5_000,
    )

    # B-SHELL-009: click Compact density.
    page.get_by_test_id("settings-appearance-density-compact").click()
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="app-shell"]');
            return el && el.getAttribute('data-density') === 'compact';
        }""",
        timeout=5_000,
    )

    # Allow PUT /api/prefs to complete before reading back.
    page.wait_for_timeout(500)

    # B-SHELL-007: close settings modal.
    page.get_by_test_id("slide-over-panel-close").click()
    expect(page.get_by_test_id("slide-over-panel")).not_to_be_visible(timeout=5_000)

    # API: both prefs persisted.
    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    ui_prefs = prefs.get("ui_prefs", {})
    assert ui_prefs.get("theme") == "light", f"Expected theme='light' in GET /api/prefs; got: {prefs!r}"
    assert ui_prefs.get("density") == "compact", (
        f"Expected density='compact' in GET /api/prefs; got: {prefs!r}"
    )

    # On-disk: ui-prefs.json carries both values.
    disk_prefs = _read_prefs_file(e2e_data_root)
    app_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    ui_disk = app_disk.get("ui_prefs", {})
    assert ui_disk.get("theme") == "light", f"Expected theme='light' on disk; got: {disk_prefs!r}"
    assert ui_disk.get("density") == "compact", f"Expected density='compact' on disk; got: {disk_prefs!r}"

    # B-SHELL-011: reload and verify both attributes restored.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') === 'light'",
        timeout=5_000,
    )
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="app-shell"]');
            return el && el.getAttribute('data-density') === 'compact';
        }""",
        timeout=5_000,
    )

    # End-state assertions: no settings modal visible, no error toast.
    expect(page.get_by_test_id("slide-over-panel")).not_to_be_visible()
    expect(page.locator("[data-sonner-toast]")).to_have_count(0)


# ---------------------------------------------------------------------------
# F-NOTFOUND-01 — Stale recent-project row leads to not-found block
# ---------------------------------------------------------------------------


def test_notfound_recovery_flow(
    page: Page,
    live_server_url: str,
) -> None:
    """Covers: F-NOTFOUND-01

    Flow: seed a recent-project row pointing at a non-existent project_id →
    click it (B-HOME-013) → results page fetches 404 → "Job not found" block
    renders (B-RESULTS-011) → click back-home link → home page renders.

    This seeds a prefs entry for a non-existent project_id so that B-HOME-013
    (row-click navigation) is genuinely exercised by clicking the row on the
    home page, not just by navigating to an unknown URL directly.

    Regression: yes — B-RESULTS-011 is regression-tagged (fix 279d4b4; prior
    useOcrJob did not distinguish 404 from transient errors, so a stale project
    would leave the page stuck loading forever instead of rendering the not-found
    block).

    End state:
    - Home page visible (data-testid="home-page").
    - No crash; no generic results-error block (results-page is gone from DOM).

    Bad-state: N/A — this flow IS the bad path (stale recent-project entry).
    """
    ghost_id = "e2e-ghost-not-on-disk-xyz999"
    ghost_name = "Deleted Project"

    # Seed prefs with a recent-project entry pointing at a non-existent project.
    prefs_payload = {
        "recent_projects": [
            {
                "project_id": ghost_id,
                "name": ghost_name,
                "last_opened_at": "2026-01-01T00:00:00+00:00",
                "page_count": 1,
                "engine": "doctr",
                "status": "succeeded",
            }
        ]
    }
    resp = httpx.put(f"{live_server_url}/api/prefs", json=prefs_payload, timeout=5.0)
    resp.raise_for_status()

    # On-disk / API: the ghost project does NOT exist.
    job_resp = httpx.get(f"{live_server_url}/api/jobs/{ghost_id}", timeout=5.0)
    assert job_resp.status_code == 404, f"Expected ghost project to return 404; got {job_resp.status_code}"

    # B-HOME-013: navigate to home; click the seeded recent-project row.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    row = page.get_by_test_id("recent-project-row").first
    expect(row).to_be_visible(timeout=10_000)

    # The row must point at the ghost project (check the aria-label or URL on click).
    row.click()

    # B-RESULTS-011: results page renders but shows the "Job not found" block.
    # The results-page testid is present (page mounted), but the not-found block
    # replaces the normal content.
    expect(page.get_by_test_id("results-page")).to_be_visible(timeout=15_000)
    not_found = page.get_by_test_id("results-not-found")
    expect(not_found).to_be_visible(timeout=10_000)
    # "not found" (case-insensitive) — check inner text directly.
    not_found_text = not_found.inner_text().lower()
    assert "not found" in not_found_text, f"Expected 'not found' in not-found block; got: {not_found_text!r}"

    # No generic error block (the 404 path is distinct from a 500).
    expect(page.get_by_test_id("results-error")).to_have_count(0)

    # B-RESULTS-011 recovery: click the back-home link inside the not-found block.
    back_link = not_found.get_by_role("link")
    expect(back_link).to_be_visible(timeout=5_000)
    back_link.click()

    # End state: home page is visible again; no crash.
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    assert "/jobs/" not in page.url, f"Expected home URL after recovery; got {page.url!r}"

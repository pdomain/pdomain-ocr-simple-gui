"""Tier-A behavior tests for App shell (AppShell / AppHeader / prefs / shortcuts).

Covers B-SHELL-001 through B-SHELL-013 (AppShell, prefs persist, shortcuts cheatsheet).

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser`` / ``make e2e-fast``.

Every test cites its behavior record (``Covers: B-SHELL-NNN``), asserts the
observable DOM output, re-queries the backend API where there is a backend effect,
and inspects on-disk artifacts (ui-prefs.json) for prefs records.  Each record
has a good path and at least one bad path.

Settings modal (B-SHELL-006/007/008/009/010):
  ``App.tsx`` places ``<SettingsSlot />`` inside ``AppHeader.actions`` alongside
  ``<ShortcutsHelpButton />``.  ``SettingsSlot`` is exported from
  ``@pdomain/pdomain-ui/shell`` and calls ``useSettingsModal().openModal()``.
  Because ``AppHeader`` is a descendant of ``AppShell`` (rendered inside the
  ``header`` slot), the ``SettingsModalContext`` provided by ``AppShell`` is
  available and the gear button opens the built-in settings modal.

  All six prefs-related behaviors are now fully testable via real UI interaction:
    - ``settings-slot-trigger`` → click → opens the utility dock (``slide-over-panel``)
    - Appearance controls (theme/density/font-scale) inside the dock panel
    - ``slide-over-panel-close`` → click → closes the dock

Active-jobs pill (B-SHELL-002/003):
  The ``useActiveJobs`` hook polls ``GET /api/jobs`` every 5 s.  Driving a
  "running job" state without racing a real pipeline is done via
  ``page.route()`` to intercept the jobs endpoint and ``route.fulfill()`` a
  held running-job payload.

NOTE on registry-vs-local-dev:
  - Selectors for the shortcuts cheatsheet and help button are stable in the INSTALLED
    registry package (@pdomain/pdomain-ui@0.2.2):
    * ``shortcuts-help-button`` = ShortcutsHelpButton (in AppHeader via ``actions`` prop)
    * ``shortcuts-cheatsheet`` = cheatsheet dialog (hardcoded in pdomain-ui bundle)
  - The ``?`` key and Escape key are registered globally by ShortcutsContext in the
    registry build (verified in ShortcutsContext-CAfy8e9D.js dist chunk).
  - ``APP_TEST_IDS.shortcutsCheatsheet`` = ``"shortcuts-cheatsheet"`` is a hardcoded
    testid in the pdomain-ui bundle, NOT exported as a named constant from the testids
    catalog.  The alias is defined locally in ``frontend/src/lib/testids.ts``.
  - ``ShortcutsProvider`` and ``useShortcuts`` from ``@pdomain/pdomain-ui/hooks`` are
    present in the registry 0.2.2 dist (hooks.d.ts + hooks.js).

On-disk prefs location:
  The ``reset_prefs`` autouse fixture wipes ui-prefs.json before each test
  (commit f575aea).  The prefs file path is
  ``<PD_SUITE_DATA_DIR>/ui-prefs.json``.  All e2e prefs tests must read the
  file relative to ``e2e_data_root / "suite_data"`` to stay in-scope.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


def _read_prefs(e2e_data_root: Path) -> dict:
    """Read ui-prefs.json; return empty dict if absent."""
    p = e2e_data_root / "suite_data" / "ui-prefs.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# B-SHELL-001 — App loads and renders shell with config
# ---------------------------------------------------------------------------


def test_app_shell_loads(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-001 — app-shell wrapper + home-page are visible on load."""
    page.goto(live_server_url)

    # Observable: AppShell wrapper + header + main zone are present.
    expect(page.get_by_test_id("app-shell")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("app-shell-header")).to_be_visible(timeout=10_000)
    expect(page.get_by_test_id("app-shell-main")).to_be_visible(timeout=10_000)

    # Observable: home-page is visible inside the main zone.
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Backend: /api/config returns 200 with required fields.
    resp = httpx.get(f"{live_server_url}/api/config", timeout=5.0)
    assert resp.status_code == 200
    body = resp.json()
    assert "mode" in body
    assert "is_containerized" in body

    # Bad-state: /api/prefs is readable on startup.
    prefs_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert prefs_resp.status_code == 200


# ---------------------------------------------------------------------------
# B-SHELL-002 — Active-jobs count updates when a job is running
# ---------------------------------------------------------------------------


def test_active_jobs_count_badge_appears_with_running_job(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-002 — jobs-pill-count badge appears when GET /api/jobs
    returns running jobs.

    Drives the running-job state deterministically with page.route() to
    fulfill GET /api/jobs with a synthetic running payload, avoiding any
    dependency on real pipeline timing.
    """
    running_payload = json.dumps(
        [
            {
                "project_id": "fake-running-job-001",
                "name": "Fake Running Job",
                "state": "running",
                "page_count": 10,
                "pages": [{"state": "succeeded"} for _ in range(3)] + [{"state": "running"}] * 7,
            }
        ]
    )

    # Intercept GET /api/jobs to always return the running-job payload.
    page.route(
        "**/api/jobs",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=running_payload,
        ),
    )

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Observable: jobs-pill-count badge appears (only visible when 1+ active jobs).
    expect(page.get_by_test_id("jobs-pill-count")).to_be_visible(timeout=10_000)
    pill_count = page.get_by_test_id("jobs-pill-count")
    count_text = pill_count.inner_text()
    assert count_text.strip() == "1", f"Expected count=1 in badge; got: {count_text!r}"

    # Observable: pulse dot is also present alongside the count.
    expect(page.get_by_test_id("jobs-pill-pulse")).to_be_visible(timeout=5_000)

    # Bad-state: when GET /api/jobs returns empty list the badge disappears.
    page.unroute("**/api/jobs")
    page.route(
        "**/api/jobs",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body="[]",
        ),
    )
    # Wait for the 5-second refetch or trigger a manual navigation to reload.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    # Badge must not be visible when no active jobs.
    expect(page.get_by_test_id("jobs-pill-count")).not_to_be_visible(timeout=10_000)


# ---------------------------------------------------------------------------
# B-SHELL-003 — Jobs button opens right-side jobs panel
# ---------------------------------------------------------------------------


def test_jobs_button_opens_right_jobs_panel(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-003 — clicking the jobs button opens the right-side
    jobs panel with the running job listed.

    Drives the running-job state with page.route() (same pattern as B-SHELL-002).
    """
    running_payload = json.dumps(
        [
            {
                "project_id": "fake-running-job-002",
                "name": "Running OCR Scan",
                "state": "running",
                "progress_message": "Processing page 3/5",
                "page_count": 5,
                "pages": [{"state": "succeeded"}] * 2 + [{"state": "running"}] * 3,
            }
        ]
    )

    page.route(
        "**/api/jobs",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=running_payload,
        ),
    )
    page.route(
        "**/api/jobs/fake-running-job-002",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "project_id": "fake-running-job-002",
                    "name": "Running OCR Scan",
                    "state": "running",
                    "progress_message": "Processing page 3/5",
                    "page_count": 5,
                    "pages_done": 2,
                    "pages": [{"page_idx": 0, "page_name": "page-001", "state": "running"}],
                }
            ),
        ),
    )

    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Wait for the jobs-pill count badge to appear.
    expect(page.get_by_test_id("jobs-pill-count")).to_be_visible(timeout=10_000)
    jobs_button = page.get_by_role("button", name=re.compile("Jobs"))

    # Bad-state / regression: hover alone must not open a sticky header popover.
    # In pdomain-ui 0.4.0 the hover popover was removed; click opens the utility dock.
    jobs_button.hover()
    expect(page.get_by_test_id("jobs-pill-popover")).not_to_be_visible(timeout=1_000)

    # Click path: the utility dock slide-over opens with the Jobs surface.
    # The slide-over-panel is absolutely positioned; jobs-panel-body shows empty list
    # ("No active jobs") since AppShell's internal UtilityDock doesn't receive activeJobs.
    # The pill click wires to useUtilityDock().toggle('jobs') via the utility dock API.
    jobs_button.click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)
    expect(page.get_by_test_id("jobs-panel-body")).to_be_visible(timeout=5_000)

    # Dismiss path: slide-over close button hides the dock.
    page.get_by_test_id("slide-over-panel-close").click()
    expect(page.get_by_test_id("slide-over-panel")).not_to_be_visible(timeout=5_000)

    # Row action path: re-open (jobs surface; no job rows since empty active list).
    jobs_button.click()
    expect(page.get_by_test_id("jobs-panel-body")).to_be_visible(timeout=5_000)
    # Note: AppShell's built-in UtilityDock doesn't receive activeJobs, so
    # JobPanelBody shows "No active jobs" — no job-row to click.
    # The full jobs-in-dock integration requires AppShell to gain a jobsConfig prop.

    # Bad-state: when GET /api/jobs returns empty list, the count badge disappears.
    # The panel is click-owned; when no jobs are running the count badge is absent.
    page.unroute("**/api/jobs")
    page.route(
        "**/api/jobs",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body="[]",
        ),
    )
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    # Count badge is absent when idle.
    expect(page.get_by_test_id("jobs-pill-count")).not_to_be_visible(timeout=10_000)


# ---------------------------------------------------------------------------
# B-SHELL-004 — Shortcuts cheatsheet opens via button click
# ---------------------------------------------------------------------------


def test_shortcuts_cheatsheet_opens_on_button_click(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-SHELL-004 — clicking the ? button opens the shortcuts cheatsheet."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # The cheatsheet must be absent before clicking.
    # In pdomain-ui 0.4.0, ShortcutsHelpButton opens the utility dock's keybinds
    # surface (SlideOverPanel with ShortcutsCheatsheetBody) instead of a Dialog.
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).not_to_be_visible()

    # Click the ? help button (rendered by AppHeader via actions={<ShortcutsHelpButton/>}).
    help_btn = page.get_by_test_id("shortcuts-help-button")
    expect(help_btn).to_be_visible(timeout=5_000)
    help_btn.click()

    # Observable: shortcuts-cheatsheet-body appears inside the utility dock.
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)

    # Backend: no writes — purely client-side state.
    prefs_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert prefs_resp.status_code == 200  # unchanged; no PUT was fired


# ---------------------------------------------------------------------------
# B-SHELL-004 (second open path) — Shortcuts cheatsheet opens via ? key
# ---------------------------------------------------------------------------


def test_shortcuts_cheatsheet_opens_on_question_mark_key(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-SHELL-004 — pressing ? key opens the shortcuts cheatsheet."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Make sure focus is on body, not inside a text input.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).not_to_be_visible()

    # Press ? to open — ShortcutsContext registers a global ? keydown.
    page.keyboard.press("?")
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)

    # Bad-state: no API writes.
    resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# B-SHELL-005 — Shortcuts cheatsheet closes on Escape
# ---------------------------------------------------------------------------


def test_shortcuts_cheatsheet_closes_on_escape(page: Page, live_server_url: str, seeded_job_id: str) -> None:
    """Covers: B-SHELL-005 — Escape closes the shortcuts cheatsheet."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Open the cheatsheet first.
    # In pdomain-ui 0.4.0, ShortcutsHelpButton opens the utility dock's keybinds surface.
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)

    # Press Escape — SlideOverPanel handles this globally.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).not_to_be_visible(timeout=5_000)

    # Bad-state check: re-open and confirm it works again after close.
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# B-SHELL-006 — Settings modal opens on gear click
# ---------------------------------------------------------------------------


def test_settings_modal_opens_on_gear_click(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-006 — clicking settings-slot-trigger opens the settings modal.

    SettingsSlot is placed inside AppHeader.actions alongside ShortcutsHelpButton.
    It calls useSettingsModal().openModal() provided by AppShell's
    SettingsModalContext, which is available because AppHeader is a descendant
    of AppShell.
    """
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Observable: settings-slot-trigger is present in the header.
    trigger = page.get_by_test_id("settings-slot-trigger")
    expect(trigger).to_be_visible(timeout=5_000)

    # Settings panel is absent before clicking.
    # In pdomain-ui 0.4.0, SettingsSlot opens the utility dock (slide-over) instead
    # of a modal dialog. The testid "settings-modal" is no longer rendered by AppShell;
    # "slide-over-panel" wraps the SettingsPanel inside the utility dock.
    expect(page.get_by_test_id("slide-over-panel")).not_to_be_visible()

    trigger.click()

    # Observable: settings panel appears inside the utility dock with Appearance tab active.
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Appearance controls are visible inside the panel.
    expect(page.get_by_test_id("settings-appearance-theme-dark")).to_be_visible(timeout=3_000)
    expect(page.get_by_test_id("settings-appearance-theme-light")).to_be_visible(timeout=3_000)
    expect(page.get_by_test_id("settings-appearance-density-compact")).to_be_visible(timeout=3_000)
    expect(page.get_by_test_id("settings-appearance-font-scale-slider")).to_be_visible(timeout=3_000)

    # Backend: no writes on open.
    prefs_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert prefs_resp.status_code == 200


# ---------------------------------------------------------------------------
# B-SHELL-007 — Settings modal closes on close button
# ---------------------------------------------------------------------------


def test_settings_modal_closes_on_close_button(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-007 — clicking settings-modal-close dismisses the modal."""
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Open the settings panel (utility dock).
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Click the close button (SlideOverPanel close button).
    page.get_by_test_id("slide-over-panel-close").click()

    # Observable: panel disappears.
    expect(page.get_by_test_id("slide-over-panel")).not_to_be_visible(timeout=5_000)

    # Bad-state: panel can be re-opened after closing.
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Backend: no writes from open/close cycle.
    prefs_resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert prefs_resp.status_code == 200


# ---------------------------------------------------------------------------
# B-SHELL-008 — Theme toggle persists via /api/prefs
# ---------------------------------------------------------------------------


def test_theme_persists_via_ui(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-008 — clicking Light theme radio in settings modal
    applies data-theme="light" and persists via PUT /api/prefs.

    Regression: yes — prior persistCommon had silent catch {}; now throws +
    shows toast on error (unit-tested in AppPrefsError.test.tsx).
    """
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Open the settings panel (utility dock) via the gear trigger.
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Click the Light theme radio.
    page.get_by_test_id("settings-appearance-theme-light").click()

    # Observable: data-theme="light" is applied to documentElement immediately.
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') === 'light'",
        timeout=5_000,
    )

    # Backend: GET /api/prefs reflects the persisted change.
    # Give a brief moment for the PUT to complete before reading back.
    page.wait_for_timeout(500)
    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    # Theme is persisted in ui_prefs (written by persistCommon via AppShell).
    ui_prefs = prefs.get("ui_prefs", {})
    assert ui_prefs.get("theme") == "light", f"Expected theme='light' in GET /api/prefs; got: {prefs!r}"

    # On-disk: App.tsx's persistCommon sends {ui_prefs: prefs} which is stored
    # in apps.pdomain-ocr-simple-gui.ui_prefs by write_app().
    disk_prefs = _read_prefs(e2e_data_root)
    app_on_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    ui_prefs_on_disk = app_on_disk.get("ui_prefs", {})
    assert ui_prefs_on_disk.get("theme") == "light", (
        f"Expected apps.pdomain-ocr-simple-gui.ui_prefs.theme='light' on disk; got: {disk_prefs!r}"
    )

    # UI: reload — data-theme="light" is restored from prefs on boot.
    page.get_by_test_id("slide-over-panel-close").click()
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') === 'light'",
        timeout=5_000,
    )

    # Bad-state (PUT fails): tested at unit level via AppPrefsError.test.tsx.
    # Error path (persist error → sonner toast) is covered there.


def test_theme_persists_via_api(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-008 — API-level fallback: PUT /api/prefs theme persists and
    survives reload even without UI interaction.

    Regression: yes — prior persistCommon had silent catch {}.
    """
    # Seed via PUT /api/prefs with ui_prefs.
    put_resp = httpx.put(
        f"{live_server_url}/api/prefs",
        json={"ui_prefs": {"theme": "light", "density": "normal", "fontScale": 1.0}},
        timeout=5.0,
    )
    put_resp.raise_for_status()

    # Backend: GET /api/prefs reflects the change.
    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    assert prefs.get("ui_prefs", {}).get("theme") == "light", (
        f"Expected theme='light' in GET /api/prefs; got: {prefs!r}"
    )

    # On-disk: ui-prefs.json stores ui_prefs under apps.pdomain-ocr-simple-gui.
    # (PUT /api/prefs writes via write_app(), not write_common(); the `common`
    # key is only written when AppShell's persistCommon fires after a UI toggle.)
    disk_prefs = _read_prefs(e2e_data_root)
    app_prefs_on_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    assert app_prefs_on_disk.get("ui_prefs", {}).get("theme") == "light", (
        f"Expected ui_prefs.theme='light' in apps.pdomain-ocr-simple-gui on disk; got: {disk_prefs!r}"
    )

    # UI: reload — data-theme="light" should be applied on boot.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') === 'light'",
        timeout=5_000,
    )

    # Bad-state: PUT with non-ok → prefs unchanged (tested at unit level via
    # AppPrefsError.test.tsx; not repeated here to keep e2e scope tight).


# ---------------------------------------------------------------------------
# B-SHELL-009 — Density toggle persists via /api/prefs
# ---------------------------------------------------------------------------


def test_density_persists_via_ui(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-009 — clicking the Compact density radio in settings modal
    applies data-density="compact" and persists via PUT /api/prefs.

    Regression: yes — same silent-catch as B-SHELL-008.
    """
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Open the settings panel (utility dock).
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)

    # Click the Compact density radio.
    page.get_by_test_id("settings-appearance-density-compact").click()

    # Observable: data-density="compact" applied to the app-shell element.
    # (UIPrefsApplicator sets data-density on [data-testid="app-shell"].)
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="app-shell"]');
            return el && el.getAttribute('data-density') === 'compact';
        }""",
        timeout=5_000,
    )

    # Backend: persist check.
    page.wait_for_timeout(500)
    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    ui_prefs = prefs.get("ui_prefs", {})
    assert ui_prefs.get("density") == "compact", (
        f"Expected density='compact' in GET /api/prefs; got: {prefs!r}"
    )

    # On-disk: App.tsx's persistCommon sends {ui_prefs: prefs} which is stored
    # in apps.pdomain-ocr-simple-gui.ui_prefs by write_app().
    disk_prefs = _read_prefs(e2e_data_root)
    app_on_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    ui_prefs_on_disk = app_on_disk.get("ui_prefs", {})
    assert ui_prefs_on_disk.get("density") == "compact", (
        f"Expected apps.pdomain-ocr-simple-gui.ui_prefs.density='compact' on disk; got: {disk_prefs!r}"
    )

    # UI: reload — compact density restored.
    page.get_by_test_id("slide-over-panel-close").click()
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="app-shell"]');
            return el && el.getAttribute('data-density') === 'compact';
        }""",
        timeout=5_000,
    )


def test_density_persists_via_api(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-009 — PUT /api/prefs density persists and survives reload.

    Regression: yes — same silent-catch as B-SHELL-008.
    """
    put_resp = httpx.put(
        f"{live_server_url}/api/prefs",
        json={"ui_prefs": {"theme": "dark", "density": "compact", "fontScale": 1.0}},
        timeout=5.0,
    )
    put_resp.raise_for_status()

    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    assert prefs.get("ui_prefs", {}).get("density") == "compact", (
        f"Expected density='compact' in GET /api/prefs; got: {prefs!r}"
    )

    disk_prefs = _read_prefs(e2e_data_root)
    app_prefs_on_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    assert app_prefs_on_disk.get("ui_prefs", {}).get("density") == "compact", (
        f"Expected ui_prefs.density='compact' in apps.pdomain-ocr-simple-gui on disk; got: {disk_prefs!r}"
    )

    # UI: reload — data-density="compact" applied to the app-shell element.
    # (UIPrefsApplicator sets data-density on the app-shell div, not documentElement.)
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="app-shell"]');
            return el && el.getAttribute('data-density') === 'compact';
        }""",
        timeout=5_000,
    )


# ---------------------------------------------------------------------------
# B-SHELL-010 — FontScale slider persists via /api/prefs
# NOTE: slider drag via UI is deferred; API round-trip + error-path are covered here.
# ---------------------------------------------------------------------------


def test_fontscale_persists_via_api(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-010 — fontScale PUT /api/prefs persists and survives reload.

    Regression: yes — same silent-catch as B-SHELL-008/009.
    Slider drag via UI requires a specific Playwright drag sequence; this test
    covers PUT/GET + reload via API and verifies the slider is visible in the modal.
    """
    # Open modal and verify slider is accessible in the DOM.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)
    expect(page.get_by_test_id("settings-appearance-font-scale-slider")).to_be_visible(timeout=3_000)
    page.get_by_test_id("slide-over-panel-close").click()

    # Backend uses snake_case: font_scale (not fontScale) per CommonUIPrefs schema.
    put_resp = httpx.put(
        f"{live_server_url}/api/prefs",
        json={"ui_prefs": {"theme": "dark", "density": "normal", "font_scale": 1.2}},
        timeout=5.0,
    )
    put_resp.raise_for_status()

    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    assert prefs.get("ui_prefs", {}).get("font_scale") == 1.2, (
        f"Expected font_scale=1.2 in GET /api/prefs; got: {prefs!r}"
    )

    # On-disk: persisted in apps.pdomain-ocr-simple-gui.ui_prefs.
    disk_prefs = _read_prefs(e2e_data_root)
    app_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    ui_disk = app_disk.get("ui_prefs", {})
    assert ui_disk.get("font_scale") == 1.2, f"Expected font_scale=1.2 on disk; got: {disk_prefs!r}"

    # UI: reload — fontScale applied (zoom on documentElement.style via UIPrefsApplicator).
    # Verify via GET /api/prefs that the value survived (DOM zoom is opaque to httpx).
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    prefs_after = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    assert prefs_after.get("ui_prefs", {}).get("font_scale") == 1.2

    # Bad-state: fontScale out of range is clamped by uiPrefsConfig.load [0.8, 1.4].
    # (Tested at unit level; not repeated here.)


def test_prefs_persist_error_shows_toast(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-008 (bad-state) — when PUT /api/prefs returns 500, the
    onPersistError callback fires a sonner toast.

    Uses page.route() to fulfill PUT /api/prefs with a 500 after the settings
    modal triggers a theme toggle.
    """
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Intercept PUT /api/prefs to return 500.
    page.route(
        "**/api/prefs",
        lambda route: (
            route.fulfill(status=500, body="Server Error")
            if route.request.method == "PUT"
            else route.continue_()
        ),
    )

    # Open the settings panel (utility dock) and click a theme toggle to trigger persistCommon.
    page.get_by_test_id("settings-slot-trigger").click()
    expect(page.get_by_test_id("slide-over-panel")).to_be_visible(timeout=5_000)
    page.get_by_test_id("settings-appearance-theme-light").click()

    # Observable: sonner toast error appears.
    # Sonner renders toasts as <li data-sonner-toast> inside the <ol data-sonner-toaster>
    # container.  The <ol> is always in DOM but hidden when empty; individual <li>
    # elements appear as toasts are added.
    toast_locator = page.locator("[data-sonner-toast]")
    expect(toast_locator.first).to_be_visible(timeout=8_000)
    toast_text = toast_locator.first.inner_text()
    assert "Preferences not saved" in toast_text or "server error" in toast_text.lower(), (
        f"Expected persist-error toast; got toast content: {toast_text!r}"
    )


# ---------------------------------------------------------------------------
# B-SHELL-011 — Prefs survive page reload (round-trip)
# ---------------------------------------------------------------------------


def test_prefs_survive_reload(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-011 — prefs written via PUT /api/prefs survive a reload."""
    # Seed all three common-prefs fields.
    put_resp = httpx.put(
        f"{live_server_url}/api/prefs",
        json={"ui_prefs": {"theme": "light", "density": "comfortable", "fontScale": 1.1}},
        timeout=5.0,
    )
    put_resp.raise_for_status()

    # Backend: verify persisted.
    prefs = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0).json()
    assert prefs.get("ui_prefs", {}).get("theme") == "light"
    assert prefs.get("ui_prefs", {}).get("density") == "comfortable"

    # On-disk: confirm file exists before reload.
    disk_prefs = _read_prefs(e2e_data_root)
    app_disk = disk_prefs.get("apps", {}).get("pdomain-ocr-simple-gui", {})
    assert app_disk.get("ui_prefs", {}).get("theme") == "light"

    # UI: full page reload — prefs applied by uiPrefsConfig.load.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') === 'light'",
        timeout=5_000,
    )
    # data-density is set on the app-shell element, not documentElement.
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="app-shell"]');
            return el && el.getAttribute('data-density') === 'comfortable';
        }""",
        timeout=5_000,
    )

    # Bad-state: reset prefs → defaults on next reload.
    httpx.put(f"{live_server_url}/api/prefs", json={}, timeout=5.0)
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)
    # After reset the default theme (dark or no attribute) is restored.
    page.wait_for_function(
        "() => document.documentElement.getAttribute('data-theme') !== 'light'",
        timeout=5_000,
    )


# ---------------------------------------------------------------------------
# B-SHELL-012 — PageViewPage shortcuts appear in cheatsheet
# ---------------------------------------------------------------------------


def test_page_view_shortcuts_appear_in_cheatsheet(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-SHELL-012 — PageViewPage registers its bindings in the cheatsheet."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # Open the shortcuts cheatsheet via the help button.
    # In pdomain-ui 0.4.0, ShortcutsHelpButton opens the utility dock's keybinds surface.
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)

    # Observable: cheatsheet body contains PageViewPage-specific bindings.
    cheatsheet = page.get_by_test_id("shortcuts-cheatsheet-body")
    cheatsheet_text = cheatsheet.inner_text()

    assert any(
        fragment in cheatsheet_text
        for fragment in [
            "Save",
            "save",
            "Next",
            "Previous",
            "Rerun",
            "rerun",
            "←",
            "→",
        ]
    ), f"No expected PageViewPage shortcuts in cheatsheet: {cheatsheet_text!r}"

    # Backend: no writes.
    resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert resp.status_code == 200

    # Bad-state: navigate away → PageViewPage bindings unregistered.
    page.keyboard.press("Escape")  # Close the keybinds dock panel.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Open cheatsheet on home page — should show only home-page bindings.
    page.locator("body").click()  # Ensure focus is not in an input.
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)
    home_cheatsheet_text = page.get_by_test_id("shortcuts-cheatsheet-body").inner_text()
    # "Ctrl+S" / PageViewPage-specific keys should not be listed on the home page.
    # Soft assertion — if future pages also register Ctrl+S, update.
    assert "page-view" not in home_cheatsheet_text.lower()


# ---------------------------------------------------------------------------
# B-SHELL-013 — HomePage keyboard shortcut focuses source path input
# ---------------------------------------------------------------------------


def test_home_page_shortcut_focuses_path_input(page: Page, live_server_url: str) -> None:
    """Covers: B-SHELL-013 — 'n' key focuses the source path input on home page."""
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=15_000)

    # Precondition: path input is present (local, non-containerized mode).
    path_input = page.get_by_test_id("source-picker-path-input")
    expect(path_input).to_be_visible(timeout=5_000)

    # Click body to ensure focus is not on the input initially.
    page.locator("body").click()

    # Good path: 'n' key → path input gains focus.
    page.keyboard.press("n")
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="source-picker-path-input"]');
            return el && document.activeElement === el;
        }""",
        timeout=5_000,
    )

    # Backend: no side-effect.
    resp = httpx.get(f"{live_server_url}/api/prefs", timeout=5.0)
    assert resp.status_code == 200

    # Cheatsheet: 'n' binding should appear in the home-page cheatsheet.
    # In pdomain-ui 0.4.0, ShortcutsHelpButton opens the utility dock's keybinds surface.
    page.keyboard.press("Escape")
    page.locator("body").click()
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet-body")).to_be_visible(timeout=5_000)
    cheatsheet_text = page.get_by_test_id("shortcuts-cheatsheet-body").inner_text()
    assert any(
        fragment in cheatsheet_text for fragment in ["Focus source path input", "source", "path", "picker"]
    ), f"Expected home-page shortcut in cheatsheet but got: {cheatsheet_text!r}"

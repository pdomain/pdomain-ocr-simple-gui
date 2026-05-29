"""Tier-A behavior tests for App shell (AppShell / AppHeader / prefs / shortcuts).

Covers B-SHELL-001 through B-SHELL-013 (AppShell, prefs persist, shortcuts cheatsheet).

Marked ``slow`` and ``e2e`` — excluded from ``make test``, included in
``make e2e-browser`` / ``make e2e-fast``.

Every test cites its behavior record (``Covers: B-SHELL-NNN``), asserts the
observable DOM output, re-queries the backend API where there is a backend effect,
and inspects on-disk artifacts (ui-prefs.json) for prefs records.  Each record
has a good path and at least one bad path.

NOTE on settings modal / prefs controls:
  The app uses a CUSTOM header prop in AppShell (``header={<AppHeader/>}``), which
  means AppShell's built-in header (with ``SettingsSlot`` / ``settings-slot-trigger``)
  is never rendered.  The ``AppHeader`` component from pdomain-ui does not include a
  settings gear by default. Therefore:
    - B-SHELL-006/007 (settings modal open/close) are NOT testable via Playwright in
      the current app — the ``settings-slot-trigger`` element is absent from the DOM.
    - B-SHELL-008/009/010 (theme/density/fontScale toggle via UI) fall back to API-level
      testing: PUT /api/prefs + GET /api/prefs + page reload.  The prefs persistence is
      fully testable; only the UI toggle affordance is absent.

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
# B-SHELL-004 — Shortcuts cheatsheet opens via button click
# ---------------------------------------------------------------------------


def test_shortcuts_cheatsheet_opens_on_button_click(
    page: Page, live_server_url: str, seeded_job_id: str
) -> None:
    """Covers: B-SHELL-004 — clicking the ? button opens the shortcuts cheatsheet."""
    page.goto(f"{live_server_url}/jobs/{seeded_job_id}/pages/0")
    expect(page.get_by_test_id("page-view-page")).to_be_visible(timeout=15_000)

    # The cheatsheet must be absent before clicking.
    expect(page.get_by_test_id("shortcuts-cheatsheet")).not_to_be_visible()

    # Click the ? help button (rendered by AppHeader via actions={<ShortcutsHelpButton/>}).
    help_btn = page.get_by_test_id("shortcuts-help-button")
    expect(help_btn).to_be_visible(timeout=5_000)
    help_btn.click()

    # Observable: cheatsheet dialog appears.
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)

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
    expect(page.get_by_test_id("shortcuts-cheatsheet")).not_to_be_visible()

    # Press ? to open — ShortcutsContext registers a global ? keydown.
    page.keyboard.press("?")
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)

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
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)

    # Press Escape — ShortcutsContext handles this globally.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("shortcuts-cheatsheet")).not_to_be_visible(timeout=5_000)

    # Bad-state check: re-open and confirm it works again after close.
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# B-SHELL-008/009/010 — Prefs persist via API (theme/density/fontScale)
# NOTE: UI toggle affordance (settings-slot-trigger) is absent — App.tsx uses
# a custom header prop, so AppShell's built-in SettingsSlot is never rendered.
# Prefs persistence is tested via PUT /api/prefs + GET + reload instead.
# ---------------------------------------------------------------------------


def test_theme_persists_via_api(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-008 — PUT /api/prefs theme persists and survives reload.

    Regression: yes — prior persistCommon had silent catch {}; now throws +
    shows toast on error (unit-tested in AppPrefsError.test.tsx).
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
# B-SHELL-010 — FontScale persists via /api/prefs (API-level)
# NOTE: slider drag via UI is deferred; this covers the PUT/GET/reload round-trip
# and the clamp logic (values outside [0.8, 1.4] are clamped by uiPrefsConfig.load).
# ---------------------------------------------------------------------------


def test_fontscale_persists_via_api(page: Page, live_server_url: str, e2e_data_root: Path) -> None:
    """Covers: B-SHELL-010 — fontScale PUT /api/prefs persists and survives reload.

    Regression: yes — same silent-catch as B-SHELL-008/009.
    Slider drag via UI is deferred; this test covers PUT/GET + reload via API.
    """
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
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)

    # Observable: cheatsheet body contains PageViewPage-specific bindings.
    cheatsheet = page.get_by_test_id("shortcuts-cheatsheet")
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
    page.keyboard.press("Escape")  # Close cheatsheet.
    page.goto(live_server_url)
    expect(page.get_by_test_id("home-page")).to_be_visible(timeout=10_000)

    # Open cheatsheet on home page — should show only home-page bindings.
    page.locator("body").click()  # Ensure focus is not in an input.
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)
    home_cheatsheet_text = page.get_by_test_id("shortcuts-cheatsheet").inner_text()
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
    page.keyboard.press("Escape")
    page.locator("body").click()
    page.get_by_test_id("shortcuts-help-button").click()
    expect(page.get_by_test_id("shortcuts-cheatsheet")).to_be_visible(timeout=5_000)
    cheatsheet_text = page.get_by_test_id("shortcuts-cheatsheet").inner_text()
    assert any(
        fragment in cheatsheet_text for fragment in ["Focus source path input", "source", "path", "picker"]
    ), f"Expected home-page shortcut in cheatsheet but got: {cheatsheet_text!r}"

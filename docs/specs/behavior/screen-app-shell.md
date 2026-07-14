---
Status: active
Owner: CT
Created: 2026-05-30
Last verified: 2026-07-14
Kind: spec
---

# Behavior unit spec — App shell

## Adversarial Review

- **Stage:** post-implementation
- **Source:** 2026-07-14 docgraph migration; independent read-only review of current code, tests, history, and related docs.
- **Accepted findings:** The review compared the documented contract with current implementation and accepted the material deviations recorded in the architecture and authored context.
- **Effect on result:** Shipped behavior remains active; obsolete UI or workflow assumptions are not treated as current truth.
- **Implementation deviations:** The shared jobs dock and fixed job-level download buttons replaced parts of the earlier projected surfaces. Recent projects are written at job creation. Upload/edit/download coverage does not prove edited text is present in the exported ZIP.
- **Residual risks:** Per-page edits and reruns can leave the job output mirror stale; the download redesign remains deferred.

- **Unit type:** screen
- **Address:** shell / header (wraps every route)
- **Implementation:** `frontend/src/App.tsx` (AppShell + AppHeader from
  `@pdomain/pdomain-ui/shell`; ShortcutsProvider + useShortcuts from
  `@pdomain/pdomain-ui/hooks`; prefs via `uiPrefsConfig` callback object;
  active-jobs via `useActiveJobs` hook)
- **Backend / collaborators touched:** `routes/prefs.py` (GET/PUT `/api/prefs`),
  `routes/config.py` (GET `/api/config`), `routes/jobs.py` (GET `/api/jobs`)

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path.

> **NOTE — registry gap:**
>
> **Shortcuts:** `ShortcutsProvider`, `useShortcuts`, `ShortcutsHelpButton`
> from `@pdomain/pdomain-ui/hooks` and `@pdomain/pdomain-ui/shell` are present
> in the registry 0.2.2 build (verified). The `?` and Escape key handlers are in
> `ShortcutsContext-CAfy8e9D.js`. The `shortcuts-cheatsheet` testid is hardcoded
> in the pdomain-ui bundle but NOT exported from the testids catalog — aliased
> locally in `APP_TEST_IDS.shortcutsCheatsheet`.
>
> **Settings modal (B-SHELL-006/007):** `App.tsx` places `<SettingsSlot />` inside
> `AppHeader.actions` alongside `<ShortcutsHelpButton />`. `SettingsSlot` calls
> `useSettingsModal().openModal()` from `SettingsModalContext` provided by `AppShell`.
> Since `AppHeader` is a descendant of `AppShell` (rendered via the `header` slot),
> the context is available and the gear button opens the built-in settings modal.
> All B-SHELL-006/007/008/009/010 behaviors are now testable via real UI clicks.

### Selectors (confirmed against `frontend/src/lib/testids.ts` + pdomain-ui dist)

#### App-local testid constants (`APP_TEST_IDS`)

| Element | Selector | Note |
|---------|----------|------|
| App header outer `<header>` | `data-testid="app-header"` | `APP_TEST_IDS.appHeader` |
| Active-jobs count badge | `data-testid="jobs-pill-count"` | `APP_TEST_IDS.jobsPillCount` — only present when 1+ jobs running |
| Jobs dock surface | `data-testid="jobs-panel-body"` (inside `data-testid="utility-dock"`) | `PD_UI_TEST_IDS.JOBS_PANEL_BODY` — `JobsPill.onClick` calls `useUtilityDock().toggle("jobs")`, opening the shared dock's Jobs surface (`App.tsx:593`); there is no separate hover popover |
| Jobs right panel | `data-testid="right-panel"` + `data-testid="jobs-drawer"` | Rendered by pdomain-ui when the Jobs button is clicked |
| Shortcuts cheatsheet dialog | `data-testid="shortcuts-cheatsheet"` | `APP_TEST_IDS.shortcutsCheatsheet` — hardcoded in bundle, not in testids catalog |

#### pdomain-ui catalog (`PD_UI_TEST_IDS`)

| Element | Selector | Testids constant |
|---------|----------|-----------------|
| AppShell outer wrapper | `data-testid="app-shell"` | `PD_UI_TEST_IDS.APP_SHELL` |
| Header zone | `data-testid="app-shell-header"` | `PD_UI_TEST_IDS.APP_SHELL_HEADER` |
| Main zone | `data-testid="app-shell-main"` | `PD_UI_TEST_IDS.APP_SHELL_MAIN` |
| `?` shortcuts help button | `data-testid="shortcuts-help-button"` | `PD_UI_TEST_IDS.SHORTCUTS_HELP_BUTTON` |
| Settings gear trigger | `data-testid="settings-slot-trigger"` | `PD_UI_TEST_IDS.SETTINGS_SLOT_TRIGGER` |
| Settings modal container | `data-testid="settings-modal"` | `PD_UI_TEST_IDS.SETTINGS_MODAL` |
| Settings modal close button | `data-testid="settings-modal-close"` | `PD_UI_TEST_IDS.SETTINGS_MODAL_CLOSE` |
| Theme dark radio | `data-testid="settings-appearance-theme-dark"` | `PD_UI_TEST_IDS.SETTINGS_APPEARANCE_THEME_DARK` |
| Theme light radio | `data-testid="settings-appearance-theme-light"` | `PD_UI_TEST_IDS.SETTINGS_APPEARANCE_THEME_LIGHT` |
| Density compact | `data-testid="settings-appearance-density-compact"` | `PD_UI_TEST_IDS.SETTINGS_APPEARANCE_DENSITY_COMPACT` |
| Density normal | `data-testid="settings-appearance-density-normal"` | `PD_UI_TEST_IDS.SETTINGS_APPEARANCE_DENSITY_NORMAL` |
| Density comfortable | `data-testid="settings-appearance-density-comfortable"` | `PD_UI_TEST_IDS.SETTINGS_APPEARANCE_DENSITY_COMFORTABLE` |
| FontScale slider | `data-testid="settings-appearance-font-scale-slider"` | `PD_UI_TEST_IDS.SETTINGS_APPEARANCE_FONT_SCALE_SLIDER` |

#### API-only (no DOM selector available from this repo)

The prefs controls (theme/density/fontScale) **live entirely inside
pdomain-ui's AppShell**. They are DOM-addressable via the selectors above
(PD_UI_TEST_IDS.*), but there is no wrapper `data-testid` added in
`App.tsx`. The canonical test pattern for prefs persistence is:

1. Trigger the control (e.g. `SETTINGS_APPEARANCE_THEME_LIGHT`).
2. Re-query `GET /api/prefs` and assert `ui_prefs.theme === "light"`.
3. Reload and confirm the UI reflects the persisted value.

### On-disk artifacts

Prefs are stored by `pdomain-ops.suite.prefs.LocalFilePrefs` at:
`<PD_SUITE_DATA_DIR>/ui-prefs.json` (default: `~/.local/share/pdomain-suite/ui-prefs.json`).

The JSON has two top-level keys:

- `"common"` — `{theme, density, fontScale, ...}` (written by `write_common()`
  via `uiPrefsConfig.persistCommon`)
- `"apps"` → `"pdomain-ocr-simple-gui"` — app-specific prefs (written by
  `write_app()` via `uiPrefsConfig.persistApp`). The `AppPrefs` model stores
  `default_engine`, `default_language`, `recent_projects`, etc. here.

In e2e tests, prefs isolation is provided by the `reset_prefs` autouse fixture
(see `tests/conftest.py`), which wipes the adapter before each test.

---

### B-SHELL-001 — App loads and renders shell with config

- **Flow(s):** —
- **Trigger:** User navigates to `/` (page load / full browser refresh)
- **Preconditions:** Server running; frontend built and served
- **Observable output:** `data-testid="app-shell"` is visible;
  `data-testid="app-shell-header"` and `data-testid="app-shell-main"` are
  present; `data-testid="home-page"` is visible inside the main zone
- **Backend / side-effects:** `GET /api/config` → 200 `{mode, is_containerized,
  detected_device, gpu_available}` consumed by ConfigProvider; `GET /api/prefs`
  → 200 `AppPrefs` consumed by AppShell's `uiPrefsConfig.load`; no writes
- **Bad-state / error:** Server down → React renders shell but ConfigProvider
  stays in loading state; `data-testid="home-page"` shows "Loading…" indefinitely
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_app_shell_loads`

---

### B-SHELL-002 — Active-jobs count updates every 5 s

- **Flow(s):** —
- **Trigger:** One or more jobs enter `running` or `queued` state; the
  `useActiveJobs` hook fires on its 5-second refetch interval
- **Preconditions:** At least one job in `state==="running"` or `"queued"`
  exists in the backend
- **Observable output:** `data-testid="jobs-pill-count"` appears in the DOM
  showing the count of running/queued jobs; `data-testid="jobs-pill-pulse"` is
  present alongside it
- **Backend / side-effects:** `GET /api/jobs` is polled every 5 s; response
  filtered to `state==="running" || state==="queued"`; no writes
- **Bad-state / error:** All jobs complete / `GET /api/jobs` fails → count
  badge disappears; pill returns to idle (Package icon, no pulse dot)
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_active_jobs_count_badge_appears_with_running_job`

---

### B-SHELL-003 — Jobs button opens right-side jobs panel

- **Flow(s):** —
- **Trigger:** User clicks the jobs-pill button while 1+ jobs are active
- **Preconditions:** At least one job is running/queued
- **Observable output:** `data-testid="right-panel"` appears with a
  `data-testid="jobs-drawer"` inside; each job row shows the job's title,
  phase/progress message and progress percentage. Hovering the Jobs button
  alone does **not** open `jobs-pill-popover`, preventing stale hover surfaces
  from sticking after a job finishes.
- **Backend / side-effects:** No additional backend call on click; data is from
  the existing `useActiveJobs` cache (GET /api/jobs poll). Clicking a drawer
  row's "Open project" action navigates to `/jobs/<id>`.
- **Bad-state / error:** Jobs button hovered while active → no panel opens.
  Dismissing the drawer hides the right panel. All jobs complete / GET
  `/api/jobs` returns empty → count badge disappears.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_jobs_button_opens_right_jobs_panel`

---

### B-SHELL-004 — Shortcuts cheatsheet opens on `?` button click and `?` key

- **Flow(s):** —
- **Trigger:** User clicks the `?` button (`data-testid="shortcuts-help-button"`)
  in the header, OR presses the `?` key when focus is not in a text input
- **Preconditions:** App is loaded with `ShortcutsProvider` mounted
- **Observable output:** `data-testid="shortcuts-cheatsheet"` dialog appears;
  it lists the keyboard shortcuts registered by whichever screen is currently
  mounted (e.g. PageViewPage registers j/k/←/→, Ctrl+S, Ctrl+R, etc.)
- **Backend / side-effects:** None (purely client-side ShortcutsContext state:
  `openCheatsheet()` → `isOpen = true`)
- **Bad-state / error:** Clicking `?` when no screen bindings are registered
  (e.g. on the HomePage which only registers the `n` binding) → cheatsheet opens
  with just the home-page binding listed
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_shortcuts_cheatsheet_opens_on_button_click`,
  `tests/e2e/test_click_paths_app_shell.py::test_shortcuts_cheatsheet_opens_on_question_mark_key`
- **Note (registry gap):** `ShortcutsProvider` + `useShortcuts` from
  `@pdomain/pdomain-ui/hooks` and the `?` keydown handler in `ShortcutsContext`
  are present in the INSTALLED registry 0.2.2 bundle (verified). Local-dev
  symlink to pdomain-ui is not required for this behavior.

---

### B-SHELL-005 — Shortcuts cheatsheet closes on Escape

- **Flow(s):** —
- **Trigger:** Cheatsheet dialog is open; user presses Escape
- **Preconditions:** `data-testid="shortcuts-cheatsheet"` is visible (B-SHELL-004
  completed)
- **Observable output:** `data-testid="shortcuts-cheatsheet"` disappears from
  the DOM (dialog unmounts or is hidden)
- **Backend / side-effects:** None (ShortcutsContext: `closeCheatsheet()` →
  `isOpen = false`)
- **Bad-state / error:** No close control rendered → dialog can only be
  dismissed by Escape (fallback behavior of the underlying dialog primitive)
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_shortcuts_cheatsheet_closes_on_escape`

---

### B-SHELL-006 — Settings modal opens on gear click

- **Flow(s):** —
- **Trigger:** User clicks the gear icon (`data-testid="settings-slot-trigger"`)
  in the header
- **Preconditions:** App is loaded
- **Observable output:** `data-testid="settings-modal"` is visible; the
  Appearance tab is active (font-scale slider, theme and density controls visible)
- **Backend / side-effects:** None on open (settings-modal reads state already
  loaded by `uiPrefsConfig.load` at startup); no API call on modal open
- **Bad-state / error:** No bad-state for opening; the modal always renders
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_settings_modal_opens_on_gear_click`

---

### B-SHELL-007 — Settings modal closes on close button

- **Flow(s):** —
- **Trigger:** Settings modal is open; user clicks
  `data-testid="settings-modal-close"`
- **Preconditions:** `data-testid="settings-modal"` is visible (B-SHELL-006
  completed)
- **Observable output:** `data-testid="settings-modal"` disappears
- **Backend / side-effects:** None (modal state only)
- **Bad-state / error:** —
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_settings_modal_closes_on_close_button`

---

### B-SHELL-008 — Theme toggle persists via /api/prefs

- **Flow(s):** —
- **Trigger:** Settings modal is open; user clicks the Light theme radio
  (`data-testid="settings-appearance-theme-light"`)
- **Preconditions:** Current theme is Dark (default)
- **Observable output:** `data-theme="light"` attribute is applied to the
  document root element (visible CSS change — light background); the light
  radio is selected
- **Backend / side-effects:** `PUT /api/prefs` with body
  `{ui_prefs: {theme: "light", density: <current>, fontScale: <current>}}`
  → 200; prefs file `ui-prefs.json` `common.theme` is updated to `"light"`;
  on next page load, `GET /api/prefs` returns `ui_prefs.theme === "light"`
  and the shell re-applies the light theme
- **Bad-state / error (PUT fails):** A non-ok response from PUT /api/prefs
  now surfaces a sonner toast ("Preferences not saved — server error") instead
  of failing silently. On page reload the old theme (dark) is restored.
- **Tier(s):** A
- **Regression:** yes — prior code had `catch {}` (silent) and no `res.ok`
  check; fix adds `throw if !res.ok` + `onPersistError` → `toast.error(...)`
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_theme_persists_via_ui`,
  `tests/e2e/test_click_paths_app_shell.py::test_theme_persists_via_api`,
  `tests/e2e/test_click_paths_app_shell.py::test_prefs_persist_error_shows_toast`

---

### B-SHELL-009 — Density toggle persists via /api/prefs

- **Flow(s):** —
- **Trigger:** Settings modal is open; user clicks the Compact density radio
  (`data-testid="settings-appearance-density-compact"`)
- **Preconditions:** Current density is Normal (default)
- **Observable output:** `data-density="compact"` attribute is applied to the
  document root; the Compact option is selected in the modal
- **Backend / side-effects:** `PUT /api/prefs` with body
  `{ui_prefs: {theme: <current>, density: "compact", fontScale: <current>}}`
  → 200; `ui-prefs.json` `common.density` updated; on reload the compact
  density is re-applied
- **Bad-state / error:** Same error-surfacing as B-SHELL-008 — a failed PUT
  now shows a sonner toast; density reverts on reload
- **Tier(s):** A
- **Regression:** yes — same silent-catch regression as B-SHELL-008
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_density_persists_via_ui`,
  `tests/e2e/test_click_paths_app_shell.py::test_density_persists_via_api`

---

### B-SHELL-010 — FontScale slider persists via /api/prefs

- **Flow(s):** —
- **Trigger:** Settings modal is open; user drags the font-scale slider
  (`data-testid="settings-appearance-font-scale-slider"`) to a new value
- **Preconditions:** Current fontScale is 1.0 (default); new value is in
  range [0.8, 1.4]
- **Observable output:** CSS zoom is applied to the document root; the slider
  position reflects the new scale; text/UI elements appear visually larger or
  smaller
- **Backend / side-effects:** `PUT /api/prefs` with body
  `{ui_prefs: {theme: <current>, density: <current>, fontScale: <newValue>}}`
  → 200; `ui-prefs.json` `common.fontScale` updated; on reload the new scale
  is re-applied. The clamp [0.8, 1.4] is **frontend-only** (`uiPrefsConfig.load`
  at `App.tsx:72`); the backend stores whatever value is PUT and does not
  enforce the range.
- **Bad-state / error (slider out of range):** Values outside [0.8, 1.4] are
  clamped by `uiPrefsConfig.load` on load — a stored value of 2.0 is read back
  as 1.4
- **Bad-state / error (PUT fails):** Same error-surfacing as B-SHELL-008 — sonner
  toast; scale reverts on reload
- **Tier(s):** A
- **Regression:** yes — same silent-catch regression as B-SHELL-008/009
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_fontscale_persists_via_api`
  (slider visibility confirmed in the modal; Playwright drag-sequence for slider
  value change deferred — PUT/GET round-trip covered by this test + B-SHELL-011)

---

### B-SHELL-011 — Prefs survive page reload (round-trip)

- **Flow(s):** —
- **Trigger:** User changes theme/density/fontScale and then refreshes the page
- **Preconditions:** A prefs PUT has succeeded (B-SHELL-008/-009/-010); app
  reloaded
- **Observable output:** On reload, `GET /api/prefs` is called by
  `uiPrefsConfig.load`; the AppShell applies the persisted `theme`, `density`,
  and `fontScale` attributes before first render
- **Backend / side-effects:** `GET /api/prefs` → 200 with persisted values;
  no writes on load
- **Bad-state / error:** `GET /api/prefs` returns non-2xx or body parsing
  fails → `uiPrefsConfig.load` catches the error and returns the hardcoded
  defaults `{theme: "dark", density: "normal", fontScale: 1.0}`. Pref changes
  are silently lost (by design — load-time errors fall back to defaults; only
  persist-time errors are surfaced to the user).
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_prefs_survive_reload[chromium]`

---

### B-SHELL-012 — App-level shortcuts are screen-aware (PageViewPage)

- **Flow(s):** —
- **Trigger:** User navigates to `/jobs/:id/pages/:idx` (PageViewPage); then
  opens the shortcuts cheatsheet via the `?` button
- **Preconditions:** PageViewPage mounts and calls `useShortcuts(bindings)` with
  its bindings (←/→/j/k, Ctrl+S, Ctrl+R, Ctrl+Shift+R, Ctrl+Shift+T/J, Ctrl+D)
- **Observable output:** `data-testid="shortcuts-cheatsheet"` shows those
  bindings grouped under their label/group headings
- **Backend / side-effects:** None (ShortcutsContext aggregation is client-only)
- **Bad-state / error:** User navigates away from PageViewPage → bindings are
  unregistered by `useShortcuts` unmount cleanup; cheatsheet no longer shows
  PageViewPage-specific bindings
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_page_view_shortcuts_appear_in_cheatsheet`
- **Note (registry gap):** Same as B-SHELL-004.

---

### B-SHELL-013 — HomePage keyboard shortcut focuses source path input

- **Flow(s):** —
- **Trigger:** User is on the home page (`/`) and presses the `n` key with
  focus outside a text input
- **Preconditions:** App is in `local` mode (so the path input is rendered);
  `ShortcutsProvider` is mounted; focus is not inside an `<input>` or
  `<textarea>`
- **Observable output:** `data-testid="source-picker-path-input"` receives
  keyboard focus (browser focus outline visible); the cheatsheet lists
  "Focus source path input" under the "Home" group
- **Backend / side-effects:** None (purely client-side focus)
- **Bad-state / error (managed mode):** In managed mode the path input is not
  rendered → pressing `n` does nothing (no element to focus); the binding is
  still registered and listed in the cheatsheet, but the handler is a no-op
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_app_shell.py::test_home_page_shortcut_focuses_path_input`
- **Note (registry gap):** Same as B-SHELL-004.

---

## Known regressions

B-SHELL-008, B-SHELL-009, and B-SHELL-010 are all tagged `Regression: yes`.

**Root cause:** `persistCommon` and `persistApp` in `uiPrefsConfig` (App.tsx)
had a silent `catch {}` and never checked `res.ok`. A failed PUT /api/prefs
was invisible to the user; the pref change appeared to apply but reverted on
reload.

**Fix:** (a) Remove the internal `try/catch` wrapper from `persistCommon` and
`persistApp`; (b) throw after `if (!res.ok)`; (c) add
`onPersistError: handlePersistError` to `uiPrefsConfig`, where
`handlePersistError` calls `toast.error(...)` from sonner. `UIPrefsConfig`
already accepts the optional `onPersistError` callback (verified in registry
0.2.2 `shell.d.ts`).

Covered by unit tests in
`frontend/src/__tests__/AppPrefsError.test.tsx` and Tier-A e2e in
`tests/e2e/test_click_paths_app_shell.py`.

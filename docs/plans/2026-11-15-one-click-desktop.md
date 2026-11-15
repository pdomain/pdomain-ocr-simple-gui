---
Status: active
Owner: CT
Created: 2026-11-15
Last verified: 2026-11-15
Kind: plan
---

# One-click desktop implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

Install, launch, stop and safely uninstall OCR Simple GUI through desktop controls on Windows, macOS and Linux.

## Architecture

Keep FastAPI and React. Add app-owned storage, a single-instance native launcher,
server-owned browser leases, and native wrappers for tested installation and removal operations.

## Tech Stack

Python, React/TypeScript, WebSockets, POSIX shell, PowerShell and platform-native desktop controls.

**Spec:** [One-click desktop design](../specs/2026-11-15-one-click-desktop.md).

## Agent Index

- **Kind:** plan
- **Status:** active
- **Read when:** implementing or resuming the one-click desktop goal.
- **Search terms:** one-click, install, uninstall, desktop, lifecycle, migration, heartbeat.

## Global Constraints

- Preserve the guide worker's exclusive `gui-walkthrough` worktree.
- Keep source scans, specified output folders, other apps and shared dependencies intact.
- CuPy requires CUDA 13; compatible CUDA 12 PyTorch selection remains supported.
- Preserve explicit environment overrides and persistent headless operation.
- No pushes, releases, paid services or reboots without their required authorization.
- One full CI at a time; at most four test workers and two native OCR CPU threads.
- Every platform needs its own install/run/shutdown/uninstall evidence. Do not count mocks as native acceptance.

## Review Focus

- A last-tab disconnect during OCR must defer exit and preserve work.
- Two launchers racing must create only one authenticated instance.
- A migration failure or old custom jobs folder must never lose unrelated files.
- A last-app decision must account for installed but not yet registered suite apps.
- Browser install/focus restrictions must yield working fallback controls and honest instructions.

### Task 1: Make existing destructive operations safe

**Files:** `routes/jobs.py`, deletion tests, `uninstall.sh`, `tests/test_uninstall_sh.py`.

**Interfaces:** Job deletion consumes stored output mode and the configured managed root.
It removes only this job's owned managed mirror. Unix uninstall defaults to app-only removal.

- [x] Write failing tests for external outputs, source folders, symlinks, missing metadata and cancellation.
- [x] Add the containment/mode guard and move confirmation before uninstall side effects.
- [x] Prove unattended uninstall preserves uv and user data; run scoped Python/shell gates.

Evidence: 48 focused deletion tests; 14 uninstall tests each under Bash, dash and BusyBox ash.
Python lint/type checks and shellcheck/shfmt passed. Independent review and full CI passed.
Later native-test fixes still require a final CI run before commit.

### Task 2: Establish app-owned paths and safe migration

**Files:** new `src/pdomain_ocr_simple_gui/locations.py`, `app_preferences.py`, `migration.py`;
storage, preferences and upload/output root consumers; location/migration tests.

**Interfaces:** `get_locations()` returns effective config/data/state/cache paths and override sources.
An app preferences adapter separates this app's settings from suite-wide integration preferences.
Migration exposes plan, start and status operations with a server-owned activity guard.

- [x] Test platform defaults, all existing overrides, old roots, custom project folders and conflicting destinations.
- [x] Centralize resolution; copy and verify owned files before committing the new location.
- [x] Test failed copy, overlapping/symlink destinations, active jobs and stale settings; preserve old data on failure.

Evidence: the foundation passed 80 focused tests. Migration passed 19 tests. Those tests included
failed copies, source changes, parent-path overlap and empty-directory changes. Independent migration
review has no remaining findings. Native migration acceptance remains part of Task 6.

### Task 3: Add desktop instance and shutdown control

**Files:** new `desktop.py`, `lifecycle.py`, `routes/lifecycle.py`; entrypoint/lifespan wiring;
desktop/lifecycle tests. Reuse the reviewed held-socket port-selection work.

**Interfaces:** The desktop launcher owns startup locking and runtime discovery. The backend owns
instance identity, browser leases, active-operation counts and graceful shutdown. Headless mode opts out.

- [x] Test concurrent launch, wrong-instance responses, stale PID/port records and startup failure.
- [x] Implement authenticated single-instance reuse, browser show requests and observable startup errors.
- [x] Test two tabs, last-tab 30-second grace, 120-second initial grace, reconnect and active-operation deferral.

Source runtime evidence came from a headed Brave session in Linux gui-sandbox. It passed two tabs,
refresh, closing one tab, and a second launcher that reused the server and visible tab. Closing the
last tab stopped uvicorn after 30.76 seconds. The test used the fake OCR dispatcher and does not
establish installation or real OCR acceptance.

### Task 4: Add browser lifecycle and location controls

**Files:** new frontend lifecycle/session components and tests; settings panels/API hooks;
manifest and browser-install control where supported.

**Interfaces:** Frontend observes server-owned lifecycle and migration state. Each page has a unique
lease. Settings shows effective roots and explicit overrides; provider cache changes require restart.

- [x] Test mounting/reconnecting sessions, multiple tabs and Quit with active work.
- [x] Add session transport, Quit, reopen/recovery, app-data/cache controls and migration status.
- [ ] Validate browser-installed app handling where available and unsupported installation prompts; native launch/focus fallback and frontend gates have passed.

Full CI passed frontend lint, types and all 252 tests. A separate focus regression verifies that a
visible background page acknowledges a show request only after it has focus. The backend retains
one current show request; a focused review found no remaining issue.

### Task 5: Build graphical install, run and uninstall artifacts

**Files:** `installer/` native wrappers/build recipes; Windows/macOS desktop integration;
`uninstall.ps1`, shared removal helpers and installer/removal tests.

**Interfaces:** Native wrappers show progress/results and call the tested install/removal operations.
Launch icons call the desktop launcher without a terminal. Optional bundled wheels support exact local artifacts.

Windows produces `OCR-Simple-GUI-Setup.exe`, a graphical bootstrapper that invokes the bundled
PowerShell operations and reports failures with a Retry control. Install its launcher and removal
wrappers under `%LOCALAPPDATA%/Programs/pdomain-ocr-simple-gui/`, with Start menu app and uninstall
shortcuts. Run uses `pythonw` from the verified tool environment, never a visible console. Removal
keeps its own wrapper until tool removal succeeds and then removes only those wrapper files.

macOS produces `Install OCR Simple GUI.app`, `OCR Simple GUI.app` and `Uninstall OCR Simple GUI.app`.
The installer puts launch/removal bundles in `~/Applications/`; their native dialogs report progress,
cancel and retry. Linux produces `OCR-Simple-GUI-Installer.AppImage` using the existing wizard, with
app and uninstall desktop entries under the user applications directory and wrappers under the app's
user installation directory. Both launchers call the verified installed desktop entrypoint. All three
installers record exact owned wrapper paths in an app-owned installation manifest. Retry resumes
idempotently; never report success before validating the entrypoint and icon target.

Native acceptance must open each actual artifact, cancel once, install, run its app icon twice,
perform CPU OCR, close two tabs independently, relaunch and run its uninstall icon. Verify default
data retention, shortcut removal, error/retry behavior and that unrelated suite apps still run.

- [x] Build a working Windows and Linux graphical proof before signing or publication changes.
- [x] Add native macOS application bundles and all platform launch/uninstall entries.
- [x] Test Windows/Linux data retention, failure/cancellation, reinstall and conservative last-app cleanup.
- [ ] Complete the same native checks on macOS.

### Task 6: Verify the complete platform flows

**Files:** platform acceptance workflows/scripts; source-owned runtime tests and the goal inventory.

**Interfaces:** Each platform record names the artifact, installed version, observed controls,
real CPU OCR results, uninstall outcomes and retained files. Windows/macOS workflow triggers stay manual.

- [x] Run the final exact-source CI and independent code review; resolve all blocking findings.

- [x] Exercise actual Windows and Linux artifacts, including two tabs, relaunch, shutdown and uninstall.
- [ ] Run the native macOS flow when access permits; keep any unavailable acceptance or publication step incomplete.

Complete independent readability review before committing the documents.

The final exact-source CI passed 1,084 backend tests, 252 frontend tests and 131 browser tests, with no skipped backend cases.
It also passed smoke, packaging, lint, formatting, type and build checks. CI excludes real OCR acceptance;
the Windows and Linux native tests below provide that evidence. Independent code review has no remaining findings.

Windows native testing passed actual Setup installation, Open app, CPU OCR, editing, rerun and ZIP export.
The OCR fixture had an expected-word overlap of 1.0. Two tabs survived refresh; closing one preserved the other.
With every tab closed, an upload remained active for 35.17 seconds, then the backend exited after completion.
Total time from closing the last tab to exit was 35.57 seconds. A second native launch reused the same
backend but opened another tab when the existing browser did not acknowledge focus. This is the supported fallback.

Windows graphical uninstall stopped the running backend and removed the tool, native controls and both
Start menu shortcuts. The latest retest preserved all 63 tracked data/settings files byte for byte, retained
shared uv and cleared its uninstall marker. A complete rebuilt Setup then reinstalled without marker repair.
Its native Open app control reopened the migrated data, and installed modules matched the final source.
Native uninstall repeated the 63-file preservation and marker-clear checks on that complete build.

Windows testing first found an archive-marker collision, now fixed by extracting into a payload subdirectory.
Later partial installs came from Defender detections naming uv and `Behavior:Win32/SuspClickFix.F`.
The uv binary matched the official release hash. Opening local Setup directly through the Windows shell
succeeded with Defender enabled; no exclusion or protection change was made. An earlier unresponsive guest
recovered after the owner authorized its restart. The Linux host was not restarted.

Linux testing passed the AppImage's bare FUSE smoke check, GUI cancellation, fresh graphical installation,
and the installed desktop launch target. Real CPU OCR, editing, rerun and ZIP export passed in 27.5 seconds,
with expected-word overlap 1.0. Two tabs survived refresh. A second launch reused the backend and focused tab.
After every tab closed, an active upload remained protected for 35.04 seconds. It completed, and the backend
exited 1.15 seconds later, 36.15 seconds after the last tab closed.

Linux graphical uninstall stopped a relaunched backend, removed the tool, wrapper, manifest, both menu entries
and the known last-app suite registry. All 13 sampled data/settings files remained byte-identical. Shared uv
and base Python remained. The installed native controls were republished after fixing buttons hidden by short
windows. The complete rebuilt artifact includes the final fixes and suppresses internal finalizer JSON.
Its native launcher reopened the migrated project and recovered a stale record after sandbox expiry.
Native uninstall preserved all 24 tracked files, including an unknown shared suite file, plus uv and base Python.
It removed the backend, tool and controls and cleared its uninstall marker. Installed modules and wrapper matched final source.

Reinstall testing caught a Windows marker-cleanup defect after those initial removal checks.
The branch that retained shared suite files dropped the operation metadata needed to clear its own marker.
The finalizer now preserves that metadata for every outcome. It clears only the matching marker after the
app environment is gone. A remaining environment returns failure and keeps the marker and recovery files.
Both native wrappers also verify that uv removed the tool before reporting completion.
The finalizer and Unix-wrapper regressions cover retained suite files, false uv success, retry after removal,
and interrupted recovery-state writes. Recovery state now uses an atomic replacement. PowerShell failure
and retry tests passed separately. Windows component retesting and complete rebuilt Windows/Linux artifact retesting passed.

The latest installed Linux build also passed a data move through Settings. It copied one project,
preserved all 11 original data files byte for byte, and loaded the migrated job through the API.
Settings reported valid installed desktop-launcher and uv paths even though they were absent from PATH.
Windows Settings also migrated three projects, preserved all 31 original data files and loaded the copied jobs through the API.

New storage choices reject destinations inside the removable app environment or macOS app bundles. The check
covers data migration, job folders, output destinations and provider cache children, including symlink aliases.
Existing legacy locations remain readable so users can move data out. Uninstall checks effective roots, saved
model-cache choices and owned project output metadata before stopping the app or changing removal state.
Unsafe or unreadable configuration refuses removal and preserves the installation for recovery. Invalid paths
return domain errors before writes. An explicit NUL check makes rejection independent of platform path resolution.

The Linux fresh-install test found and fixed uv discovery under custom XDG paths. Bootstrap now checks the
download, installer exit and executable before recording ownership, and it leaves shell profiles alone.
Tk/Tcl libraries were extracted in scratch for this test; no system packages were installed. The native
macOS bundle builds, but its installation, dialogs, launch, shutdown and uninstall remain untested on macOS.
The manual macOS workflow now offers a current-checkout native test while retaining its published-CLI default.
Its driver checks actual bundle dialogs, CPU OCR, browser leases, uninstall and retained files. Twelve mocked
tests, lint, types and actionlint passed; native execution and AppleScript compilation remain unrun.
The workflow checks GUI permissions instead of changing them. It cannot prove downloaded-app quarantine,
signing or notarization behavior. Running it requires the unpublished feature branch to be available on GitHub.

### Task 7: Reconcile guidance and delivery

**Files:** architecture/current-state/usage references, installer instructions and shared coordination records.

- [x] Give the guide owner controls, supported platform commands and retained-file map through the shared coordination file.
- [x] Reconcile indexed docs and run strict docgraph. Preserve required metadata and headings.
- [ ] Report each platform's acceptance separately; seek rollout authorization only after a concrete reviewed result exists.

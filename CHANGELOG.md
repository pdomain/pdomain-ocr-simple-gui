---
Status: active
Owner: CT
Created: 2026-06-03
Last verified: 2026-11-14
Kind: reference
---

# Changelog

All notable changes to `pdomain-ocr-simple-gui` are documented here.

---

## [Unreleased]

---

## [0.5.6] — 2026-11-14

### GPU detection

- GPU detection reads newer NVIDIA drivers. Driver 615 prints
  `CUDA UMD Version: 13.4` where older drivers print `CUDA Version: 13.4`.
  `install.sh` and the installer engine matched only the old text, so a GPU
  machine got a CPU-only install.
- GPU installs work again. `install.sh` and the installer engine added the
  PyTorch CUDA index (`download.pytorch.org/whl/cuXXX`) as an extra index.
  That index also holds old copies of common packages, `packaging` 24.1 at
  most. uv took `packaging` from it, `pdomain-ops` needs `packaging` 26 or
  newer, and every GPU install failed with "No solution found". Both now pass
  `--torch-backend auto` to `uv tool install`, so uv sends only PyTorch
  packages to the PyTorch index. A CPU install passes no `--torch-backend`.
- If uv fails and mentions `--torch-backend`, `install.sh` tells you to run
  `uv self update` and try again. The packaged installer prints the same
  hint when a GPU install fails. uv honours `--torch-backend` in `uv tool`
  commands from 0.9.19. The installer already asks for uv 0.11.16 or newer.

### OpenCV

- OCR no longer breaks at random after an install. pdomain-book-tools
  required `opencv-contrib-python`, and python-doctr requires
  `opencv-python`. Both write the same `cv2/` folder, and uv installs them in
  parallel, so some installs ended with mixed files and OCR failed with
  `module 'cv2' has no attribute 'typing'`. pdomain-book-tools 0.31.3
  depends on `opencv-python` only, and this release pins it.
- To upgrade a manual install, add `--reinstall` to the `uv tool install`
  command. The installers already pass it.
- The README lists the X11 and OpenGL packages a Linux server or container
  needs. Without them, OCR and startup fail with `libxcb.so.1: cannot open
  shared object file`.
- Installer messages no longer say the `[gpu]` extra installs `opencv-cuda`.
  pdomain-book-tools dropped it from that extra in 0.31.0.

---

## [0.5.5] — 2026-11-14

### Windows fixes

Found by running the app on Windows 11 as a standard user, driven by
Playwright and Edge.

- Jobs open on Windows. Path checks compared paths as strings with a `/`
  separator, so every job id was rejected and `GET /api/jobs/<id>` returned
  400. ZIP uploads would also have been refused.
- The app starts when its output is redirected. A startup line with an emoji
  could not be encoded in Windows' cp1252 and stopped the app.
- Unknown `/api/*` paths return 404 JSON instead of the page HTML, so a
  missing route fails visibly instead of leaving the page waiting.
- When PyTorch cannot load, for example on Windows without the Microsoft
  Visual C++ Redistributable, DocTR is reported as unavailable with the reason
  and the download link. The home page shows it and DocTR jobs are refused.
- The home page explains a slow first start. On a cold Windows CPU start,
  loading the OCR runtime took 52 s.
- The app now requires pdomain-ops 0.12.5 or later. That release accepts
  Windows paths for installed apps, so the suite settings routes mount on
  Windows.

### Layout fixes

- The page view's button row now wraps inside the text panel. Before, it was
  wider than the panel on laptop screens such as 1280x720. A download click
  then scrolled the panel sideways and hid the OCR text.

---

## [0.5.4] — 2026-11-13

### Download fixes

- ZIP downloads now carry saved page edits and single-page reruns. Save and
  rerun refresh the output folder and both combined texts. Each page JSON
  keeps the engine text and word boxes, with the saved edit in `edited_text`.

### Release gate

- The release preflight, `just ci-slow`, now runs a real-OCR browser
  acceptance test on the CPU: upload, OCR, edit, Tesseract rerun, and ZIP
  export. A missing browser, model weight, or `tesseract` binary fails the
  release instead of skipping. `scripts/do-release.sh` pins the preflight.

---

## [0.5.3] — 2026-11-13

This entry also covers 0.5.1 and 0.5.2, which had no separate entries.

### Bug fixes

- The font-size setting now saves and is restored after a reload.
- Ctrl+R re-runs DocTR without Tesseract installed, and Ctrl+Shift+R no longer
  sends a Tesseract re-run the server would reject.
- Page viewer caches now go in the project directory. Page collection skips
  the `.viewer.png` copies older versions left in source folders.
- The CUDA setup link in the Compute panel opens the guide on GitHub.
- Setup no longer defaults Playwright to the old devcontainer path, and
  `just local-setup` clones siblings from the `pdomain` organization.

### Tooling and dependencies

- Just replaces the Make task runner. Read-only lint/format checks, frontend
  typecheck and knip, locked setup, and strict docgraph are part of the gate.
- Dependency refresh pins book-tools to 0.31.0, raises contracts to at least
  0.3.1 and ops to at least 0.12.2, and locks the frontend UI at 0.13.0.
- Architecture now records current module ownership, storage publication,
  asynchronous test readiness, and SPA distribution. Completed handoffs are
  retired after promotion; deferred download redesign stays unbuilt.

### Tests

- The release smoke test now finds its OCR page fixture outside the old
  devcontainer: it tries `/workspaces/ocr-container`, then the sibling
  `pdomain-book-tools` checkout, then the in-repo page, and skips only when
  none exist.

- Browser tests wait for terminal jobs, positive word counts, and the actual
  404 response before asserting results. Browser and smoke servers read the
  kernel-assigned uvicorn port instead of reserving and releasing a port.

---

## [0.5.0] — 2026-11-06

### Added

- PP-DocLayout-Plus-L layout pass: the pipeline detects layout on the
  upright page and passes it to `Page.reorganize_page`. Word dropping stays
  off.
- Suite compute-device preference now governs OCR execution, with CUDA setup
  guidance and device warmup.
- Wider API token coverage: mutating suite routes, upload mutations, and
  per-id job status now require the token. A shared frontend `apiFetch`
  sends it as an optional bearer token, and a Settings field stores it.

### Fixed

- Security: path traversal blocked in the words route; zip extraction size
  capped and moved off the event loop.
- Dispatcher waits are bounded by `PDOMAIN_OCR_BATCH_TIMEOUT_S`; re-runs
  respect `PDOMAIN_MAX_CONCURRENT_JOBS`.
- Staged writes get their final mode before the rename; virtual environments
  are kept out of the source distribution; `make setup` rewrites stale git
  hooks.
- Prefs and recent-projects lock I/O runs off the event loop; the
  jobs-location setting creates its directory on save.

### Changed

- `make run` rebuilds the SPA only when it is missing or stale.
- Frontend major upgrades (Vite 8, Vitest 5, ESLint 10,
  `@pdomain/pdomain-ui` 0.12.1) and a Tailwind 4 migration.
- Dependencies: `pdomain-book-tools` pinned to `==0.30.1`;
  `pdomain-book-contracts>=0.2.0` added as a direct dependency;
  `pdomain-ops>=0.11.2`.
- GitHub workflows removed; `scripts/release-common.sh` now builds the
  artifacts and creates the GitHub Release locally. Releases no longer carry
  the AppImage installer. The workflow action pinning tool was dropped, and
  pre-commit Node hooks use the system Node.
- Unreachable job-cancellation state removed.

---

## [0.4.0] — 2026-06-10

- Atomic JSON writes (temp file plus `os.replace`).
- The prefs file lock is bounded so a held lock cannot hang the app; relies on
  the `pdomain-ops` 0.10.0 lock (`pdomain-ops>=0.10.0`).

## [0.3.10] — 2026-06-06

- Installer passes `--reinstall`, so re-running it upgrades instead of doing
  nothing.

## [0.3.9] — 2026-06-06

- Browser-only launch: the Qt/webview dependency and the `desktop` extra are
  dropped.

## [0.3.8] — 2026-06-06

- Installer wizard renders list-form commands as shell strings in its plan.

## [0.3.7] — 2026-06-06

- Installer uses `PD_INDEX_URL` and folds GPU handling into the tool install;
  wizard welcome copy matches its button label.

## [0.3.6] — 2026-06-06

- AppImage embeds the type2 static runtime (works with FUSE3 or without FUSE);
  installer detects the CUDA version for the torch wheel index.

## [0.3.5] — 2026-06-06

- First release with the Linux AppImage installer attached; `install.sh`
  prefers it on supported desktops.

## [0.3.4] — 2026-06-06

- Installer webview backend switched from WebKitGTK to Qt (PyQt6);
  `ci-against-main` check against `pdomain-book-tools` and `pdomain-ops`.

## [0.3.3] — 2026-06-06

- OCR model cache settings and endpoints; the shared compute settings panel;
  slow packaging regression tests added to the release gate.

## [0.3.2] — 2026-06-05

- Packaging: a wheel built from the sdist now includes the frontend SPA.

## [0.3.1] — 2026-06-05

- Packaging: the wheel ships the built frontend SPA. `--desktop` forwards
  `--port`; requires `pdomain-ops>=0.8.2`.

## [0.3.0] — 2026-06-05

- Curl-pipe `install.sh` with interactive confirm gates and a uv version
  guard, plus `uninstall.sh`.

## [0.2.1] — 2026-06-05

- basedpyright gate raised to warnings level, with all warnings fixed.

## [0.2.0] — 2026-06-05

- Gated install engine and a Linux AppImage GUI wizard over it.
- Job lifecycle and job-creation statecharts (backend and frontend), with
  statecharts included in behavior coverage.
- User-configurable jobs location; `PUT /api/prefs` merges instead of
  overwriting.
- Two explicit download buttons, a trash button that deletes a run, PWA web
  manifest, Compute and Updates panels, `--update` and `--desktop` CLI flags.
- Security: `%2f` traversal blocked in the SPA catch-all.
- `pdomain-ops>=0.8.0`.

## [0.1.5] — 2026-06-01

- Release workflow builds and publishes only, without the runner `ci-slow`
  gate.

## [0.1.4] — 2026-06-01

- CI fixes: honor `PLAYWRIGHT_BROWSERS_PATH` in the Makefile; use
  `typing_extensions.override` for Python 3.11.

## [0.1.3] — 2026-06-01

- CI fixes: set `PLAYWRIGHT_BROWSERS_PATH` on runners; resolve 38 basedpyright
  warnings.

## [0.1.2] — 2026-06-01

- Jobs panel opens from the header; Home hides the other source pickers once a
  source is chosen.

## [0.1.1] — 2026-06-01

- Test-only: ignore the `hf_xet.download_files` deprecation warning.

## [0.1.0] — 2026-06-01

- Security: API token auth and a concurrent-job cap; `SOURCE_ROOT_ALLOWLIST`
  restricts local source paths.
- Concurrent, batched page OCR; per-phase progress messages; JPEG 2000 and
  WebP input; text-normalization options; CPU/GPU chooser.
- Inline job config on Home, viewer toolbars and keyboard shortcuts, text or
  JSON chosen at download time, self-hosted fonts, copy-path button.
- Dynamic port selection; `PDOMAIN_OCR_FAKE_DISPATCHER` e2e seam; behavior
  coverage gate (`make behavior-coverage`); parallel `local-frontend-*` and
  `local-setup-py` targets.
- Renamed to the `pdomain` prefix: depends on `pdomain-ops` (was
  `pdomain-ocr-ops`). Floors: `pdomain-book-tools>=0.18.0` (batch
  auto-rotation), `pdomain-ops>=0.7.2`.
- `FakeStageDispatcher._page_dict_for` drops the pre-0.17 Page fields and
  matches the 0.17 `Page.to_dict()` output.

## [0.0.1] — 2026-05-26

First tagged release, published as GitHub Release artifacts. Covers milestones
M0–M8 below plus source handling (folder, single image, zip, and uploads),
three output modes with a results zip download, word overlays in the page
view, and the rename from `pd-ocr-simple-gui` to `pdomain-ocr-simple-gui`.
Depends on `pdomain-book-tools>=0.14.1` and `pdomain-ocr-ops>=0.2.2`.

---

## [0.1.0a0] — 2026-05-17

Pre-release version string in `pyproject.toml`; it was never tagged. The
first tag is `v0.0.1`. Initial alpha — drag-and-drop OCR app serving as the Phase 3
reference consumer for `pdomain-ocr-ops`' `LocalStageDispatcher`.

### M0 — Repo scaffold

- Directory skeleton, `.gitignore`, `LICENSE`, `README.md`
- `pyproject.toml` with `pdomain-book-tools` + `pdomain-ocr-ops` deps, entry point
  `pdomain-ocr-simple-gui`
- `Makefile` with `install`, `lint`, `typecheck`, `test`, `smoke`,
  `frontend-build`, `ci` targets
- `.github/workflows/ci.yml` running `make ci AI=1` on push/PR
- `CLAUDE.md` + workspace agent definition

### M1 — FastAPI backend

- Pydantic models: `ProjectSpec`, `PageResult`, `ProjectStatus`, `AppPrefs`
- Sidecar IO helpers (`storage.py`): read/write project JSON, per-page JSON +
  `.txt`, combined output, project listing and deletion
- Routes: `POST/GET/LIST/DELETE /api/jobs`, `GET/PUT /api/pages`, prefs CRUD
- `__main__.py` CLI entry point with `--port`, `--host`, `--reload`,
  `--unregister-suite`, `--install-desktop-shortcut`, `--remove-desktop-shortcut`

### M2 — OCR pipeline

- `pipeline.py`: `collect_images()` + async `run_project()` driven by
  `LocalStageDispatcher`
- `register_default_stages()` wired at app startup (from `pdomain-ocr-ops`)
- Page state transitions: queued → running → done / error
- Per-page re-run and project re-run routes

### M3 — React frontend (Home screen)

- Vite + React + TypeScript scaffold with `@pdomain/pdomain-ui` wiring
- `AppShell` + React Router (Home / Results / PageView)
- `DropZone` with drag-and-drop, path input, Browse button, validation
- `RecentProjectsList` fetching from `GET /api/prefs`

### M4 — Job config dialog + results list

- `JobConfigDialog`: Radix Dialog with engine/language/output-dir fields,
  pre-filled from prefs, validates before submit
- `ResultsList`: live-polling progress bar (1s interval, stops on terminal state),
  page rows with status chips and text previews

### M5 — Per-page view

- `PageView` two-panel layout: `PageImageCanvas` + editable textarea
- Prev/next navigation, Save edits (`PUT /api/pages/:id/:idx/text`),
  success/error toast

### M6 — Per-page and project re-run

- "Re-run page ▾" dropdown (DocTR / Tesseract) in PageView toolbar
- "Re-run all" button in ResultsList; polling restarts after re-run
- Backend `POST /api/pages/:id/:idx/rerun` and `POST /api/jobs/:id/rerun`

### M7 — Suite integration

- `pdomain-suite.json` fragment (app_id, display_name, default_port, icon)
- `register_self()` called at startup via `pdomain-ocr-ops.suite`
- `/api/suite/*` and `/api/icons/<size>` routes mounted
- `--unregister-suite` CLI flag; desktop-shortcut flags raise `NotImplementedError`
- Placeholder PNG icons (16 / 24 / 32 / 48 / 64 / 128 / 256)

### M8 — CI gate, smoke test, release prep

- `make ci AI=1` runs lint → typecheck → test → smoke → frontend-build; exits 0
- `tests/smoke/test_e2e.py`: subprocess-based e2e test — starts server on a
  random port, POSTs a job with a real fixture image, polls until terminal state,
  asserts `.txt` output; marked `@pytest.mark.slow @pytest.mark.e2e`
- Excluded from `make test` (`-m "not slow"` via `addopts`); included in `make ci`
- Version confirmed `0.1.0a0` in `pyproject.toml`
- Release publishing is active. Releases are tag-derived via `hatch-vcs`,
  published as GitHub Release artifacts, and indexed by `pdomain-index-pip`.

---

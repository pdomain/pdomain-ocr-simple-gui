# Changelog

All notable changes to `pdomain-ocr-simple-gui` are documented here.

---

## [Unreleased]

### Dependencies

- Bumped `pdomain-book-tools` floor to `>=0.18.0` (batch auto-rotation support).
- Bumped `pdomain-ops` floor to `>=0.7.2`.
- `frontend/knip.json`: added `src/jsx-dev-runtime-shim.ts` to `ignore` list;
  the file is used via a vitest `resolve.alias` (not a direct import), so knip
  cannot trace the usage without this explicit exemption.

### Test doubles

- Removed stale pre-0.17 Page fields (`ocr_provenance`, `source`, `ocr_failed`,
  `rotation_applied`, `image_path`) from `FakeStageDispatcher._page_dict_for`.
  The fake now matches the real 0.17 `Page.to_dict()` output exactly.

---

## [0.1.0a0] — 2026-05-17

Initial alpha release — drag-and-drop OCR app serving as the Phase 3
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

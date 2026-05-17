# Changelog

All notable changes to `pd-ocr-simple-gui` are documented here.

---

## [0.1.0a0] — 2026-05-17

Initial alpha release — drag-and-drop OCR app serving as the Phase 3
reference consumer for `pd-ocr-ops`' `LocalStageDispatcher`.

### M0 — Repo scaffold

- Directory skeleton, `.gitignore`, `LICENSE`, `README.md`
- `pyproject.toml` with `pd-book-tools` + `pd-ocr-ops` deps, entry point
  `pd-ocr-simple-gui`
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
- `register_default_stages()` wired at app startup (from `pd-ocr-ops`)
- Page state transitions: queued → running → done / error
- Per-page re-run and project re-run routes

### M3 — React frontend (Home screen)

- Vite + React + TypeScript scaffold with `@concavetrillion/pd-ui` wiring
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

- `pd-suite.json` fragment (app_id, display_name, default_port, icon)
- `register_self()` called at startup via `pd-ocr-ops.suite`
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
- Actual publish to `pd-index-pip` is deferred pending that repo's publish
  workflow being bootstrapped (see `pd-index` rename plan)

---

> **Note:** Publish step (`uv tool install pd-ocr-simple-gui` from `pd-index-pip`)
> is blocked on `pd-index-pip` existing with a functional CI publish workflow.
> Tag `v0.1.0a0` and wheel upload will follow once the index is operational.

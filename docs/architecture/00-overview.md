---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-11-12
Kind: architecture
---

# pdomain-ocr-simple-gui — Architecture Overview

**Status:** Shipped. M0–M8 are complete. The verification milestone and the behavior-E2E pilot are complete.
**Last updated:** 2026-11-12

---

## 1. Purpose

This is a minimal drag-and-drop OCR web app. The user picks a folder of scanned images by path, drag-drop, or file upload. The user then picks an OCR engine, DocTR or Tesseract, runs OCR, and gets `.txt` output files.

It is the Phase 3 reference consumer. It validates `pdomain-ops`' `LocalStageDispatcher` and `register_default_stages()`.

It ships as a single Python wheel: `uv tool install pdomain-ocr-simple-gui`.

The default launch is `http://localhost:8004`.

The supported installer launches the browser application. Historical desktop extras and Qt launch instructions were removed. Installer tests require the plain package and reject a `desktop` extra.

---

## What this repo owns

This repo owns the local web app: the FastAPI routes, the React screens, the job storage, and the install path for this one package.

Shared OCR and layout stay in `pdomain-book-tools`.

Suite plumbing, preferences, and GPU dispatch stay in `pdomain-ops`.

Shared shell, jobs dock, and settings controls stay in `@pdomain/pdomain-ui`.

Labeling, training, and synthetic pages stay in their own repos.

Caller-controlled paths and IDs are untrusted.

Backend and frontend contracts stay aligned.

The open list, including work that should not be built here, is the [roadmap](../roadmap.md).

The decision is [preserved runtime boundaries](../decisions/2026-07-13-preserved-runtime-boundaries.md).

Specialized tests still keep their own HTTP clients when setup timing or isolation requires them.

Security behavior that ships today is in the source, the security tests, this overview, and the intent map.

The commit list for the test and security work is in [decisions](../context/decisions.md). It includes `d61dd42`, `c6af2ee`, `195c67d` through `b5c9fef`, `9afd500`, `ac3577a`, `e9aac52`, `db544d8`, `5c6f052`, `218b152`, and `398ed04`.

### Suite launcher tab isolation

The suite launcher belongs to `@pdomain/pdomain-ui`, not to this app. The locked package is 0.12.1.

It opens sibling apps with `window.open(url, "_blank", "noopener,noreferrer")`. A launched tab gets no `window.opener` handle back to this app. Upstream commit `562938d` added the isolation. `LauncherTile.test.tsx` asserts all three arguments.

This app's own anchors do not use `target="_blank"`. The exception is the external CUDA link in `CudaSetupGuidance.tsx`, which sets `rel="noopener noreferrer"`.

Evidence:

- Code: `frontend/package.json` has `@pdomain/pdomain-ui` at `^0.12.1`. `frontend/pnpm-lock.yaml` resolves 0.12.1. The installed bundle `node_modules/@pdomain/pdomain-ui/dist/shell-BfHbj-R0.js` contains `window.open(n.url, "_blank", "noopener,noreferrer")`. Upstream `pdomain-ui` `src/shell/LauncherTile.tsx` is at commit `562938d`.
- Tests: upstream `pdomain-ui` `src/shell/LauncherTile.test.tsx` asserts `toHaveBeenCalledWith(url, '_blank', 'noopener,noreferrer')`. This app adds no duplicate test because it does not own `LauncherTile`.
- Verified: 2026-11-07, by source inspection of the lockfile, the installed bundle, and the upstream commit.

## Evidence

- Code: `src/pdomain_ocr_simple_gui/`, `frontend/src/`
- Tests: `tests/`, `frontend/src/**/__tests__/`, `tests/e2e/`
- Artifacts: the Vite build is packaged under `src/pdomain_ocr_simple_gui/frontend/`
- Verified: 2026-11-07 with source inspection
- Verified: 2026-11-12. `_transcode_for_browser` writes
  `<project_dir>/<name>.viewer.webp` or `<project_dir>/<name>.viewer.png`.
  `collect_images` skips an old `<name>.viewer.png` left beside a scan.
  `_IMAGE_SUFFIXES` includes `.png` and omits `.webp`.
  `tests/` has 47 top-level `test_*.py` files. `tests/e2e/` has 23, of
  which 21 are Tier A and 2 are Tier B.
  `docs/archive/` is gone (`a803e9c`).

## 2. Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn, Python 3.11+ |
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS 4 + `@pdomain/pdomain-ui` |
| OCR | `pdomain-book-tools` (DocTR / Tesseract runners) |
| Suite plumbing | `pdomain-ops` (`LocalStageDispatcher`, `PrefsAdapter`, `register_self`) |
| Storage | JSON sidecar files in `~/.local/share/pdomain-suite/simple-gui/projects/` |
| Tests | pytest + pytest-asyncio + httpx; Playwright e2e; vitest for frontend |

---

## 3. Where the code lives

- The Python package is `src/pdomain_ocr_simple_gui/`.
- The React source is `frontend/src/`.
- `make frontend-build` writes the packaged SPA to `src/pdomain_ocr_simple_gui/frontend/`.
- Tests live under `tests/`.

Per-module surfaces are in the [module map](module-map.md).

Request steps are in [runtime flows](runtime-flows.md).

The screen-by-screen contract that the coverage gate reads stays in `docs/specs/behavior/`.

---

## 4. API surface

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/config` | none | Runtime config (deploy mode, engine caps, CUDA) |
| `POST` | `/api/jobs` | token | Create project + enqueue OCR job |
| `GET` | `/api/jobs` | token | List recent projects |
| `GET` | `/api/jobs/{id}` | token | Get project status (for polling) |
| `DELETE` | `/api/jobs/{id}` | token | Delete project + files |
| `POST` | `/api/jobs/{id}/rerun` | token | Re-run all pages |
| `GET` | `/api/jobs/{id}/download` | none | Stream job output as zip |
| `GET` | `/api/pages/{id}/{idx}` | none | Get page sidecar JSON |
| `GET` | `/api/pages/{id}/{idx}/image` | none | Stream source image |
| `PUT` | `/api/pages/{id}/{idx}/text` | token | Save edited OCR text |
| `POST` | `/api/pages/{id}/{idx}/rerun` | token | Re-run OCR on single page |
| `GET` | `/api/pages/{id}/{idx}/words` | none | Word overlays (bbox + confidence) |
| `GET` | `/api/prefs` | token | Read app prefs (recent projects, defaults) |
| `PUT` | `/api/prefs` | token | Update app prefs |
| `POST` | `/api/uploads` | token | Upload image files or zip |
| `DELETE` | `/api/uploads/{id}` | token | Delete uploaded source |
| `GET` | `/api/models/cache` | token | DocTR model cache status |
| `POST` | `/api/models/precache` | token | Pre-download DocTR models |
| `GET` | `/api/health` | none | Health check (Playwright fixture) |
| `GET` | `/api/self/icons/{size}` | none | Icon PNG by pixel size |
| `GET/…` | `/api/suite/*` | middleware | Suite routes (mounted by pdomain-ops) |
| `GET` | `/{full_path:path}` | none | SPA catch-all (serves index.html) |

`token` means the `require_token` FastAPI dependency in `auth.py`.

When `PDOMAIN_API_TOKEN` is unset or empty, the dependency no-ops. Local dev is then open.

Suite mutating methods use `suite_token_middleware` on method and prefix, not a fixed path allowlist. Those methods are `POST`, `PUT`, `PATCH`, and `DELETE` under `/api/suite/`.

The SPA sends the token through `frontend/src/api/apiFetch.ts`. Every API call reads `localStorage["pdomain.apiToken"]`. When that value is set, the call adds `Authorization: Bearer <token>`.

Operators set, view, and clear the token from **Settings > API Token** in `frontend/src/components/ApiTokenSettings.tsx`. The view is masked.

Setting the same `pdomain.apiToken` key from the browser console remains a documented headless fallback for setups with no browser session. See `docs/runbooks/install.md`.

`POST /api/jobs` and `POST /api/jobs/{id}/rerun` share an in-process `asyncio.Semaphore`. `PDOMAIN_MAX_CONCURRENT_JOBS` sizes it. The default is 3. Those routes return **429** when the semaphore is full.

Single-page page rerun does not take this semaphore.

---

## 5. OCR pipeline

`pipeline.py`:

1. `collect_images(source_path)` accepts a file or a directory. It filters PNG, JPEG, TIFF, and JPEG 2000 suffixes, and it skips an old `<name>.viewer.png` copy. The result is sorted.
2. `run_project(spec, dispatcher, status_callback)` is async. It splits pages into chunks of `spec.batch_pages`. The default is 8. It calls `dispatcher.run_ocr_batch(req)` per chunk. It runs the PP-DocLayout-Plus-L layout pass and `Page.reorganize_page` on each page, in `layout_pass.py`. It writes the sidecar and the `.txt` through storage helpers. It calls `status_callback` for progress. Batch waits are bounded by `PDOMAIN_OCR_BATCH_TIMEOUT_S`, using `asyncio.wait_for`. Cancelling the await does not stop the executor thread. The predictor-cache lock is upstream in pdomain-ops. Details are in [`runtime-flows.md`](runtime-flows.md#2-ocr-pipeline-execution).

The FastAPI lifespan wires `LocalStageDispatcher` from `pdomain-ops` at app startup, with `device_resolver=_resolve_device`. That resolver calls `resolve_effective_device(prefs, APP_ID)` on each dispatch. Settings device changes then apply on the next OCR stage, without a restart.

`register_default_stages()` registers DocTR and Tesseract runners.

When `PDOMAIN_OCR_FAKE_DISPATCHER` is set, lifespan swaps in `FakeStageDispatcher`. It logs a production warning that OCR output is fake. The swap is for test isolation only.

---

## 6. Storage layout

```text
~/.local/share/pdomain-suite/simple-gui/projects/{project_id}/
  project.json            ProjectSpec + ProjectStatus (state, pages, timestamps)
  pages/<page_name>.json  Page sidecar (DocTR export dict + text, words, edits)
  pages/<page_name>.txt   Extracted or edited text per page
  combined.txt            All pages joined
```

The output mirror, the jobs-meta sidecar, and the viewer caches are documented in [runtime flows](runtime-flows.md#storage-paths-summary). The viewer caches are `<project_dir>/<name>.viewer.webp` and `<project_dir>/<name>.viewer.png`.

`collect_images` skips an old `<name>.viewer.png` left beside a scan. Deleting those leftover files is an owner decision on the [roadmap](../roadmap.md).

---

## 7. Suite integration

On startup, `__main__.py` calls `pdomain_ops.suite.bootstrap_spa()`. That calls `register_self()`, which writes an entry into `~/.local/share/pdomain-suite/installed.toml`. Sibling suite apps can then show this app in their launcher.

The launcher hides when no siblings are installed.

`pdomain-suite.json` inside the wheel package provides the registration metadata: `app_id`, `display_name`, `package`, `default_port`, `icon`.

Suite HTTP routes mount under the real `app_id` `pdomain-ocr-simple-gui`, from `constants.APP_ID`, not the ops default `"unknown"`.

Prefs use a shared adapter. Suite device/update routes and app routes hit the same `LocalFilePrefs` instance, and they honor `PD_SUITE_DATA_DIR` at call time.

On startup, the app migrates a stranded `apps["unknown"].compute_device` into the real app section. The migration is best-effort.

---

## 8. Frontend screens

| Screen | Route | Component | Notes |
|--------|-------|-----------|-------|
| Home | `/` or `/new-job` | `HomePage` | `SourcePicker` + `JobConfigInline` + `RecentProjectsList` |
| Results | `/jobs/:id` | `ResultsPage` | Live-polls `/api/jobs/:id`; per-page rows; two managed download buttons |
| Page view | `/jobs/:id/pages/:idx` | `PageViewPage` | `PageViewerWithZoom` + editable textarea + save/rerun |
| Help | `/help/tesseract` | `TesseractHelpPage` | Tesseract engine setup guide |

All screens live inside `<AppShell deployMode="local" launcherSlot="header">` from `@pdomain/pdomain-ui`. `ComputeStateWarmup`, in `App.tsx`, prefetches device info on mount.

Job config is inline on the home page, in `JobConfigInline`, not a modal dialog.

Managed-mode downloads after success expose two fixed actions: images+text, and images+text+JSON. They are not include-filter checkboxes. Both hit the job-level download API and zip the **output mirror**.

Edited-page truth separation is still deferred.

---

## 9. Test strategy

- **Unit + integration:** Route tests use pytest with `httpx.AsyncClient`. Storage tests use `tmp_path`. These tests make no real filesystem side effects outside fixtures. Shared fixtures are in `tests/conftest.py`. Test data is in `tests/factories.py`. `tests/` has 47 top-level test files: routes, models, storage, pipeline, layout pass, sources, output, security, statechart, packaging, CLI, and smoke checks.
- **Frontend:** Component and hook tests use vitest and `@testing-library/react`.
- **Smoke:** `tests/smoke/test_e2e.py` is an httpx end-to-end test. It starts the server through a subprocess. It submits a real job. It asserts `state=succeeded` and a `.txt` output. It xfails when the job fails, for example on missing weights. It uses the first page image that exists: the dev-container `pdomain-book-tools` page, the sibling `../pdomain-book-tools` page, then the in-repo `tests/e2e/fixtures/known_good_page.png`. It skips only when none exists.
- **Browser e2e, Tier A:** 21 files under `tests/e2e/`, excluding `test_real_ocr_pipeline.py` and `test_real_ocr_rerun.py`. They run in Playwright on Chromium with the fake-dispatcher `live_server` fixture. Behavior-asserting tests cite stable IDs from `docs/specs/behavior/screen-*.md` and `flows.md`. They boot with `PD_SUITE_DATA_DIR` under a pytest tmp tree. They assert the path is tmp-like before launch, so prefs-reset fixtures cannot wipe real suite data.
- **Behavior coverage gate:** `make behavior-coverage` runs `scripts/behavior_coverage.py`. It matches the IDs declared in `docs/specs/behavior/*.md` against citations in `tests/`. It rewrites `docs/specs/behavior/coverage.md`. It fails on a citation with no declared ID or an uncovered regression record. `tests/test_behavior_coverage.py` unit-tests the scanner.
- **Browser e2e, Tier B:** `tests/e2e/test_real_ocr_pipeline.py` and `tests/e2e/test_real_ocr_rerun.py` use a real OCR engine. They are GPU-backed. They are opt-in through `make e2e-real-ocr`, which does not set the fake dispatcher.
- **SPA serving contract:** `tests/test_routes_root.py` uses a monkeypatch and a `tmp_path` fake `index.html`. It always runs, even without a built frontend.

---

## 10. Build + release

```sh
make build   # frontend-build, then uv build --sdist and uv build --wheel
```

`make release-patch`, `make release-minor`, or `make release-major` attaches the wheel and sdist to a GitHub Release. `pdomain-index-pip`'s `scripts/publish-index.sh` then publishes them to its GitHub Pages PEP 503 index. The steps are in [`docs/runbooks/release.md`](../runbooks/release.md).

---

## 11. Further reading

- Module-level reference: `docs/architecture/module-map.md`
- Runtime flows for job creation, the OCR pipeline, page save, and download: `docs/architecture/runtime-flows.md`
- Open work, and work that belongs in another repo:
  [`docs/roadmap.md`](../roadmap.md)
- Deployment and packaging boundaries that remain deferred:
  [`docs/context/intent-map.md`](../context/intent-map.md)
- Decisions that preserve the minimal-consumer, test-isolation, and
  distribution-verification boundaries:
  [`docs/decisions/2026-07-13-preserved-runtime-boundaries.md`](../decisions/2026-07-13-preserved-runtime-boundaries.md)
- Former GitHub issue ledger, for implemented backlog provenance:
  [`docs/context/github-issue-migration-ledger.md`](../context/github-issue-migration-ledger.md)
- Historical spec: workspace `docs/specs/2026-05-17-pdomain-ocr-simple-gui-design.md`

## Evidence (2026-07-19 architecture refresh)

- Code: `auth.py`, `app.py`, `pipeline.py`, `routes/jobs.py`, `routes/pages.py`,
  `routes/uploads.py`, `sources/local_path.py`, `frontend/src/api/apiFetch.ts`
- Tests: `tests/test_security_auth_token.py`, `tests/test_security_source_allowlist.py`,
  `tests/test_uploads.py`, `tests/test_app_suite_mount.py`,
  `tests/test_e2e_conftest_guard.py`, `frontend/src/api/__tests__/apiFetch.test.ts`
- Verified: 2026-07-19 source inspection after completed-issue migration repair

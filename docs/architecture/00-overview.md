---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-07-14
Kind: architecture
---

# pdomain-ocr-simple-gui — Architecture Overview

**Status:** Shipped (M0–M8 complete; verification milestone and behavior-E2E pilot complete)
**Last updated:** 2026-07-14

---

## 1. Purpose

A minimal drag-and-drop OCR web app. The user picks a folder of scanned images
(by path, drag-drop, or file upload), picks an OCR engine (DocTR or Tesseract),
runs OCR, and gets `.txt` output files. Phase 3 reference consumer that validates
`pdomain-ops`' `LocalStageDispatcher` and `register_default_stages()`.

Ships as a single Python wheel: `uv tool install pdomain-ocr-simple-gui`.
Default launch: `http://localhost:8004`.

The supported installer launches the browser application. Historical desktop
extras and Qt launch instructions were removed; installer tests require the
plain package and reject a `desktop` extra.

---

## Migration evidence and deviations

The shared fixture, fake-dispatcher, browser-E2E, behavior-contract, and
statechart systems shipped in commits `d61dd42`, `c6af2ee`, and `195c67d`
through `b5c9fef`. The final test design is less absolute than its original
audit plan: specialized tests retain inline clients when setup timing or
isolation requires them.

Most security findings from the 2026-05-22 scan were addressed across commits
`9afd500`, `ac3577a`, `e9aac52`, `db544d8`, `5c6f052`, `218b152`, `398ed04`,
and later hardening. One residual finding remains upstream: the shared
`@pdomain/pdomain-ui` launcher must add `noopener,noreferrer` to its
`window.open` call. Current security truth lives in the source, security tests,
this architecture, and the intent map rather than the retired scan.

## Evidence

- Code: `src/pdomain_ocr_simple_gui/`, `frontend/src/`
- Tests: `tests/`, `frontend/src/**/__tests__/`, `tests/e2e/`
- Artifacts: the Vite build is packaged under `src/pdomain_ocr_simple_gui/frontend/`
- Verified: 2026-07-14 with source inspection and `make ci AI=1`

## 2. Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn, Python 3.11+ |
| Frontend | React 19 + Vite + TypeScript + `@pdomain/pdomain-ui` |
| OCR | `pdomain-book-tools` (DocTR / Tesseract runners) |
| Suite plumbing | `pdomain-ops` (`LocalStageDispatcher`, `PrefsAdapter`, `register_self`) |
| Storage | JSON sidecar files in `~/.local/share/pdomain-suite/simple-gui/projects/` |
| Tests | pytest + pytest-asyncio + httpx; Playwright e2e; vitest for frontend |

---

## 3. Repo layout

```text
pdomain-ocr-simple-gui/
  src/pdomain_ocr_simple_gui/
    __main__.py        CLI entry: pdomain-ocr-simple-gui [--port N] [--host H]
    app.py             FastAPI app + lifespan (prefs, dispatcher, suite, auth middleware)
    auth.py            require_token dependency + suite_token_middleware
    models.py          Pydantic: ProjectSpec, ProjectStatus, PageResult, AppPrefs
    storage.py         Sidecar read/write helpers (project dirs, .txt output)
    pipeline.py        collect_images() + run_project() OCR orchestration
    _testjobs.py       Test job factories (used by testing/ and e2e fixtures)
    routes/
      config.py        GET /api/config
      downloads.py     GET /api/jobs/{id}/download
      jobs.py          POST/GET /api/jobs  GET/DELETE /api/jobs/{id}
                       POST /api/jobs/{id}/rerun
      model_cache.py   GET /api/models/cache  POST /api/models/precache
      pages.py         GET /api/pages/{id}/{idx}  GET .../image
                       PUT .../text  POST .../rerun
      prefs.py         GET /api/prefs  PUT /api/prefs
      uploads.py       POST /api/uploads  DELETE /api/uploads/{id}
      words.py         GET /api/pages/{id}/{idx}/words
    output/
      config.py        Output directory config helpers
    sources/
      local_path.py    Local path source validation
      uploaded_files.py Upload-backed source handling
    statecharts/
      job_lifecycle.py Backend job lifecycle state machine
    runtime/
      container_detect.py  Container vs host environment detection
      mode.py              App deployment mode (local / managed)
      ocr_engines.py       Engine capability introspection
    testing/
      fake_dispatcher.py   FakeStageDispatcher for test isolation
    scripts/
      purge_test_jobs.py   Dev utility: purge jobs with test_ prefix
    pdomain-suite.json     Suite registration metadata
    icons/                 PNG icons (16–256 px) + simple-gui.ico
    frontend/              Built React SPA (populated by `make frontend-build`)
  frontend/
    src/
      App.tsx              React Router root + AppShell wiring + ComputeStateWarmup prefetch
      pages/
        HomePage.tsx         Source picker + inline job config + recent projects
        ResultsPage.tsx      Live-polling job status + per-page rows
        PageViewPage.tsx     Image canvas + editable textarea + save/rerun
        TesseractHelpPage.tsx  Help page for Tesseract engine setup
      components/
        CudaSetupGuidance.tsx    CUDA installation guidance panel
        JobConfigInline.tsx      Inline job config form (engine, language, output dir)
        JobsLocationSettings.tsx Jobs output location preference settings
        ModelCacheSettings.tsx   DocTR model pre-cache controls
        OutputConfigPanel.tsx    Output directory + format configuration
        PageViewerWithZoom.tsx   Zoomable page image viewer wrapper
        RecentProjectsList.tsx   Recent projects from /api/prefs
        SourcePicker.tsx         Source selection (local path / upload / drag-drop)
      api/
        useOcrJob.ts        React Query hooks for job CRUD + polling
      statecharts/
        jobCreationMachine.ts    XState job creation state machine
        jobCreationBehavior.ts   Side effects wired to the machine
        jobCreationTypes.ts      Shared types for the machine
      runtime/
        ConfigContext.tsx    Runtime config (deploy mode, engine caps) context
        ocrEngines.ts        Engine capability constants
      lib/
        testids.ts           Stable test-ID constants for Playwright
  tests/
    conftest.py              Shared fixtures (AsyncClient, tmp project roots, auth)
    factories.py             Shared test data factories
    test_models.py           Pydantic model validation
    test_storage.py          Storage read/write helpers
    test_routes_jobs.py      Job CRUD + state machine routes
    test_routes_pages.py     Page sidecar, image, text, rerun routes
    test_routes_prefs.py     Prefs GET/PUT
    test_routes_root.py      SPA serving contract tests
    test_config_route.py     /api/config
    test_download_route.py   /api/jobs/{id}/download
    test_model_cache_route.py  /api/models/cache + precache
    test_uploads.py          /api/uploads POST/DELETE
    test_words_route.py      /api/pages/{id}/{idx}/words
    test_pipeline.py         collect_images + run_project
    test_output_config.py    Output config helpers
    test_sources_local_path.py  Local path source validation
    test_sources_uploaded.py    Upload source handling
    test_job_lifecycle_statechart.py  Backend statechart unit tests
    test_security_*.py       Auth token, project-id, source allowlist, SPA catchall
    test_fake_dispatcher.py  FakeStageDispatcher contract
    test_suite.py            Suite registration
    test_entrypoint.py       CLI entry point
    test_behavior_coverage.py  Behavior-coverage gate (spec IDs vs e2e citations)
    test_container_detect.py   Container detection
    test_jobs_location_pref.py  Jobs location preference
    test_prefs_lock_timeout.py  Prefs lock timeout
    test_storage_isolation_guard.py  Storage isolation guard
    test_pwa_manifest.py     PWA manifest
    test_cuda_setup_doc.py   CUDA guidance content
    test_ocr_engines.py      Engine introspection
    test_smoke.py            Miscellaneous smoke checks
    test_app_env_seam.py     App environment seam
    test_cli_*.py            CLI desktop + update
    test_dynamic_port.py     Dynamic port assignment
    test_hf_xet_dep_probe.py HuggingFace xet dependency probe
    test_e2e_conftest_guard.py  E2E conftest guard
    test_suite_device_update_routes.py  Suite device update routes
    test_testjobs.py         Test job factory
    test_git_master_sources.py  Git master source validation
    test_purge_test_jobs.py   Purge-test-jobs script
    packaging/test_install_engine.py  Wheel install + launch integration
    test_packaging.py        Wheel contents check
    test_install_sh.py       install.sh smoke
    test_uninstall_sh.py     uninstall.sh smoke
    test_update_github_actions.py  GitHub Actions update check
    smoke/test_e2e.py        httpx end-to-end (marked slow; xfails without weights)
    e2e/                     Playwright browser e2e (25 files)
      conftest.py            live_server fixture (fake + real-OCR variants)
      test_browser_smoke.py  App loads + routing
      test_click_paths_*.py  Per-screen behavior-asserting Tier-A tests
      test_flows.py          Cross-screen flow tests (F-* IDs)
      test_real_ocr_*.py     Tier-B real-OCR tests (opt-in; GPU)
      test_jobs_panel.py     Jobs panel behavior
      test_preview.py        Preview behavior
      test_desktop_panels.py Desktop panel behavior
```

---

## 4. API surface

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/config` | none | Runtime config (deploy mode, engine caps, CUDA) |
| `POST` | `/api/jobs` | token | Create project + enqueue OCR job |
| `GET` | `/api/jobs` | token | List recent projects |
| `GET` | `/api/jobs/{id}` | none | Get project status (for polling) |
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
| `POST` | `/api/uploads` | none | Upload image files or zip |
| `DELETE` | `/api/uploads/{id}` | none | Delete uploaded source |
| `GET` | `/api/models/cache` | token | DocTR model cache status |
| `POST` | `/api/models/precache` | token | Pre-download DocTR models |
| `GET` | `/api/health` | none | Health check (Playwright fixture) |
| `GET` | `/api/self/icons/{size}` | none | Icon PNG by pixel size |
| `GET/…` | `/api/suite/*` | middleware | Suite routes (mounted by pdomain-ops) |
| `GET` | `/{full_path:path}` | none | SPA catch-all (serves index.html) |

"token" = `require_token` FastAPI dependency (`auth.py`). Suite routes use
`suite_token_middleware` applied via `BaseHTTPMiddleware`.

---

## 5. OCR pipeline

`pipeline.py`:

1. `collect_images(source_path)` — accepts file or dir; filters `.png/.jpg/.tiff`; sorted.
2. `run_project(spec, dispatcher, status_callback)` — async; iterates pages; calls
   `dispatcher.run_stage("ocr", ...)` per page; writes sidecar + `.txt` via storage
   helpers; calls `status_callback` for progress.

`LocalStageDispatcher` (from `pdomain-ops`) is wired at app startup via the FastAPI
lifespan. `register_default_stages()` registers DocTR and Tesseract runners.

---

## 6. Storage layout

```text
~/.local/share/pdomain-suite/simple-gui/projects/{project_id}/
  spec.json           ProjectSpec
  status.json         ProjectStatus (state, page counts, timestamps)
  page_{n:04d}.json   PageResult sidecar per page (DocTR export dict)
  page_{n:04d}.txt    Extracted text per page
  combined.txt        All pages joined
```

---

## 7. Suite integration

On startup, `pdomain_ops.suite.register_self()` writes an entry into
`~/.local/share/pdomain-suite/installed.toml` so sibling suite apps can show
this app in their launcher. The launcher hides when no siblings are installed.

`pdomain-suite.json` inside the wheel package provides the registration metadata:
`app_id`, `display_name`, `package`, `default_port`, `icon`, `description`.

---

## 8. Frontend screens

| Screen | Route | Component | Notes |
|--------|-------|-----------|-------|
| Home | `/` or `/new-job` | `HomePage` | `SourcePicker` + `JobConfigInline` + `RecentProjectsList` |
| Results | `/jobs/:id` | `ResultsPage` | Live-polls `/api/jobs/:id`; per-page rows |
| Page view | `/jobs/:id/pages/:idx` | `PageViewPage` | `PageViewerWithZoom` + editable textarea + save/rerun |
| Help | `/help/tesseract` | `TesseractHelpPage` | Tesseract engine setup guide |

All screens live inside `<AppShell deployMode="local" launcherSlot="header">`
from `@pdomain/pdomain-ui`. `ComputeStateWarmup` (in `App.tsx`) prefetches
device info and config state on mount.

Job config is inline on the home page (`JobConfigInline`), not a modal dialog.

---

## 9. Test strategy

- **Unit + integration:** pytest with `httpx.AsyncClient` for route tests;
  `tmp_path` for storage tests; no real fs side-effects outside fixtures.
  Shared fixtures in `tests/conftest.py`; test data in `tests/factories.py`.
  ~46 test files in `tests/` (routes, models, storage, pipeline, sources,
  output, security, statechart, packaging, CLI, smoke checks).
- **Frontend:** vitest + `@testing-library/react` for component and hook tests.
- **Smoke:** `tests/smoke/test_e2e.py` — httpx end-to-end; starts server via
  subprocess; submits a real job; asserts `state=done` (xfails on missing weights).
- **Browser e2e (Tier A):** `tests/e2e/` — 25 Playwright (Chromium) files; fake-dispatcher
  `live_server` fixture; behavior-asserting tests cite stable IDs from
  `docs/specs/behavior/screen-*.md` and `flows.md`.
- **Behavior coverage gate:** `tests/test_behavior_coverage.py` asserts all spec IDs
  are cited in e2e tests; run via `make behavior-coverage`.
- **Browser e2e (Tier B):** `tests/e2e/test_real_ocr_*.py` — real OCR engine,
  GPU-backed, opt-in via `make e2e-real-ocr`.
- **SPA serving contract:** `tests/test_routes_root.py` — monkeypatch + `tmp_path`
  fake `index.html`; always runs even without a built frontend.

---

## 10. Build + release

```sh
make frontend-build   # vite build → src/pdomain_ocr_simple_gui/frontend/
uv build              # wheel (requires populated frontend/)
```

Published to `pdomain-index-pip` (GitHub Pages PEP 503 index).

---

## 11. Further reading

- Module-level reference: `docs/architecture/module-map.md`
- Runtime flows (job creation, OCR pipeline, page save, download): `docs/architecture/runtime-flows.md`
- Deployment and packaging boundaries that remain deferred:
  [`docs/context/intent-map.md`](../context/intent-map.md)
- Decisions that preserve the minimal-consumer, test-isolation, and
  distribution-verification boundaries:
  [`docs/decisions/2026-07-13-preserved-runtime-boundaries.md`](../decisions/2026-07-13-preserved-runtime-boundaries.md)
- Historical spec: workspace `docs/specs/2026-05-17-pdomain-ocr-simple-gui-design.md`

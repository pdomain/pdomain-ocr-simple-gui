---
Status: active
Owner: CT
Created: 2026-06-14
Last verified: 2026-11-07
Kind: architecture
---

# pdomain-ocr-simple-gui — Module Map

**Last updated:** 2026-11-07

Per-module reference. Each entry gives a one-line responsibility and its
key public surface (types, functions, hooks). Derived from current source.

---

## Backend — `src/pdomain_ocr_simple_gui/`

### Top-level modules

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `app.py` | FastAPI app factory (route registration, suite route mount, auth middleware, static mount) and lifespan (prefs, dispatcher) | `create_app()` |
| `auth.py` | Token auth for mutating endpoints; suite middleware | `require_token` (Depends), `suite_token_middleware` |
| `models.py` | Pydantic data models | `ProjectSpec`, `ProjectStatus`, `PageResult`, `AppPrefs` |
| `storage.py` | Sidecar read/write; project directory management; atomic text writes | `get_projects_root()`, `read_project()`, `write_project()`, `read_page_sidecar()`, `write_page_sidecar()`, `write_txt()`, `write_combined_txt()`, `write_output_page_files()`, `list_projects()`, `validate_project_id()` |
| `pipeline.py` | Image collection + async OCR orchestration; DocTR sidecar building | `collect_images()`, `run_project()`, `build_sidecar_payload()`, `extract_words()`, `OCRDispatcher` (Protocol) |
| `layout_pass.py` | PP-DocLayout-Plus-L detection on the upright page, passed to `Page.reorganize_page` (word dropping off) | `reorganize_ocr_page()`, `LayoutSession`, `load_layout_detector()`, `detect_page_layout()` |
| `__main__.py` | CLI entry point — `pdomain-ocr-simple-gui [--port N] [--host H]`; registers with the suite through `bootstrap_spa()` before `uvicorn.run()` | `main()` |
| `_testjobs.py` | Test-job signature shared by `purge_test_jobs` and tests: e2e fixture id prefixes and a pytest-tmp source-path check | `TEST_JOB_PREFIX`, `TEST_JOB_PREFIXES`, `is_test_job()`, `is_test_source_path()` |

### `routes/`

| Module | Responsibility | Endpoints |
|--------|---------------|-----------|
| `config.py` | Runtime config (deploy mode, device, engine list, CUDA) | `GET /api/config` |
| `jobs.py` | Job CRUD + background OCR dispatch | `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`, `DELETE /api/jobs/{id}`, `POST /api/jobs/{id}/rerun` |
| `pages.py` | Per-page sidecar, image streaming, text save, single-page rerun | `GET /api/pages/{id}/{idx}`, `GET .../image`, `PUT .../text`, `POST .../rerun` |
| `prefs.py` | App preferences (recent projects, jobs location, output defaults) | `GET /api/prefs`, `PUT /api/prefs` |
| `uploads.py` | File upload source management | `POST /api/uploads`, `DELETE /api/uploads/{id}` |
| `downloads.py` | Job output zip download with content-type filter | `GET /api/jobs/{id}/download` |
| `words.py` | Word overlay extraction from page sidecars | `GET /api/pages/{id}/{idx}/words` |
| `model_cache.py` | DocTR model cache status + pre-download | `GET /api/models/cache`, `POST /api/models/precache` |

### `sources/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `local_path.py` | Validate and resolve a local filesystem path source against `SOURCE_ROOT_ALLOWLIST`; ZIP size/traversal checks | `LocalPathSource`, `get_allowlist()` |
| `uploaded_files.py` | Manage an uploaded-file-backed source directory | `UploadedFilesSource` |

### `output/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `config.py` | Resolve and validate output directory; output format config | `OutputConfig`, `resolve_output_dir()`, `OutputConfigError` |

### `statecharts/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `job_lifecycle.py` | Backend job lifecycle state machine; validate allowed transitions | `JobLifecycleMachine`, `transition_job_state()`, `assert_job_transition()`, `narrow_job_state()`, `aggregate_pages_state()`, `InvalidJobTransition` |

### `runtime/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `mode.py` | App deployment mode detection (local / managed) | `Mode` enum, `read_mode()` |
| `container_detect.py` | Detect whether running inside a container | `detect_containerized()` |
| `ocr_engines.py` | Tesseract/DocTR availability introspection | `OcrEngineStatus`, `detect_tesseract()`, `detect_ocr_engines()`, `is_engine_request_available()` |

### `testing/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `fake_dispatcher.py` | Deterministic fake `OCRDispatcher` for test isolation; every page returns one fixed text with full word geometry | `FakeStageDispatcher` |

### `scripts/`

| Module | Responsibility |
|--------|---------------|
| `purge_test_jobs.py` | Dev utility: remove leaked e2e test jobs (pytest-tmp source, legacy `e2etestjob-`-style id prefix, or empty degenerate job) from the projects, output, and jobs-meta roots; dry-run unless `--apply` |

---

## Frontend — `frontend/src/`

### Pages

| File | Route | Responsibility |
|------|-------|---------------|
| `pages/HomePage.tsx` | `/`, `/new-job` | Source picker + inline job config + recent projects |
| `pages/ResultsPage.tsx` | `/jobs/:id` | Live-polling job status; per-page rows with state |
| `pages/PageViewPage.tsx` | `/jobs/:id/pages/:idx` | Zoomable page image + editable OCR text + save/rerun |
| `pages/TesseractHelpPage.tsx` | `/help/tesseract` | Tesseract engine installation guide |

### Components

| File | Responsibility |
|------|---------------|
| `components/SourcePicker.tsx` | Tabbed source selection: local path / file upload / drag-drop |
| `components/JobConfigInline.tsx` | Inline job config form: engine, language, output dir |
| `components/CudaSetupGuidance.tsx` | CUDA installation guidance; always shown under the Settings > Compute panel |
| `components/JobsLocationSettings.tsx` | Jobs output location preference panel |
| `components/ModelCacheSettings.tsx` | DocTR model pre-cache status + trigger |
| `components/OutputConfigPanel.tsx` | Output destination selector: next to source, specified path, or managed |
| `components/PageViewerWithZoom.tsx` | Wraps the pdomain-ui `ArtifactViewer` in a CSS-transform zoom layer with fit-to-page default and zoom in/out |
| `components/RecentProjectsList.tsx` | Recent projects list from `/api/prefs` |
| `components/ApiTokenSettings.tsx` | Settings panel to view (masked), set, and clear the `pdomain.apiToken` localStorage key |

### API hooks — `api/`

| File | Responsibility | Key exports |
|------|---------------|-------------|
| `api/apiFetch.ts` | Shared fetch wrapper: reads `localStorage["pdomain.apiToken"]` and attaches `Authorization: Bearer` when set | `apiFetch()` |
| `api/useOcrJob.ts` | Polls `GET /api/jobs/:id` through pdomain-ui `useLongJob`, maps backend states to `LongJobStatus`, and keeps the raw job data | `useOcrJob()`, `OcrJobData`, `UseOcrJobResult`, `JobFetchError` |
| `api/config.ts` | Single fetch+parse site for `GET /api/config`, consumed by `ConfigContext` and `jobCreationMachine` | `fetchRuntimeConfig()`, `RuntimeConfig`, `OcrEngineConfig` |

### Statecharts — `statecharts/`

| File | Responsibility | Key exports |
|------|---------------|-------------|
| `statecharts/jobCreationMachine.ts` | XState v5 job creation state machine (source selection → config → submit) | `jobCreationMachine` |
| `statecharts/jobCreationBehavior.ts` | Maps job-creation steps to behavior-spec IDs (`B-HOME-*`) and appends them to a behavior trace | `JOB_CREATION_BEHAVIOR`, `JobCreationBehaviorId`, `appendBehaviorTrace()` |
| `statecharts/jobCreationTypes.ts` | Shared types for the machine context and events | `RuntimeProfile`, `ChosenSource`, `JobForm`, `JobCreationContext`, `JobCreationEvent` |

### Runtime — `runtime/`

| File | Responsibility | Key exports |
|------|---------------|-------------|
| `runtime/ConfigContext.tsx` | Provides `RuntimeConfig` (mode, engine caps) via React context; wraps the app | `ConfigProvider`, `useConfig()`, `useConfigStatus()` |
| `runtime/ocrEngines.ts` | Engine availability checks against `/api/config`, DocTR fallback, and Tesseract language normalization | `EngineId`, `engineIsAvailable()`, `availableEngineOptions()`, `normalizeEngine()`, `normalizeEngineLanguage()` |

### App root

| File | Responsibility |
|------|---------------|
| `App.tsx` | `BrowserRouter` + `AppShell` + route tree; `ComputeStateWarmup` prefetches device info on mount |

### Utilities — `lib/`

| File | Responsibility |
|------|---------------|
| `lib/testids.ts` | Stable test-ID constants for Playwright; defines the driver contract |

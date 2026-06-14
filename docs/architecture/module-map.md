# pdomain-ocr-simple-gui — Module Map

**Last updated:** 2026-06-14

Per-module reference. Each entry gives a one-line responsibility and its
key public surface (types, functions, hooks). Derived from current source.

---

## Backend — `src/pdomain_ocr_simple_gui/`

### Top-level modules

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `app.py` | FastAPI app factory, lifespan (prefs, dispatcher, suite wiring, auth middleware, route registration, static mount) | `create_app()` |
| `auth.py` | Token auth for mutating endpoints; suite middleware | `require_token` (Depends), `suite_token_middleware` |
| `models.py` | Pydantic data models | `ProjectSpec`, `ProjectStatus`, `PageResult`, `AppPrefs` |
| `storage.py` | Sidecar read/write; project directory management; atomic text writes | `get_projects_root()`, `read_project()`, `write_project()`, `read_page_sidecar()`, `write_page_sidecar()`, `write_txt()`, `write_combined_txt()`, `write_output_page_files()`, `list_projects()`, `validate_project_id()` |
| `pipeline.py` | Image collection + async OCR orchestration; DocTR sidecar building | `collect_images()`, `run_project()`, `build_sidecar_payload()`, `extract_words()`, `OCRDispatcher` (Protocol) |
| `__main__.py` | CLI entry point — `pdomain-ocr-simple-gui [--port N] [--host H]` | — |
| `_testjobs.py` | Test job factories for fake jobs in dev/test | — |

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
| `local_path.py` | Validate and resolve a local filesystem path source | `LocalPathSource`, `get_allowlist()` |
| `uploaded_files.py` | Manage an uploaded-file-backed source directory | `UploadedFilesSource` |

### `output/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `config.py` | Resolve and validate output directory; output format config | `OutputConfig`, `resolve_output_dir()`, `OutputConfigError` |

### `statecharts/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `job_lifecycle.py` | Backend job lifecycle state machine; validate allowed transitions | `JobLifecycleMachine`, `transition_job_state()`, `assert_job_transition()`, `InvalidJobTransition` |

### `runtime/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `mode.py` | App deployment mode detection (local / managed) | `Mode` enum, `read_mode()` |
| `container_detect.py` | Detect whether running inside a container | `detect_containerized()` |
| `ocr_engines.py` | Tesseract/DocTR availability introspection | `OcrEngineStatus`, `detect_tesseract()`, `detect_ocr_engines()`, `is_engine_request_available()` |

### `testing/`

| Module | Responsibility | Key public surface |
|--------|---------------|-------------------|
| `fake_dispatcher.py` | In-memory fake `OCRDispatcher` for test isolation; controllable pass/fail | `FakeStageDispatcher` |

### `scripts/`

| Module | Responsibility |
|--------|---------------|
| `purge_test_jobs.py` | Dev utility: remove all jobs whose ID starts with `test_` |

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
| `components/CudaSetupGuidance.tsx` | CUDA installation guidance; shown when GPU is unavailable |
| `components/JobsLocationSettings.tsx` | Jobs output location preference panel |
| `components/ModelCacheSettings.tsx` | DocTR model pre-cache status + trigger |
| `components/OutputConfigPanel.tsx` | Output directory and format configuration |
| `components/PageViewerWithZoom.tsx` | Wraps `PageImageCanvas` with pinch/scroll zoom |
| `components/RecentProjectsList.tsx` | Recent projects list from `/api/prefs` |

### API hooks — `api/`

| File | Responsibility | Key exports |
|------|---------------|-------------|
| `api/useOcrJob.ts` | React Query hooks for job CRUD, live polling, page operations | `useOcrJob()`, `OcrJobData`, `UseOcrJobResult`, `JobFetchError` |

### Statecharts — `statecharts/`

| File | Responsibility | Key exports |
|------|---------------|-------------|
| `statecharts/jobCreationMachine.ts` | XState v5 job creation state machine (source selection → config → submit) | `jobCreationMachine` |
| `statecharts/jobCreationBehavior.ts` | Side effects wired to machine events (API calls, navigation) | — |
| `statecharts/jobCreationTypes.ts` | Shared types for the machine context and events | `RuntimeProfile`, `ChosenSource`, `JobForm`, `JobCreationContext`, `JobCreationEvent` |

### Runtime — `runtime/`

| File | Responsibility | Key exports |
|------|---------------|-------------|
| `runtime/ConfigContext.tsx` | Provides `RuntimeConfig` (mode, engine caps) via React context; wraps the app | `ConfigProvider`, `useConfig()`, `useConfigStatus()`, `RuntimeConfig` |
| `runtime/ocrEngines.ts` | Engine capability constants (display names, supported languages) | — |

### App root

| File | Responsibility |
|------|---------------|
| `App.tsx` | `BrowserRouter` + `AppShell` + route tree; `ComputeStateWarmup` prefetches device info on mount |

### Utilities — `lib/`

| File | Responsibility |
|------|---------------|
| `lib/testids.ts` | Stable test-ID constants for Playwright; defines the driver contract |

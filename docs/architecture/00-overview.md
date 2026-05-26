# pdomain-ocr-simple-gui — Architecture Overview

**Status:** Shipped (M0–M8 complete, verification milestone complete)
**Last updated:** 2026-05-22

---

## 1. Purpose

A minimal drag-and-drop OCR web app. The user drops a folder of scanned images,
picks an OCR engine (DocTR or Tesseract), runs OCR, and gets `.txt` output files.
Phase 3 reference consumer that validates `pdomain-ocr-ops`' `LocalStageDispatcher`
and `register_default_stages()`.

Ships as a single Python wheel: `uv tool install pdomain-ocr-simple-gui`.
Default launch: `http://localhost:8004`.

---

## 2. Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn, Python 3.11+ |
| Frontend | React 19 + Vite + TypeScript + `@pdomain/pdomain-ui` |
| OCR | `pdomain-book-tools` (DocTR / Tesseract runners) |
| Suite plumbing | `pdomain-ocr-ops` (`LocalStageDispatcher`, `PrefsAdapter`, `register_self`) |
| Storage | JSON sidecar files in `~/.local/share/pdomain-suite/simple-gui/projects/` |
| Tests | pytest + pytest-asyncio + httpx; Playwright e2e; vitest for frontend |

---

## 3. Repo layout

```text
pdomain-ocr-simple-gui/
  src/pdomain_ocr_simple_gui/
    __main__.py        CLI entry: pdomain-ocr-simple-gui [--port N] [--host H]
    app.py             FastAPI app + lifespan (prefs, dispatcher, suite)
    models.py          Pydantic: ProjectSpec, ProjectStatus, PageResult, AppPrefs
    storage.py         Sidecar read/write helpers (project dirs, .txt output)
    pipeline.py        collect_images() + run_project() OCR orchestration
    routes/
      jobs.py          POST /api/jobs  GET /api/jobs  GET /api/jobs/{id}
                       DELETE /api/jobs/{id}  POST /api/jobs/{id}/rerun
      pages.py         GET /api/pages/{id}/{idx}  GET .../image
                       PUT .../text  POST .../rerun
      prefs.py         GET /api/prefs  PUT /api/prefs
    pdomain-suite.json      Suite registration fragment
    icons/             PNG icons (16–256 px) + simple-gui.ico
    static/            Built React SPA (populated by `make frontend-build`)
  frontend/
    src/
      App.tsx          React Router root
      pages/
        HomePage.tsx         Screen 1: DropZone + RecentProjectsList
        ResultsPage.tsx      Screen 3: live-polling job status + page rows
        PageViewPage.tsx     Screen 4: image canvas + editable textarea
      components/
        DropZone.tsx          Drag-and-drop + Browse button
        JobConfigDialog.tsx   Screen 2: project config (name, engine, language, dirs)
        RecentProjectsList.tsx Recent projects from /api/prefs
  tests/
    test_models.py
    test_storage.py
    test_routes_jobs.py
    test_routes_pages.py
    test_routes_prefs.py
    test_routes_root.py     SPA serving contract tests
    test_suite.py
    test_pipeline.py
    test_entrypoint.py
    smoke/test_e2e.py       httpx end-to-end smoke (marked slow)
    e2e/                    Playwright browser e2e tests
      conftest.py           live_server fixture
      test_app_loads.py     Browser smoke: app loads + home-page visible
      test_job_flow.py      Happy path: submit job → results page → page view
```

---

## 4. API surface

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/jobs` | Create project + enqueue OCR job |
| `GET` | `/api/jobs` | List recent projects |
| `GET` | `/api/jobs/{id}` | Get project status (for polling) |
| `DELETE` | `/api/jobs/{id}` | Delete project + files |
| `POST` | `/api/jobs/{id}/rerun` | Re-run all pages |
| `GET` | `/api/pages/{id}/{idx}` | Get page sidecar JSON |
| `GET` | `/api/pages/{id}/{idx}/image` | Stream source image |
| `PUT` | `/api/pages/{id}/{idx}/text` | Save edited OCR text |
| `POST` | `/api/pages/{id}/{idx}/rerun` | Re-run OCR on single page |
| `GET` | `/api/prefs` | Read app prefs (recent projects, defaults) |
| `PUT` | `/api/prefs` | Update app prefs |
| `GET` | `/api/health` | Health check (used by Playwright fixture) |
| `GET` | `/api/suite/*` | Suite routes (mounted by pdomain-ocr-ops) |
| `GET` | `/api/icons/{size}` | Icon PNG by pixel size |
| `GET` | `/{full_path:path}` | SPA catch-all (serves index.html) |

---

## 5. OCR pipeline

`pipeline.py`:

1. `collect_images(source_path)` — accepts file or dir; filters `.png/.jpg/.tiff`; sorted.
2. `run_project(spec, dispatcher, status_callback)` — async; iterates pages; calls
   `dispatcher.run_stage("ocr", ...)` per page; writes sidecar + `.txt` via storage
   helpers; calls `status_callback` for progress updates.

`LocalStageDispatcher` (from `pdomain-ocr-ops`) is wired at app startup via the
FastAPI lifespan, with `register_default_stages()` registering DocTR and
Tesseract runners.

---

## 6. Storage layout

```text
~/.local/share/pdomain-suite/simple-gui/projects/{project_id}/
  spec.json           ProjectSpec
  status.json         ProjectStatus (state, page counts, timestamps)
  page_{n:04d}.json   PageResult sidecar per page
  page_{n:04d}.txt    Extracted text per page
  combined.txt        All pages joined
```

---

## 7. Suite integration

On startup, `pdomain_ocr_ops.suite.register_self()` writes an entry into
`~/.local/share/pdomain-suite/installed.toml` so sibling suite apps (pdomain-ocr-labeler-spa,
pdomain-prep-for-pgdp) can show this app in their launcher. The launcher inside
pdomain-ocr-simple-gui hides when no siblings are installed.

The `pdomain-suite.json` fragment (inside the wheel package) provides the registration
metadata: `app_id`, `display_name`, `package`, `default_port`, `icon`, `description`.

---

## 8. Frontend screens

| Screen | Route | Component |
|--------|-------|-----------|
| Home | `/` | `HomePage` — DropZone + RecentProjectsList |
| Job config | dialog | `JobConfigDialog` — Radix Dialog, engine/language/output-dir config |
| Results | `/jobs/:id` | `ResultsPage` — live-polls `/api/jobs/:id`; page rows with status pip |
| Page view | `/jobs/:id/pages/:idx` | `PageViewPage` — `PageImageCanvas` + editable textarea + save/rerun |

All screens live inside `<AppShell deployMode="local" launcherSlot="header">`
from `@pdomain/pdomain-ui`.

---

## 9. Test strategy

- **Unit + integration:** pytest with `httpx.AsyncClient` for route tests;
  `tmp_path` for storage tests; no real fs side-effects outside fixtures.
- **Frontend:** vitest + `@testing-library/react` for component tests.
- **Smoke:** `tests/smoke/test_e2e.py` — httpx end-to-end; starts server via
  subprocess; submits a real job; asserts `state=done` (xfails on missing model weights).
- **Browser e2e:** `tests/e2e/` — Playwright (Chromium); `live_server` session fixture;
  covers app load, job submission → results page, page-row click → page view.
- **SPA serving contract:** `tests/test_routes_root.py` — monkeypatch + `tmp_path`
  fake `index.html`; always runs even without built frontend.

---

## 10. Build + release

```sh
make frontend-build   # vite build → src/pdomain_ocr_simple_gui/static/
uv build              # wheel (requires populated static/)
```

Published to `pdomain-index-pip` (GitHub Pages PEP 503 index).

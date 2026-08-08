---
Status: active
Owner: CT
Created: 2026-06-14
Last verified: 2026-08-08
Kind: architecture
---

# pdomain-ocr-simple-gui — Runtime Flows

**Last updated:** 2026-08-08

Step-by-step reference for the major request flows. Each flow shows the
actors involved, the state transitions from `job_lifecycle.py`, and the
on-disk side effects.

---

## State machine reference

`statecharts/job_lifecycle.py` defines all valid job states and transitions.

| State | Meaning |
|-------|---------|
| `new` | Initial state (never persisted; exists only in the machine) |
| `queued` | Job accepted; background task queued |
| `running` | Pipeline is processing pages |
| `succeeded` | All pages processed successfully |
| `failed` | At least one page failed, or the whole job errored |

| Event | Transition |
|-------|-----------|
| `queue` | `new → queued` |
| `start` | `queued → running` |
| `succeed` | `running → succeeded` |
| `fail` | `queued → failed` or `running → failed` |
| `rerun_requested` | `succeeded/failed → queued` |

**No `cancel` event or `cancelled` state.** These were modeled but
unreachable — no route ever fired `cancel` — and were stripped
([ocr-container-meta#395](https://github.com/ConcaveTrillion/ocr-container-meta/issues/395)).
The wire-level Literals (`ApiJobState`, `ProjectStatus.state`,
`PageResult.state` in `models.py`/`storage.py`/`pipeline.py`/`routes/jobs.py`)
still list `"cancelled"` as a legal value, and `job_lifecycle.py` exports a
`narrow_job_state()` helper that validates a wire-level state against the
live machine states before it's used in a transition. This is intentional
compatibility with the frontend's shared `@pdomain/pdomain-ui` `JobState`
type, not an oversight — do not "helpfully" narrow those wire Literals to
match the machine; the backend must still be able to *receive* a stored
`"cancelled"` value even though it will never emit one again.

---

## 1. Job creation

**Actors:** frontend `jobCreationMachine`, `POST /api/jobs`, `routes/jobs.py`,
`sources/`, `storage.py`.

### Frontend state machine

Before the request reaches the backend, the XState `jobCreationMachine`
in `frontend/src/statecharts/jobCreationMachine.ts` drives the home-page
flow:

1. **`loadingConfig`** — fetches `GET /api/config`; branches to
   `choosingSource.managedServer`, `choosingSource.localContainer`, or
   `choosingSource.localHost` depending on the response.
2. **`choosingSource`** — user picks a local path or drops/selects files.
   - PATH_CHOSEN event → `configuringJob`
   - FILES_SELECTED event → `uploading`
3. **`uploading`** (upload path) — calls `POST /api/uploads`; on success,
   stores `upload_id` and moves to `configuringJob`.
4. **`configuringJob`** — user adjusts engine, language, output dir.
   SUBMIT_JOB event → `submittingJob`.
5. **`submittingJob`** — calls `POST /api/jobs`; on success, stores
   `project_id` and moves to `submitted` (final state).
   The React Router then navigates to `/jobs/:id`.

### Backend: `POST /api/jobs`

1. Check the concurrent-jobs semaphore (`_job_semaphore`). If it has no
   capacity, return 429.
2. Acquire the semaphore slot.
3. Detect `Mode` (local vs managed). Validate the engine + language combo.
4. Resolve the source:
   - `upload_id` path: `UploadedFilesSource` materializes the staged upload
     directory. `source_is_folder = False`.
   - `source_path` path (local mode only): `LocalPathSource` validates the
     path against the allowlist. `source_is_folder = path.is_dir()`.
5. Resolve the output directory via `OutputConfig` / `resolve_output_dir()`.
   Write `output_mode.json` sidecar in the jobs-meta dir.
6. Build a `ProjectSpec` (UUID project_id, engine, language, source_path,
   output_dir, normalizations, timestamps).
7. Transition `new → queued` via `assert_job_transition("new", "queue")`.
8. Write `project.json` (spec + status) atomically via `write_project()`.
   - **On-disk:** `<projects_root>/{project_id}/project.json` created.
9. Add the project to `prefs.recent_projects` (best-effort).
10. Enqueue `_pipeline_run_job_with_semaphore(spec)` as a FastAPI
    `BackgroundTask`.
11. Return 202 `{"project_id": "<uuid>"}`.

### Source-ingestion trust boundary

Local paths and uploaded files enter through different authority boundaries.
`LocalPathSource` is available only in local mode. It resolves a requested path
against `SOURCE_ROOT_ALLOWLIST` (colon-separated allowed roots) before reading a
file or directory. When the allowlist is set, the path must resolve to a strict
child of one root (symlink targets included via `resolve()`). When unset or
empty, any host path is accepted and lifespan logs a warning. Managed mode
accepts an upload identifier instead of granting arbitrary host-path access.

Both ZIP paths validate every member before extraction. A member must remain
inside its temporary or upload root after resolution. Local ZIP materialization
sums declared member sizes before extract and hard-caps total uncompressed size
at **2 GiB** (`SourceTooLarge`). Upload extraction caps at
`PD_OCR_SIMPLE_GUI_UPLOAD_MAX_EXTRACTED_BYTES` (default matches the compressed
upload max), returns **413** when over the cap, and runs extraction in
`asyncio.to_thread`. Uploaded filenames are reduced to their basename, upload
identifiers reject traversal characters, and extracted data stays under the
upload root.

In-process concurrent OCR work is capped by `PDOMAIN_MAX_CONCURRENT_JOBS`
(default **3**). `POST /api/jobs` and full-job `POST /api/jobs/{id}/rerun` return
**429** when no semaphore slot is free; the slot is released in
`_pipeline_run_job_with_semaphore`'s `finally`. Single-page rerun does not take
this semaphore.

These controls preserve the local-first convenience without treating browser
input as filesystem authority. Current evidence is in
`sources/local_path.py`, `routes/uploads.py`, `routes/jobs.py`,
`tests/test_sources_local_path.py`, `tests/test_uploads.py`, and
`tests/test_security_auth_token.py`.

---

## 2. OCR pipeline execution

**Actors:** `_pipeline_run_job` (background), `pipeline.run_project`,
`pdomain-ops LocalStageDispatcher`, `pdomain-book-tools`.

This flow runs in the background after job creation returns 202.

1. `collect_images(spec.source_path)` — scans the source directory for
   `.png`, `.jpg`, `.jpeg`, `.tiff`, `.jp2` and related extensions; returns
   a sorted list of `Path` objects. Returns `[]` if the path is missing.

2. Seed initial page list:
   - If no images found: transition `queued → failed` via
     `assert_job_transition(state, "fail")`. Write `project.json` with
     `state=failed` and an error message. Stop.
   - Otherwise: write `project.json` with one `PageResult(state="queued")`
     per image. **On-disk:** `project.json` updated.

3. Call `run_project(spec, dispatcher, _status_callback)`:
   a. Read `project.json`. Transition `queued → running` (event `start`).
      Write updated `project.json`. **On-disk:** `project.json` updated.
   b. Write warm-up progress message: "Loading OCR engine — first run may
      download ~200 MB to ~/.cache/huggingface".
   c. Divide images into chunks of `spec.batch_pages` (default 8).
   d. For each chunk:
      - Mark each page in the chunk `running`. Write `project.json`.
      - Read image bytes from disk.
      - Build `OcrBatchRequest(images, source_identifiers, engine, language, device)`.
      - Call `dispatcher.run_ocr_batch(req)`. This calls
        `LocalStageDispatcher` from `pdomain-ops`, which handles VRAM
        sizing, OOM backoff, and CPU fallback internally.
      - For each returned page dict:
        1. `Page.from_dict(raw)` + `page_obj.reorganize_page()` —
           clusters flat OCR words into lines/paragraphs/blocks
           (`pdomain-book-tools`). Falls back to raw dict on error.
        2. `apply_text_normalizations(text, ...)` — curly-quote and
           em-dash cleanup (`pdomain-book-tools`).
        3. `build_sidecar_payload(page_dict, text)` — augments the page
           dict with top-level `text`, `width`, `height`, and flat
           `words` array.
        4. `write_page_sidecar(spec, idx, payload)` — atomic write.
           **On-disk:** `<project_dir>/pages/<page_name>.json`.
        5. `write_txt(spec, idx, text)`.
           **On-disk:** `<project_dir>/pages/<page_name>.txt`.
        6. `write_output_page_files(spec, idx, ...)` — mirrors `.txt`
           and `.json` into `spec.output_dir`.
           **On-disk:** `<output_dir>/<stem>.txt`, `<output_dir>/<stem>.json`.
        7. Mark page `succeeded`. Write `project.json`.
      - On chunk exception: mark all chunk pages `failed`. Write
        `project.json`. Continue to next chunk.
      - Fire `_status_callback` after each chunk.

4. After all chunks:
   - Write progress message: "Writing outputs".
   - `write_combined_txt(spec, status)` — concatenates all per-page `.txt`
     files. **On-disk:** `<project_dir>/combined.txt`.
   - `write_output_combined_txt(spec, status)` — mirrors to `spec.output_dir`.
     **On-disk:** `<output_dir>/<name>.txt`.
   - Compute terminal event: `succeed` if all pages succeeded, `fail`
     otherwise.
   - Transition `running → succeeded` or `running → failed`. Write final
     `project.json`. **On-disk:** `project.json` updated with terminal state.

5. `_pipeline_run_job_with_semaphore` releases the semaphore slot in `finally`.

---

## 3. Single-page rerun

**Actors:** `POST /api/pages/{id}/{idx}/rerun`, `routes/pages.py`,
`LocalStageDispatcher`.

Unlike a full-project rerun, this flow runs **inline** in the request handler
(it does not use `BackgroundTasks` and **must not** call `run_project`, which
would reprocess the whole job and historically corrupted page indices). Full-job
`POST /api/jobs/{id}/rerun` still resets all pages and re-enters background
`run_project` under the concurrent-jobs semaphore.

1. Validate `project_id` allowlist + containment.
2. Read `project.json` — resolve `spec`, `status`, and the page entry for
   `page_idx`.
3. Resolve the source image path: `spec.source_path / page_entry.page_name`
   (or `spec.source_path` directly when it is a file).
4. Validate the engine + language combo.
5. Mark the page `running` via `update_page_result(spec, running_page)`.
   **On-disk:** `project.json` updated (page state = `running`).
6. Call `dispatcher.run_stage("ocr", page_id, image_path=..., engine=..., language=..., device=...)`.
   This is a single-page call (not a batch request), bounded by
   `PDOMAIN_OCR_BATCH_TIMEOUT_S`.
7. `first_page_dict(stage_result.metadata)` — extract the page dict from
   the stage result.
8. Same reorganize + normalize pipeline as the batch flow (steps d.1–d.2).
9. `build_sidecar_payload(page_dict, text)` — add `text`, `width`,
   `height`, `words`.
10. Carry over `edited_text` from the prior sidecar if it exists — a rerun
    must not silently discard hand-edits.
11. `write_page_sidecar(spec, idx, sidecar_data)`.
    **On-disk:** `<project_dir>/pages/<page_name>.json` updated.
12. `write_txt(spec, idx, ...)` — writes edited_text if preserved, else
    fresh OCR text.
    **On-disk:** `<project_dir>/pages/<page_name>.txt` updated.
13. On exception: `done_page.state = "failed"`.
14. `update_page_result(spec, done_page)`. **On-disk:** `project.json`
    updated. Project-level state is recalculated from the full page set.
15. Return `PageResult`.

---

## 4. Page save (ground-truth / text edits)

**Actors:** `PUT /api/pages/{id}/{idx}/text`, `routes/pages.py`,
`storage.py`.

1. Validate `project_id`.
2. Read `project.json`. Confirm the page index exists.
3. Read the page sidecar (best-effort). If absent, seed it with
   `{"page_idx": <idx>}`.
4. Set `sidecar["edited_text"] = body.text`.
5. `write_page_sidecar(spec, idx, sidecar)` — atomic write.
   **On-disk:** `<project_dir>/pages/<page_name>.json` updated.
6. `write_txt(spec, idx, body.text)`.
   **On-disk:** `<project_dir>/pages/<page_name>.txt` updated.
7. Return `{"status": "saved"}`.

Note: saving text does NOT write to `spec.output_dir`. The output mirror
is only updated during full-project OCR runs (`run_project`), not on save
or single-page rerun. The `GET /api/pages/{id}/{idx}` route surfaces
`edited_text` over `text` when both are present. Download truth
separation (live edited tree vs original engine output) remains deferred —
see intent-map and `docs/specs/2026-05-29-download-model.md`.

---

## 5. Job download

**Actors:** `GET /api/jobs/{id}/download`, `routes/downloads.py`, Results and
Page view managed-mode buttons.

1. Parse the `include` query param (default `text,json`). Valid tokens:
   `text`, `json`. Unknown tokens → 400.
2. `_resolve_job_output_dir(job_id)`:
   - Validate `job_id`.
   - Read `spec.output_dir` from `project.json`.
   - Return `Path(spec.output_dir)` when it is a non-empty directory.
   - Fall back to `<output_root>/{job_id}` for jobs created before
     `output_dir` was always set.
   - Return None if nothing found → 404.
3. Build a zip in memory from the **output mirror** (not the live canonical
   pages tree with `edited_text`):
   - Walk the output dir recursively (`rglob("*")`).
   - Filter: `.txt` included when `"text" in tokens`; `.json` included
     when `"json" in tokens`; all other files (images etc.) always included.
   - Archive each file with a path relative to the output dir root.
4. Stream the zip as `application/zip` with
   `Content-Disposition: attachment; filename="<job_id>.zip"`.

**UI contract:** After success in managed mode, Results and Page view expose
two fixed download actions — images+text (`?include=text`) and
images+text+JSON (`?include=text,json`) — not include-filter checkboxes.
Both still call this job-level endpoint (whole-job ZIP).

---

## 6. Job deletion

**Actors:** `DELETE /api/jobs/{id}`, `routes/jobs.py`, `storage.py`.

1. Validate `project_id`.
2. Check if the project dir exists. If not, return 204.
3. Read `spec.output_dir` from `project.json` before deletion.
4. `_remove_from_recent_projects(project_id)` — remove from prefs
   (best-effort).
5. `delete_project(project_id)` — `shutil.rmtree` the canonical project
   dir. **On-disk:** `<projects_root>/{project_id}/` removed.
6. `_delete_output_mirror(spec.output_dir)` — `shutil.rmtree` the user-
   visible output mirror. **On-disk:** `<output_dir>/` removed.
7. `_delete_job_meta(project_id)` — `shutil.rmtree` the jobs-meta sidecar
   dir. **On-disk:** `<jobs_meta_root>/{project_id}/` removed.
8. Return 200 `{"status": "deleted"}`.

All three removals are best-effort (`ignore_errors=True`). A deleted job
produces no 404 on the download endpoint after step 6.

---

## Storage paths summary

| Path | Written by |
|------|-----------|
| `<projects_root>/{id}/project.json` | `write_project()` — every state change |
| `<projects_root>/{id}/pages/<name>.json` | `write_page_sidecar()` — per-page OCR + edits |
| `<projects_root>/{id}/pages/<name>.txt` | `write_txt()` — per-page text |
| `<projects_root>/{id}/combined.txt` | `write_combined_txt()` — end of run |
| `<output_dir>/<stem>.txt` | `write_output_page_files()` — per-page mirror |
| `<output_dir>/<stem>.json` | `write_output_page_files()` — per-page mirror |
| `<output_dir>/<name>.txt` | `write_output_combined_txt()` — combined mirror |
| `<jobs_meta_root>/{id}/output_mode.json` | `_write_job_meta()` — job creation |
| `<source_path>/<name>.viewer.webp` | `_transcode_for_browser()` — image GET cache |

`<projects_root>` defaults to `~/.local/share/pdomain-suite/simple-gui/projects/`.
Override with `PD_OCR_SIMPLE_GUI_PROJECTS_ROOT` or the `jobs_location` pref.

`<output_dir>` is resolved from `spec.output_dir` (set at job creation).

`<jobs_meta_root>` defaults to `~/.local/share/pdomain-ocr-simple-gui/jobs/`.
Override with `PD_OCR_SIMPLE_GUI_JOBS_META_ROOT`.

---

## See also

- Module reference: `docs/architecture/module-map.md`
- Architecture overview: `docs/architecture/00-overview.md`
- Backend statechart: `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`
- Frontend statechart: `frontend/src/statecharts/jobCreationMachine.ts`

# Behavior unit spec — Home

- **Unit type:** screen
- **Address:** `/` and `/new-job` (the `/new-job` route renders `<HomePage />`
  inline — App.tsx; confirmed present)
- **Implementation:** `frontend/src/pages/HomePage.tsx`
- **Backend / collaborators touched:** `routes/uploads.py`, `routes/jobs.py`,
  `routes/config.py`, `routes/prefs.py`, `sources/*`, `output/config.py`,
  `pipeline.py`, `storage.py`

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path. *Observable output* is whatever the user perceives on this
surface (DOM / toasts / route).

> **STATUS: UPDATED 2026-06-01.** Source-hide behavior added to `B-HOME-001`,
> `B-HOME-003`, `B-HOME-004` (symmetric hide-on-chosen / restore-on-clear).
> `B-HOME-006` clarified to state `DocTR` is the settings-driven default on a
> fresh install. `Regression: yes` is tagged on `B-HOME-004`, `B-HOME-006`,
> `B-HOME-014` (the three fixes that restored intended behavior); each references
> its fix commit.

### On-disk artifacts (confirmed in `storage.py` + `routes/jobs.py`)

The HomePage backend writes to **four** distinct locations (env-overridable):

- **Canonical project state** — `<PD_OCR_SIMPLE_GUI_PROJECTS_ROOT>/<project_id>/`
  (default `~/.local/share/pdomain-suite/simple-gui/projects/`):
  - `project.json` — `{spec, status}` (ProjectSpec + ProjectStatus).
  - `pages/<page_name>.json` — per-page sidecar. **`<page_name>` is the source
    image filename WITH extension** (e.g. `scan.png.json`, `page-001.png.json`),
    NOT `page_0000.json`. (`storage.write_page_sidecar` → `f"{page_name}.json"`;
    `page_name = img_path.name`.) **Always written** (no `save_json` knob).
  - `pages/<page_name>.txt` — per-page text (e.g. `scan.png.txt`).
  - `combined.txt` — all per-page `.txt` joined by `\n\n`. **Always written**
    (no `combined_txt` knob — `B-HOME-011` cleanup).
- **Upload staging** — `<PD_OCR_SIMPLE_GUI_UPLOAD_ROOT>/<upload_id>/`
  (default `~/.local/share/pdomain-ocr-simple-gui/uploads/`): `<upload_id>` is a
  bare uuid hex (no `upload-` prefix; the resolver accepts both forms). Zips are
  extracted in place and the `.zip` removed. Deleted by
  `DELETE /api/uploads/{upload_id}` when the user clears the source (`B-HOME-004`).
- **Per-job meta sidecar** — `<PD_OCR_SIMPLE_GUI_JOBS_META_ROOT>/<job_id>/output_mode.json`
  (default `~/.local/share/pdomain-ocr-simple-gui/jobs/`): `{"mode": "<output.mode>"}`.
  Written only when the request carries an `output` block.
- **User-visible output mirror** — `<spec.output_dir>/` (resolved from `output`
  via `resolve_output_dir`; managed default `<PD_OCR_SIMPLE_GUI_OUTPUT_ROOT>/<job_id>/`):
  `<page_stem>.txt` AND `<page_stem>.json` (the sidecar is **always** mirrored now),
  and a combined `<sanitized-spec.name>.txt`. No-op when `output_dir` is empty.
  This is what the download zip streams (see screen-results).

### `OutputConfigError` 400 rules (from `output/config.py`)

`resolve_output_dir` raises `OutputConfigError` (→ `POST /api/jobs` 400
`{detail: "output: …"}`) in exactly three cases:

1. `mode == "next_to_source"` and the source is **not** a folder →
   `"next_to_source requires a folder source"`.
2. `mode == "specified"` while the deployment is in **managed** mode →
   `"specified output is not allowed in managed mode"`.
3. `mode == "specified"` with `path is None` → `"specified output requires a path"`.

`managed` mode never raises (it creates `<managed_root>/<job_id>`).

### B-HOME-001 — Drag-drop one or more images onto the drop zone

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01
- **Trigger:** User drags files/a folder/a `.zip` and drops onto the drop zone
  (`data-testid="source-picker-drop"`, the `APP_TEST_IDS.sourcePickerDropZone`).
- **Preconditions:** HomePage loaded; mode is `managed`, or `local`
  (containerized → the "Upload" picker, non-containerized → the combined picker).
  A drop-capable `SourcePicker` (`allowDrop`) is rendered.
- **Observable output:** Drop zone switches to the "chosen" view
  (`data-testid="source-picker-chosen"`) showing `📁 <folder>` for a folder drop,
  the single filename for one file, or `<n> files`; the `JobConfigInline` form
  (`data-testid="job-config-inline"`) appears below. In `local+containerized`
  mode (where both an "Upload" picker and an "Existing folder or zip" path picker
  are rendered), choosing an upload source **hides the path picker** — only the
  chosen picker remains visible alongside the `JobConfigInline` form. Clearing
  the chosen source (`B-HOME-004`) restores both pickers.
- **Backend / side-effects:** `POST /api/uploads` (multipart `files`) →
  `{ "upload_id": "<hex>" }`; files streamed into
  `<UPLOAD_ROOT>/<upload_id>/`; zips extracted in place. No `project.json`
  written yet (the job is created later on submit).
- **Bad-state / error:** Upload failure (non-2xx) renders an alert
  (`data-testid="source-picker-upload-error"`, `role="alert"`) with the error;
  the chosen description still shows but no `upload_id` is set so the config
  form does not appear. (Empty file set is its own record — see `B-HOME-015`.)
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-002 — Upload via the file picker (click drop zone or hidden input)

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01
- **Trigger:** User clicks the drop zone (which calls `openPicker()`), or a
  test sets files directly on the hidden file input
  (`data-testid="source-picker-file-pick"`, `APP_TEST_IDS.sourcePickerFilePick`;
  `accept="image/*,.zip"`, `multiple`).
- **Preconditions:** Same as B-HOME-001 — a drop-capable `SourcePicker`.
- **Observable output:** Identical to B-HOME-001 — chosen view + `JobConfigInline`.
- **Backend / side-effects:** Identical to B-HOME-001 (`POST /api/uploads`,
  `<UPLOAD_ROOT>/<upload_id>/`).
- **Bad-state / error:** Same alert path as B-HOME-001 on upload failure.
  Selecting then cancelling the OS dialog yields an empty file list → no request.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-003 — Choose an existing local path (folder / image / zip)

- **Flow(s):** —
- **Trigger:** User types a path into the path input
  (`data-testid="source-picker-path-input"`, `APP_TEST_IDS.sourcePickerPathInput`)
  and submits the inner form (presses Enter or clicks "Use this path").
- **Preconditions:** A `SourcePicker` with `allowPathInput` is rendered — i.e.
  mode is `local` (containerized → the second "Existing folder or zip" picker;
  non-containerized → the combined picker). Path input is NOT shown in `managed`
  mode. Draft must be non-empty/non-whitespace (`pathDraft.trim()`).
- **Observable output:** `JobConfigInline` appears with the chosen source
  `{kind: "path", path}`; the project-name default is derived from the path
  basename (`defaultProjectName`). In `local+containerized` mode (where both an
  "Upload" picker and a path picker are rendered), choosing a path source **hides
  the "Upload" picker** — only the path picker remains visible alongside the
  `JobConfigInline` form. This is symmetric with `B-HOME-001`. Clearing the
  chosen source (`B-HOME-004`) restores both pickers.
- **Backend / side-effects:** None at choose-time — the path is validated only
  later when `POST /api/jobs` runs `LocalPathSource.materialize()`.
- **Bad-state / error:** Whitespace-only path → form submit is a no-op (no
  `onPathChosen`). A bad path surfaces only at job submit (see B-HOME-009).
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-004 — Clear the chosen source (deletes the staging dir)

- **Flow(s):** —
- **Trigger:** User clicks the clear button in the chosen view
  (`data-testid="source-picker-clear"`).
- **Preconditions:** A source has been chosen (drop/pick), chosen view visible.
- **Observable output:** Chosen view collapses back to the empty drop prompt;
  the file input is reset; the config form returns to its no-source state — the
  "Use different files" cancel affordance disappears and Run OCR is disabled.
  Since commit `3ef73f1` ("keep OCR options visible before source") the
  `JobConfigInline` section is **always rendered**, so clearing collapses the
  chosen view rather than unmounting the form (parent `onClear` →
  `CLEAR_SOURCE`). In `local+containerized` mode, where selecting one source
  hides the alternative picker (see `B-HOME-001` / `B-HOME-003`), clearing also
  **restores both pickers** — the full "Upload" and "Existing folder or zip"
  inputs reappear so the user can choose a different source.
- **Backend / side-effects:** For an **upload** source, the SourcePicker calls
  `DELETE /api/uploads/{upload_id}`, which removes `<UPLOAD_ROOT>/<upload_id>/`
  from disk (idempotent: 204 when nothing matches, 400 for an unsafe id). For a
  **path** source there is no staging dir, so no DELETE is issued.
- **Bad-state / error:** A failed DELETE is best-effort — it must not block the
  UI reset. A DELETE with a traversal/unsafe `upload_id` → 400 and deletes
  nothing.
- **Tier(s):** A
- **Regression:** yes — clearing previously orphaned the staged
  `<UPLOAD_ROOT>/<upload_id>/` dir on disk; staging dirs accumulated. Fixed in
  commit `f4f9969` (DELETE /api/uploads/{upload_id} + clear-handler wiring).
- **Test:** —

### B-HOME-005 — Cancel the config form ("Use different files")

- **Flow(s):** —
- **Trigger:** User clicks "Use different files"
  (`data-testid="job-config-inline-cancel"`).
- **Preconditions:** A source is committed, so the cancel affordance is rendered
  (`job-config-inline-cancel` only renders while `source !== null`).
- **Observable output:** The chosen source is cleared and the form returns to
  its no-source state: the "Use different files" cancel button disappears and
  Run OCR (`run-ocr-button`) becomes disabled. Since commit `3ef73f1` ("keep OCR
  options visible before source") the `JobConfigInline` section is **always
  rendered** — cancel clears the source (`onCancel` → `CLEAR_SOURCE`) rather
  than unmounting the form.
- **Backend / side-effects:** None. (The cancel button on the config form does
  not itself clear the SourcePicker's staged upload; clearing the picker —
  `B-HOME-004` — is what deletes the staging dir.)
- **Bad-state / error:** The cancel affordance is absent when no source is
  committed, so clicking it with no source chosen is not reachable.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-006 — Engine/language default from prefs; user can override

- **Flow(s):** —
- **Trigger:** Form mount loads defaults via `GET /api/prefs`; the user may then
  change the engine `<select>` (`data-testid="engine-select"`,
  `APP_TEST_IDS.engineSelect`; options `doctr` / `tesseract`) and/or type into
  the language `Input` (`data-testid="language-input"`,
  `APP_TEST_IDS.languageInput`).
- **Preconditions:** `JobConfigInline` visible.
- **Observable output:** On mount the form seeds engine + language from the
  prefs response. `AppPrefs` exposes `default_engine` / `default_language`
  (model default: `"doctr"` / `"en"`). On a **fresh install** with no persisted
  prefs, the select shows `DocTR` with no user interaction needed — the
  settings-driven default is `doctr`. A user-saved `default_engine: "tesseract"`
  makes the select start on `tesseract`. Select/field then reflect any user
  change. An empty or missing `default_engine` in the prefs response does not
  overwrite the `"doctr"` init default.
- **Backend / side-effects:** `GET /api/prefs` on form mount. The chosen
  `engine`/`language` ride along in the `POST /api/jobs` body and persist into
  `project.json` → `spec.engine` / `spec.language`. Tesseract is English-only in
  the simple GUI (commit `55749e2`): at submit, `normalizeEngineLanguage` maps
  English (`en`) to Tesseract's `eng` code, so a Tesseract job persists
  `spec.language == "eng"`. A non-English language with Tesseract is an
  unsupported combination the backend rejects (`language '<x>' is unavailable`).
- **Bad-state / error:** `GET /api/prefs` failure → defaults kept (`doctr`/`en`),
  no error shown (`.catch()` swallows — non-fatal, the user can still pick).
- **Tier(s):** A
- **Regression:** yes — the form read `data.engine` / `data.language` from
  `/api/prefs`, but `AppPrefs` only exposes `default_engine` /
  `default_language`, so saved defaults silently no-op'd and the form always
  started doctr/en. Fixed in commit `634c802` (read the correct keys).
- **Test:** —

### B-HOME-007 — Toggle text-normalization options

- **Flow(s):** —
- **Trigger:** User flips any of three Toggles: straight-quotes
  (`APP_TEST_IDS.toggleStraightQuotes`, default ON), em-dash→double-hyphen
  (`APP_TEST_IDS.toggleEmDash`, default ON), emit-illustration-placeholders
  (`APP_TEST_IDS.toggleIllustrationPlaceholders`, default OFF).
- **Preconditions:** `JobConfigInline` visible.
- **Observable output:** Toggle visual state flips. **Selector note:** the
  `@pdomain/pdomain-ui` Toggle (Radix Switch) does NOT forward `data-testid` to
  the DOM, so those testid constants are documentation-only. E2e must select via
  `page.get_by_label(<label text>)`. Labels: "Convert curly quotes to straight",
  "Convert em-dashes (—) to double hyphens (--)", "Emit [illustration]
  placeholders for figures".
- **Backend / side-effects:** Values ride in `POST /api/jobs` as
  `straight_quotes`, `em_dash_to_double_hyphen`, `emit_illustration_placeholders`
  and persist into `spec`. They drive `apply_text_normalizations` +
  `reorganize_page(emit_illustration_placeholders=…)` in the pipeline, changing
  the written `.txt` / sidecar text.
- **Bad-state / error:** A toggle value that the backend doesn't recognise is
  impossible — they are plain booleans coerced by the request model.
- **Tier(s):** A (a Tier-B would prove the toggles actually change real OCR text)
- **Regression:** no
- **Test:** —

### B-HOME-008 — Select processing device (auto / cpu / gpu) + GPU help

- **Flow(s):** —
- **Trigger:** User clicks a segment in the device chooser
  (`data-testid="device-chooser"`, `APP_TEST_IDS.deviceChooser`); when no GPU,
  clicks "Why is GPU unavailable?" (`data-testid="gpu-help-toggle"`).
- **Preconditions:** `JobConfigInline` visible. Segments are `auto`/`gpu`/`cpu`
  when `cfg.gpu_available`, else `auto`/`cpu` only. The help toggle + `gpu-help`
  panel render only when `!gpu_available`.
- **Observable output:** Selected segment highlights; clicking the help toggle
  reveals/hides the `gpu-help` panel (`data-testid="gpu-help"`).
- **Backend / side-effects:** `GET /api/config` supplies `gpu_available` +
  `detected_device` (drives which segments render). The chosen `device` rides in
  `POST /api/jobs` and **is honored end-to-end**: it persists to
  `project.json` → `spec.device`, and the pipeline forwards it via
  `resolve_device(spec.device)` into `OcrBatchRequest(device=…)`
  (pipeline.py — `"cpu"` stays `"cpu"`, `"auto"` → `None` for auto-detect,
  `"gpu"` → the detected accelerator). The concretely observable effect on disk
  is `spec.device` in `project.json`. The front-end coerces `gpu`→`cpu` when
  `!gpuAvailable`, so a stale "gpu" choice can't be submitted.
- **Bad-state / error:** `GET /api/config` failure → no `cfg` → HomePage shows
  the config-error state (see B-HOME-014), not the device chooser.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-009 — Set output destination (next-to-source / specified / managed)

- **Flow(s):** —
- **Trigger:** User picks a segment in `OutputConfigPanel`
  (`data-testid="output-config-panel"` / inner `output-mode-segmented`); when
  "Specified folder" is chosen, types into the path input
  (`data-testid="output-specified-path"`, `APP_TEST_IDS.outputSpecifiedPath`).
- **Preconditions:** `JobConfigInline` visible. Available options are filtered:
  `next_to_source` only when the source is a folder/path; `specified` only when
  mode ≠ `managed`; `managed` always. Hidden legacy radio sentinels
  (`output-mode-next-to-source` / `-specified` / `-managed`) mirror state for
  back-compat selectors.
- **Observable output:** Segmented reflects the mode; the specified-path input
  appears only in `specified` mode.
- **Backend / side-effects:** The `output` block (`{mode}` or `{mode, path}`)
  rides in `POST /api/jobs`. The server resolves it via `resolve_output_dir`
  and writes `output_mode.json` to `<JOBS_META_ROOT>/<job_id>/`; the resolved
  dir becomes `spec.output_dir` (the download mirror).
- **Bad-state / error:** `resolve_output_dir` raising `OutputConfigError` →
  `POST /api/jobs` returns `400 {detail: "output: …"}`; the form shows the
  server error in its `role="alert"` block and stays on HomePage. The three
  raising cases are listed under "`OutputConfigError` 400 rules" above — e.g.
  `{mode:"next_to_source"}` on an upload source → 400 "next_to_source requires
  a folder source"; `{mode:"specified"}` with no path → 400 "specified output
  requires a path".
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-010 — Set pages-per-batch and project name

- **Flow(s):** —
- **Trigger:** User edits the project-name `Input` (`#jci-name`,
  `aria-label="Project name"`) and/or the pages-per-batch number input
  (`data-testid="batch-pages-input"`, `APP_TEST_IDS.batchPagesInput`).
- **Preconditions:** `JobConfigInline` visible.
- **Observable output:** Fields reflect typed values. Empty project name →
  Run-OCR button is `disabled` (`disabled={submitting || !projectName.trim()}`).
- **Backend / side-effects:** `batch_pages` rides in `POST /api/jobs` as
  `null` (blank → default 8) or `max(1, parseInt)`, persisting to
  `spec.batch_pages`; `name` persists to `spec.name` and seeds the recent-projects
  entry + the combined-output filename.
- **Bad-state / error:** Submitting with a blank name (if the button were
  somehow enabled) → client-side `setError("Project name is required.")` shown
  in the alert block, no request fired.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-011 — Start the OCR job (submit the config form)

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01
- **Trigger:** User clicks "Run OCR →" (`data-testid="run-ocr-button"`,
  `APP_TEST_IDS.runOcrButton`) / submits `job-config-inline-form`.
- **Preconditions:** A source chosen, non-empty project name, form not already
  submitting.
- **Observable output:** Button shows "Run OCR →…" while submitting, then the
  app navigates to `/jobs/<project_id>` — the results page
  (`data-testid="results-page"`) renders and at least one `page-row`
  (`data-testid="page-row"`) appears as the job progresses to succeeded.
- **Backend / side-effects:** `POST /api/jobs` (202) with the config body
  (`name, engine, language, straight_quotes, em_dash_to_double_hyphen,
  emit_illustration_placeholders, device, batch_pages, output`, plus `upload_id`
  OR `source_path`) → `{ "project_id": "<uuid>" }`. **No `save_json` /
  `combined_txt` knob** — the server unconditionally writes per-page sidecars
  (`pages/<name>.json`), per-page `.txt`, `combined.txt`, and the output mirror
  (per-page `.txt` + `.json` + combined). Server writes `project.json` (queued),
  enqueues `_pipeline_run_job` as a background task.
- **Bad-state / error:** Non-2xx response → `setError("Server error: <body>")`
  shown in the `role="alert"` block; the app stays on HomePage (no navigation).
  Bad source / output combos → 400 (see B-HOME-009 / B-HOME-017 / B-HOME-018).
  Zero discovered images → job marked `failed` (see B-HOME-017).
- **Tier(s):** A and B (B = the real OCR engine produces real `.txt`/sidecar
  output; covered by the existing `tests/e2e/test_real_ocr_pipeline.py`).
- **Regression:** no
- **Test:** —

### B-HOME-012 — Recent-projects list renders (and empty/loading states)

- **Flow(s):** —
- **Trigger:** HomePage mounts; `RecentProjectsList` fetches `GET /api/prefs`.
- **Preconditions:** None (always rendered at the bottom of HomePage).
- **Observable output:** Container `data-testid="recent-projects-list"`
  (`APP_TEST_IDS.recentProjectsList`) shows: "Loading…" while fetching;
  "No recent projects" when the list is empty; otherwise a table (capped at 10)
  with Name / Last opened / Pages / Engine / Status (`JobStatusPip`), one
  `data-testid="recent-project-row"` per project. This screen only **renders
  from** prefs — it does not populate them.
- **Backend / side-effects:** `GET /api/prefs` → `recent_projects` array
  (seeded by `PUT /api/prefs`). **Population is future work** — the writer that
  records a completed job into `recent_projects` belongs to a future Projects
  page (see `docs/specs/2026-05-29-projects-page.md`); nothing on this screen
  writes it.
- **Bad-state / error:** Non-ok `/api/prefs` or unexpected shape → treated as an
  empty list (`throwOnError:false`, `return []`) → "No recent projects" (no
  error UI).
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-013 — Open a recent project (click a row)

- **Flow(s):** —
- **Trigger:** User clicks (or presses Enter/Space on) a recent-project row
  (`data-testid="recent-project-row"`).
- **Preconditions:** At least one recent project rendered (seeded via prefs;
  population is future Projects-page work — see
  `docs/specs/2026-05-29-projects-page.md`).
- **Observable output:** App navigates to `/jobs/<project_id>`; the results page
  (`data-testid="results-page"`) for that project loads; URL contains the id.
- **Backend / side-effects:** None at click time (results page does its own
  `GET /api/jobs/<id>` fetch).
- **Bad-state / error:** A row for a deleted project → navigates, but the
  results page's `GET /api/jobs/<id>` returns 404. That stale-row → 404-on-open
  behavior is **deferred to ResultsPage / M4** and is asserted there, not here.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-014 — Mode/container matrix drives which pickers render

- **Flow(s):** —
- **Trigger:** HomePage mounts and reads `GET /api/config` (via ConfigContext).
- **Preconditions:** None.
- **Observable output:**
  - `mode==="managed"` → one upload-only `SourcePicker` (drop, no path input).
  - `mode==="local" && containerized` → "Upload" picker (drop) + "Existing folder
    or zip" picker (path input, container-fs hint).
  - `mode==="local" && !containerized` → one combined picker (drop + path input).
  - `cfg` not yet loaded → "Loading…".
- **Backend / side-effects:** `GET /api/config` → `{mode, is_containerized,
  detected_device, gpu_available}`.
- **Bad-state / error:** `GET /api/config` failure (non-ok or network) →
  HomePage renders an error alert (`data-testid="home-config-error"`,
  `role="alert"`) with a Retry button (`data-testid="home-config-retry"`) that
  re-runs the fetch — it does NOT hang on "Loading…".
- **Tier(s):** A
- **Regression:** yes — a failed `/api/config` left `cfg=null` forever, so
  HomePage hung on "Loading…" with no error and no recovery. Fixed in commit
  `ce96721` (ConfigContext error state + reload; HomePage error UI).
- **Test:** —

### B-HOME-015 — Empty upload (no files selected)

- **Flow(s):** —
- **Trigger:** A drop/file-pick that yields an empty file list (e.g. dropping
  nothing, or cancelling the OS file dialog).
- **Preconditions:** A drop-capable `SourcePicker` rendered.
- **Observable output:** The chosen view does NOT appear and no source is
  committed — `handleFiles` returns early on `!files.length`. Since commit
  `3ef73f1` ("keep OCR options visible before source") the `JobConfigInline`
  section is always rendered, so the observable for "nothing was chosen" is the
  absence of the committed-source affordances (the "Use different files" cancel
  button) with Run OCR disabled — not the form unmounting.
- **Backend / side-effects:** No `POST /api/uploads` request is made; no
  staging dir is created.
- **Bad-state / error:** This IS the bad path of an upload trigger; the
  good path is B-HOME-001 / B-HOME-002.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-016 — Duplicate filenames in one upload / folder

- **Flow(s):** —
- **Trigger:** Upload (or a folder containing) two files with the same basename
  — e.g. two `scan.png` from different subdirectories of a dropped folder.
- **Preconditions:** A drop-capable `SourcePicker`.
- **Observable output:** The chosen view shows the file count; both names appear
  in the list.
- **Backend / side-effects:** `POST /api/uploads` writes each file under its
  **basename** (`Path(upload.filename).name` strips any path) into the single
  `<UPLOAD_ROOT>/<upload_id>/` dir. Two files with the same basename collide:
  the second `rename(target)` overwrites the first, so the staging dir ends up
  with **one** file under that name. `collect_images` then discovers one image
  for that name. (No crash, no 500 — last-writer-wins.)
- **Bad-state / error:** The collision silently keeps the last write; the user
  sees fewer discovered pages than files dropped. This is the documented
  current behavior, asserted as a known invariant (no de-duplication / rename).
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-017 — Unsupported file types (no supported images found)

- **Flow(s):** —
- **Trigger:** Submit a job whose source contains only unsupported file types
  (e.g. `.txt`, `.bmp`) — via upload or local path.
- **Preconditions:** A source chosen; `JobConfigInline` visible; Run OCR clicked.
- **Observable output:** `POST /api/jobs` is accepted (202) and the app
  navigates to the results page, but the job transitions to **failed**.
- **Backend / side-effects:** `collect_images` returns `[]`; the background task
  writes `state="failed"`, `page_count=0`, and `error` containing "No supported
  image files found in source; supported types are PNG, JPEG, TIFF, JPEG 2000,
  WebP." `GET /api/jobs/<id>` returns that failed status. No sidecars / `.txt`
  are written.
- **Bad-state / error:** This record IS the bad path; the contrast is a job with
  ≥1 supported image (B-HOME-011 good path → succeeded).
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-018 — Oversize upload (size cap / file-count cap)

- **Flow(s):** —
- **Trigger:** Upload exceeding the per-request byte cap
  (`PD_OCR_SIMPLE_GUI_UPLOAD_MAX_BYTES`) or file-count cap
  (`PD_OCR_SIMPLE_GUI_UPLOAD_MAX_FILES`).
- **Preconditions:** A drop-capable `SourcePicker`.
- **Observable output:** The SourcePicker renders the upload-error alert
  (`data-testid="source-picker-upload-error"`, `role="alert"`) — the chosen
  view shows the description but no `upload_id` is set, so no source is
  committed. Since commit `3ef73f1` ("keep OCR options visible before source")
  the `JobConfigInline` section is always rendered, so the observable is the
  absence of the committed-source affordances (the "Use different files" cancel
  button) with Run OCR disabled.
- **Backend / side-effects:** `POST /api/uploads` returns **413** ("upload
  exceeds size cap" or "too many files"); the partially-written staging dir is
  cleaned up (`shutil.rmtree(staging, ignore_errors=True)`), so no orphan
  remains. (A `.zip` whose extraction would exceed limits / traversal → handled
  by the zip-traversal guard; an oversize zip source surfaces the same 413 /
  cleanup path.)
- **Bad-state / error:** This record IS the bad path (a within-cap upload is
  B-HOME-001 / B-HOME-002).
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-019 — Missing / permission-denied output directory

- **Flow(s):** —
- **Trigger:** Submit with `output: {mode:"specified", path:<bad>}` where the
  path can't be created (e.g. a permission-denied location), or otherwise
  violates an `OutputConfigError` rule.
- **Preconditions:** `JobConfigInline` visible, local (non-managed) mode for the
  `specified` option to be offered.
- **Observable output:** When the output config is structurally invalid
  (the three `OutputConfigError` rules), `POST /api/jobs` returns **400**
  `{detail:"output: …"}` and the form shows the server error in its
  `role="alert"` block, staying on HomePage (no navigation).
- **Backend / side-effects:** `resolve_output_dir` raises `OutputConfigError`
  (400) for the three rule violations before any project is written. A path that
  passes the rules but fails at OS level (permission denied on `mkdir`) surfaces
  as a non-2xx server error → same `role="alert"` "Server error" display; no
  `project.json` is left in a usable state.
- **Bad-state / error:** This record IS the bad path; the good path is
  B-HOME-009 with a valid destination.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

### B-HOME-020 — Concurrent jobs from the same screen

- **Flow(s):** —
- **Trigger:** Submit a job, return to `/` (or `/new-job`), choose another
  source, and submit a second job while the first may still be running.
- **Preconditions:** HomePage reachable after a prior submit (navigate back).
- **Observable output:** Each submit produces its own results page at a distinct
  `/jobs/<project_id>`; the AppHeader's active-jobs pill may show more than one
  running job (polls `GET /api/jobs?state in {running,queued}`).
- **Backend / side-effects:** Each `POST /api/jobs` mints a fresh
  `uuid4` `project_id` and its own `project.json` + background task; the two
  jobs write to disjoint `<PROJECTS_ROOT>/<project_id>/` dirs and disjoint
  output mirrors. `GET /api/jobs` lists both. No shared mutable state couples
  them — one job's failure does not affect the other.
- **Bad-state / error:** Two jobs that resolve to the **same** `specified`
  output dir would interleave files in that dir (last-writer-wins per filename);
  managed mode avoids this by keying the output dir on `job_id`.
- **Tier(s):** A
- **Regression:** no
- **Test:** —

## Known regressions

Records tagged `Regression: yes` — load-bearing behaviors that re-broke before
and must stay covered:

- **B-HOME-004** — clearing a chosen upload orphaned its `<UPLOAD_ROOT>/<id>/`
  staging dir on disk. Fixed in `f4f9969`.
- **B-HOME-006** — the config form read `engine`/`language` from `/api/prefs`
  but `AppPrefs` exposes `default_engine`/`default_language`, so saved defaults
  silently no-op'd. Fixed in `634c802`.
- **B-HOME-014** — a failed `GET /api/config` left HomePage hung on "Loading…"
  forever with no error or recovery. Fixed in `ce96721`.

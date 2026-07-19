---
Status: active
Owner: CT
Created: 2026-05-29
Last verified: 2026-07-14
Kind: spec
---

# Behavior unit spec — Results

## Adversarial Review

- **Stage:** post-implementation
- **Source:** 2026-07-14 docgraph migration; independent read-only review of current code, tests, history, and related docs.
- **Accepted findings:** The review compared the documented contract with current implementation and accepted the material deviations recorded in the architecture and authored context.
- **Effect on result:** Shipped behavior remains active; obsolete UI or workflow assumptions are not treated as current truth.
- **Implementation deviations:** The shared jobs dock and fixed job-level download buttons replaced parts of the earlier projected surfaces. Recent projects are written at job creation. Upload/edit/download coverage does not prove edited text is present in the exported ZIP.
- **Residual risks:** Per-page edits and reruns can leave the job output mirror stale; the download redesign remains deferred.
- **2026-07-14 re-verification (review-fixes Task 20 (plan retired)):** the earlier 2026-07-14 pass above left B-RESULTS-006/-007 and the download zip-membership notes pointing at the pre-Task-9 checkbox-filter UI (`download-results-button`, `download-filter-text`, `download-filter-json`) — stale since commit `8d49ad3` (2026-06-04), which replaced the single button + two filter checkboxes with two explicit buttons: `download-images-text` (`?include=text`) and `download-images-text-json` (`?include=text,json`). Corrected against current `frontend/src/pages/ResultsPage.tsx` + `frontend/src/lib/testids.ts`. Note: unlike PageViewPage, ResultsPage's download buttons carry no keyboard shortcuts (click-only). Verified every selector cited by this doc against `rg -o 'data-testid="[^"]+"' frontend/src | sort -u`.

- **Unit type:** screen
- **Address:** `/jobs/:id`
- **Implementation:** `frontend/src/pages/ResultsPage.tsx` (polling via
  `frontend/src/api/useOcrJob.ts` → `useLongJob` from `@pdomain/pdomain-ui/stores`)
- **Backend / collaborators touched:** `routes/jobs.py` (GET status / rerun /
  delete), `routes/downloads.py` (download zip), `routes/pages.py` (page nav
  target), `storage.py` (artifact IO)

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path. *Observable output* is whatever the user perceives on this
surface (DOM / toasts / route).

> **STATUS: LOCKED.** Maintainer interview complete (capture-recipe step 4).
> Five behaviors were confirmed as regressions and fixed in this milestone
> (B-RESULTS-004, -009, -011, -012, -014); the download include-filter
> (B-RESULTS-006/-007) is a new feature, not a regression. `Test:` fields cite
> the covering Tier-A (and, for -003/-009, Tier-B) tests.

### On-disk artifacts (confirmed in `storage.py` + `routes/jobs.py` + `routes/downloads.py`)

ResultsPage reads/writes across the same locations HomePage documents (see
`screen-home.md` "On-disk artifacts"). The Results-relevant facts, re-confirmed:

- **Canonical project state** — `<PD_OCR_SIMPLE_GUI_PROJECTS_ROOT>/<project_id>/`:
  - `project.json` — `{spec, status}`. `GET /api/jobs/{id}` reads this
    (`read_project`) and enriches the returned `ProjectStatus` with `name` +
    `output_dir` from spec, and `output_mode` from the meta sidecar.
  - `pages/<page_name>.json` / `pages/<page_name>.txt` — per-page sidecar +
    text. `<page_name>` is the **source image filename** (e.g. `page-001.png`;
    the seeded fixtures use a bare `page-001`). Rewritten by a per-page rerun.
  - `combined.txt` — all per-page `.txt` joined by `\n\n`.
  - **`delete_project` removes this whole dir** (`shutil.rmtree`).
- **Per-job meta sidecar** — `<PD_OCR_SIMPLE_GUI_JOBS_META_ROOT>/<job_id>/output_mode.json`
  = `{"mode": "<output.mode>"}`. Drives `output_mode` in the GET response →
  the download button only renders for `managed`. **Now removed by delete**
  (B-RESULTS-014 fix).
- **User-visible output mirror** — `<spec.output_dir>/`: `<page_stem>.txt`,
  `<page_stem>.json`, and a combined `<sanitized-spec.name>.txt`. **This is
  what the download zip streams** (`routes/downloads.py` rglobs this dir).
  **Now removed by delete** (B-RESULTS-014 fix) — `delete_job` reads the spec
  for `output_dir` before rmtree, then removes the mirror + meta too.

### Download zip membership (`routes/downloads.py`, confirmed)

`GET /api/jobs/{id}/download?include=<tokens>` streams `spec.output_dir`
(falls back to `<OUTPUT_ROOT>/<job_id>` for legacy jobs) as a zip:

- `include` tokens are `{text, json}`, comma- / plus- / space-separated. The
  backend still accepts any combination of these tokens; ResultsPage's UI
  drives only two fixed combinations via two explicit buttons (Task 9, commit
  `8d49ad3`, replacing the earlier text/json filter-checkbox pair):
  `download-images-text` sends `?include=text`; `download-images-text-json`
  sends `?include=text,json` (URL-encoded). There is no UI path to
  `?include=json` alone — only the API supports it directly.
- A `.txt` file is included iff `text` ∈ tokens; a `.json` file iff
  `json` ∈ tokens; **every other file (images, etc.) is ALWAYS included**
  regardless of tokens (legacy "zip everything" behaviour).
- Unknown token → **400** `"include has unknown token(s) …"`. Empty/blank
  include → **400**. Output dir missing → **404** `"job output not found"`.
- Members are `path.relative_to(job_dir)` (flat per-page stems + the combined
  file), sorted.

### Polling model (`useOcrJob` + `useLongJob`, confirmed)

- ResultsPage polls `GET /api/jobs/{id}` every **1000 ms**
  (`POLL_INTERVAL_MS`, overriding `useLongJob`'s 2000 ms default).
- Backend `JobState` → `LongJobStatus` map: `queued→pending`,
  `running→running`, `succeeded→done`, `failed→error`, `cancelled→cancelled`.
- `useLongJob` **re-arms the next poll only while status ∉ {done, error,
  cancelled}** — i.e. it keeps polling for `queued`/`running` and **stops** on
  `succeeded`, `failed`, `cancelled`.
- The pollFn now distinguishes failure modes via `JobFetchError.status`
  (B-RESULTS-011/-012 fix):
  - **404** → re-thrown (terminal): `useLongJob` stops, `useOcrJob` sets
    `notFound`, and ResultsPage shows the distinct "Job not found" block.
  - **5xx / network** → swallowed: the pollFn returns a non-terminal status so
    `useLongJob` **keeps polling**; `useOcrJob` sets `transientError` (a
    non-fatal "retrying…" banner), cleared on the next successful poll.
- `cancel()` is a **no-op** — the backend has no cancel endpoint
  (`useOcrJob` documents this; nothing on ResultsPage calls it).

### B-RESULTS-001 — Job page loads and shows name + status pip

- **Flow(s):** —
- **Trigger:** Navigate to `/jobs/:id` (from a HomePage submit redirect, a
  recent-project row, the AppHeader active-jobs pill, or a direct URL).
- **Preconditions:** A project with that id exists on disk
  (`project.json` present).
- **Observable output:** `data-testid="results-page"` container renders; the
  `<h1>` shows the project `name`; a `JobStatusPip` shows the current `state`.
  While the first poll is in flight (no data yet, not error) the page shows
  `Loading…` (`.results-page__loading`).
- **Backend / side-effects:** `GET /api/jobs/{id}` → `ProjectStatus` enriched
  with `name`, `output_dir`, `output_mode` (read from `project.json` +
  meta sidecar). No writes.
- **Bad-state / error:** Unknown/invalid id → see B-RESULTS-011 (404 →
  not-found block). Malformed id (traversal chars) → `GET` returns 400 (still
  surfaces as an error block client-side, never the loaded header).
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_results.py::test_results_page_loads_name_and_pip`,
  `::test_results_page_bad_id_is_not_a_crash`

### B-RESULTS-002 — Running job shows progress bar; polls until terminal

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01
- **Trigger:** Land on `/jobs/:id` while the job state is `queued` or
  `running`; the page polls on its own.
- **Preconditions:** Job state ∈ {queued, running}.
- **Observable output:** A `Progress` bar renders (`isRunning` true) with label
  `"<pages_done> of <page_count> pages"` plus a `"<pages_done> / <page_count>
  pages complete"` line. The bar value is `round(progress*100)` (progress =
  `pages_done/page_count`). The page re-renders as successive polls land.
- **Backend / side-effects:** Repeated `GET /api/jobs/{id}` every 1000 ms.
  No writes. The background pipeline (`_pipeline_run_job`) advances
  `status.pages_done` / per-page `state` in `project.json`; each poll reflects
  the latest.
- **Bad-state / error:** A poll that fails transiently (5xx / network) now
  **keeps polling** (B-RESULTS-012 fix) rather than going terminal; a 404 stops
  with the not-found block (B-RESULTS-011). The progress bar is hidden once
  state leaves running (B-RESULTS-003 / -004). A running job shows no
  download/rerun actions.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_results.py::test_running_job_shows_progress_bar`,
  `::test_running_job_no_actions_yet`

### B-RESULTS-003 — Job reaches succeeded; polling stops; results render

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01
- **Trigger:** The polled job transitions to `succeeded`.
- **Preconditions:** Job ran to completion with ≥1 page.
- **Observable output:** Progress bar disappears; the per-page status table
  (`aria-label="Page results"`) renders with one `data-testid="page-row"` per
  page; the status pip shows succeeded. **Polling stops** (no further
  `GET /api/jobs/{id}` fires — `done` is terminal). For a `managed` job the
  download button appears (B-RESULTS-006); for any succeeded job with an
  `output_dir` the Copy-path + Re-run-all actions appear (B-RESULTS-008 / -009).
- **Backend / side-effects:** Final `GET /api/jobs/{id}` returns
  `state="succeeded"`, `pages_done == page_count`, populated `pages[]`. On disk:
  `pages/<name>.{json,txt}`, `combined.txt`, and the output mirror are all
  written by the pipeline before this state.
- **Bad-state / error:** Succeeded but **empty** `pages[]` (page_count 0) → no
  table rows render (the `pages && pages.length > 0` guard); name + pip still
  show.
- **Tier(s):** A and B
  > Tier B asserts the polled `succeeded` job carries **real** OCR text. The
  > existing `tests/e2e/test_real_ocr_pipeline.py` drives upload→real OCR→
  > results→page text and now cites `Covers: B-RESULTS-003` (the Tier-A test
  > asserts the render contract + the on-disk `.txt` mirror; the Tier-B test
  > asserts real recognized text with ≥60% word overlap).
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_results.py::test_succeeded_job_renders_results_and_stops_polling`,
  `::test_succeeded_empty_pages_renders_header_only`;
  Tier B: `tests/e2e/test_real_ocr_pipeline.py::test_real_ocr_produces_expected_text`

### B-RESULTS-004 — Job reaches failed; polling stops; failure surfaced

- **Flow(s):** —
- **Trigger:** The polled job transitions to `failed` (e.g. zero supported
  images — see B-HOME-017 — or a pipeline exception).
- **Preconditions:** Job state becomes `failed`.
- **Observable output:** Status pip shows `failed`. **Polling stops** (`failed`
  → `error` in the hook, terminal — but `jobData` is populated, so this is the
  loaded failed render, not the fetch-error block). A dedicated failed block now
  renders: the `status.error` text via `data-testid="results-error"` AND a
  `data-testid="rerun-failed-button"` ("Re-run job") affordance. (Previously a
  failed job rendered only a bare red pip with no message and no rerun control.)
- **Backend / side-effects:** `GET /api/jobs/{id}` returns `state="failed"`
  with `status.error` set. No sidecars/`.txt` for a zero-image failure. Clicking
  "Re-run job" POSTs `/rerun` (shared with B-RESULTS-009).
- **Bad-state / error:** A succeeded job renders NO failed block / rerun-failed
  button (the good contrast is B-RESULTS-003).
- **Tier(s):** A
- **Regression:** yes (fixed in commit `aa6759a` — failed job now surfaces
  `status.error` + a rerun affordance instead of a bare red pip)
- **Test:** `tests/e2e/test_click_paths_results.py::test_failed_job_surfaces_error_and_rerun`,
  `::test_succeeded_job_has_no_failed_error_block`

### B-RESULTS-005 — Per-page status table populates with preview text

- **Flow(s):** —
- **Trigger:** Job has ≥1 page in `status.pages` (any state).
- **Preconditions:** `pages[]` non-empty.
- **Observable output:** A 3-column table (Page / Status / Preview). Each row
  (`data-testid="page-row"`): the page name, a `JobStatusPip` for that page's
  `state`, and the first 60 chars of `text_preview` (or `"—"` when the preview
  is empty/blank).
- **Backend / side-effects:** Rows come straight from the `GET /api/jobs/{id}`
  `pages[]` (each `{page_idx, page_name, state, text_preview}`). No writes.
- **Bad-state / error:** Empty `text_preview` → cell shows `"—"`. A still-running
  job shows per-page pips in `queued`/`running` and updates as polls land.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_results.py::test_results_page_table_rows_and_preview`,
  `::test_results_page_empty_preview_shows_dash`

### B-RESULTS-006 — Download results zip (managed mode) — two explicit buttons

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01
- **Trigger:** User clicks "Download (images + text)"
  (`data-testid="download-images-text"`) or "Download (images + text + JSON)"
  (`data-testid="download-images-text-json"`).
- **Preconditions:** `state === "succeeded"` **AND** `output_mode === "managed"`
  (`showDownload` — both buttons only render for that combination; see
  `ResultsPage.tsx`).
- **Observable output:** No filter checkboxes — Task 9 (commit `8d49ad3`,
  2026-06-04) replaced the single button + text/json filter-checkbox pair with
  two always-enabled buttons that drive fixed `include` values. Clicking
  "Download (images + text)" does
  `window.location.assign('/api/jobs/<id>/download?include=text')`; clicking
  "Download (images + text + JSON)" does
  `window.location.assign('/api/jobs/<id>/download?include=' +
  encodeURIComponent('text,json'))`. In Playwright this surfaces as a
  `download` event with a `<id>.zip` filename. Neither button has a `disabled`
  prop or a keyboard shortcut on this screen (contrast PageViewPage's mirrored
  buttons, which are keyboard-bound to `mod+shift+t` / `mod+d` —
  `screen-page-view.md` B-PAGEVIEW-016).
- **Backend / side-effects:** `GET /api/jobs/{id}/download?include=<tokens>`
  streams the **output mirror** (`spec.output_dir`) as a zip. With
  `text,json` the members are the per-page `<stem>.txt` + `<stem>.json` + the
  combined `<sanitized-name>.txt` (and any images, always included); with
  `text` only, the `.json` member is **excluded** (asserted against real ZIP
  membership). 200, `Content-Disposition: attachment; filename="<id>.zip"`.
- **Bad-state / error:** Output dir missing → endpoint 404 (`"job output not
  found"`). A non-managed succeeded job hides both buttons entirely
  (B-RESULTS-007). Malformed/empty `include` token → 400.
- **Tier(s):** A
- **Regression:** no (the two-button redesign is a UI change, not a
  regression fix; the backend `include` contract is unchanged)
  > **Corrected 2026-07-14:** this record previously described a single
  > "Download results (.zip)" button (`download-results-button`) plus two
  > filter checkboxes (`download-filter-text` / `download-filter-json`) that
  > were removed over a month before this correction. Confirmed against
  > current `ResultsPage.tsx` and `frontend/src/lib/testids.ts`.
- **Test:** `tests/e2e/test_click_paths_downloads.py::test_download_zip_from_results_page`,
  `::test_download_images_text_button_drops_json`,
  `::test_download_bad_include_token_rejected`;
  `frontend/src/pages/__tests__/ResultsPage.test.tsx` ("shows download
  buttons when output_mode is managed and state is succeeded",
  "renders two explicit download buttons (no checkboxes) in managed mode",
  "download-images-text button assigns ?include=text URL",
  "download-images-text-json button assigns ?include=text,json URL")

### B-RESULTS-007 — Download buttons hidden for non-managed / non-succeeded

- **Flow(s):** —
- **Trigger:** Render Results for a job that is succeeded but
  `output_mode !== "managed"` (e.g. `next_to_source` / `specified`), OR any job
  not yet succeeded.
- **Preconditions:** As above.
- **Observable output:** Neither `data-testid="download-images-text"` nor
  `data-testid="download-images-text-json"` is in the DOM (`showDownload` is
  `false`). (The download endpoint still exists and works by URL; only the
  in-page buttons are gated.)
- **Backend / side-effects:** None (no button → no request from this screen).
- **Bad-state / error:** This IS the hidden/bad contrast to B-RESULTS-006.
  Both buttons are absent together — there is no partial state. Non-managed
  succeeded jobs intentionally have NO download affordance on Results — the
  user gets the Copy-path button (B-RESULTS-008) to find the output on disk
  (managed-only download confirmed).
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_downloads.py::test_download_button_hidden_for_non_managed`;
  `frontend/src/pages/__tests__/ResultsPage.test.tsx` ("hides download
  buttons when output_mode is next_to_source", "hides download buttons when
  state is not succeeded")

### B-RESULTS-008 — Copy output path to clipboard

- **Flow(s):** —
- **Trigger:** User clicks "Copy path" (`data-testid="copy-path-button"`,
  `APP_TEST_IDS.copyPathButton`, `aria-label="Copy output path"`).
- **Preconditions:** `state === "succeeded"` AND `output_dir` non-empty (the
  actions block only renders then).
- **Observable output:** `navigator.clipboard.writeText(output_dir)` runs; on
  resolve the button label flips to `"Copied!"` for 1500 ms then back to
  `"Copy path"` (existing test: `test_copy_path_button_on_results_page`, which
  grants clipboard permission first).
- **Backend / side-effects:** None — pure client clipboard write of
  `spec.output_dir` (delivered in the GET response).
- **Bad-state / error:** If `navigator.clipboard` is unavailable / permission
  denied, the `.then()` never fires so the label stays "Copy path" (no crash,
  no toast). A non-succeeded / not-found job shows no copy-path control at all.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_downloads.py::test_copy_path_button_on_results_page`,
  `::test_copy_path_absent_when_not_succeeded`

### B-RESULTS-009 — Re-run the whole job

- **Flow(s):** —
- **Trigger:** User clicks "Re-run all" (`data-testid="rerun-all-button"`,
  `APP_TEST_IDS.rerunAllButton`, `aria-label="Re-run all"`).
- **Preconditions:** `state === "succeeded"` AND `output_dir` non-empty (actions
  block visible).
- **Observable output:** Button disables and shows `"Re-running…"` while the
  POST is in flight, then re-enables. On a successful POST the page bumps an
  internal `rerunKey` → `effectiveJobId` changes → `useOcrJob`/`useLongJob`
  restarts polling, so the pips cycle back through `queued`/`running` to
  `succeeded` (existing test: `test_rerun_all_button_on_results_page` asserts
  the POST fires).
- **Backend / side-effects:** `POST /api/jobs/{id}/rerun` (202) → resets ALL
  `status.pages` to `state="queued"`, `pages_done=0`, `state="queued"`, writes
  `project.json`, and re-enqueues `_pipeline_run_job` as a background task. This
  **re-OCRs every page through the dispatcher** (real engine in prod; the fake
  in Tier A) and rewrites the per-page sidecars/`.txt`, `combined.txt`, and the
  output mirror.
- **Bad-state / error:** A non-ok POST is now **surfaced** as a
  `data-testid="results-rerun-error"` banner (`Re-run failed (HTTP <status>)…`)
  rather than silently swallowed; the page does not crash (header still shows).
  A network error is surfaced the same way. (Previously the failure was
  swallowed in `catch {}` with no user feedback.)
- **Tier(s):** A and B
  > Tier B: re-run-all genuinely re-OCRs through the real engine, so the Tier-B
  > slice (`test_real_ocr_rerun.py`) asserts the regenerated page text still
  > matches ground truth (≥60% overlap) after a rerun — proving rerun is not a
  > no-op.
- **Regression:** yes (fixed in commit `aa6759a` — a non-ok rerun POST is now
  surfaced as an error banner instead of being silently swallowed)
- **Test:** `tests/e2e/test_click_paths_downloads.py::test_rerun_all_button_on_results_page`,
  `::test_rerun_error_is_surfaced`;
  Tier B: `tests/e2e/test_real_ocr_rerun.py::test_real_ocr_rerun_regenerates_text`

### B-RESULTS-010 — Open a page (navigate to PageView)

- **Flow(s):** —
- **Trigger:** User clicks a `page-row` (or presses Enter/Space on it —
  rows are `tabIndex={0}`, `role="row"`, `aria-label="Open page <page_name>"`).
- **Preconditions:** ≥1 `page-row` rendered (job has pages).
- **Observable output:** App navigates to `/jobs/<id>/pages/<page_idx>`; the
  PageView screen (`data-testid="page-view-page"`) renders for that page
  (covered in detail by `screen-page-view.md`).
- **Backend / side-effects:** None at click time — PageView does its own
  `GET /api/pages/<id>/<idx>` (+ image + words) fetches.
- **Bad-state / error:** A bad page index (e.g. `/api/pages/<id>/9999`) 404s on
  the page API; a missing sidecar/image is handled by PageView's own fetches
  (out of scope here, covered in `screen-page-view.md`).
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_results.py::test_open_page_navigates_to_page_view`,
  `::test_open_page_bad_index_returns_404`

### B-RESULTS-011 — Open a non-existent / deleted job (404 → error alert)

- **Flow(s):** —
- **Trigger:** Navigate to `/jobs/:id` for an id with no `project.json` — a
  never-existed id, OR a stale recent-project / bookmarked id whose project was
  deleted (this is the case explicitly **deferred here from B-HOME-013**).
- **Preconditions:** No `project.json` at `<PROJECTS_ROOT>/<id>/`.
- **Observable output:** `data-testid="results-page"` renders a DISTINCT
  not-found block — `data-testid="results-not-found"` (`role="alert"`) with the
  text **"Job not found. It may have been deleted."** AND a back-to-home link
  (`data-testid="results-back-home"`, navigates to `/`). NOT the generic
  `results-error` block. Polling is stopped (404 is terminal). (Previously a
  404 collapsed into the generic "Error fetching job status." because the fetch
  threw on any non-ok and the dead "Job not found." branch was unreachable.)
- **Backend / side-effects:** `GET /api/jobs/{id}` → **404** `{detail:"Project
  not found"}` (`read_project` raises `FileNotFoundError`). The fetch layer now
  raises `JobFetchError(status=404)`; `useOcrJob` sets `notFound` and re-throws
  so `useLongJob` stops. No writes.
- **Bad-state / error:** This record IS the 404/deleted-job bad path; the good
  contrast is B-RESULTS-001. A malformed (traversal) id → **400** from the same
  endpoint (a 400 is not a 404, so it shows the generic error block, not the
  not-found block — B-RESULTS-001 bad path covers it). This is the path
  deferred here from B-HOME-013 (stale recent-row → 404-on-open).
- **Tier(s):** A
- **Regression:** yes (fixed in commit `279d4b4` — the fetch layer now passes
  the HTTP status through so a 404 renders the distinct "Job not found" block +
  back-home link instead of the generic fetch-error copy)
- **Test:** `tests/e2e/test_click_paths_results.py::test_unknown_job_shows_not_found_with_back_home`,
  `::test_back_home_link_returns_to_home`

### B-RESULTS-012 — Transient status-fetch error (network / 5xx)

- **Flow(s):** —
- **Trigger:** A `GET /api/jobs/{id}` poll fails with a network error or 5xx
  while the job exists (server hiccup mid-poll).
- **Preconditions:** Job exists; a poll throws.
- **Observable output:** The page shows a non-fatal `data-testid="results-error"`
  banner reading **"Error fetching job status — retrying…"** and **keeps
  polling** under the hood. It is NOT the terminal not-found block. When a poll
  recovers, the `transientError` flag clears and the loaded header/table render.
  (Previously a transient error flipped the hook to terminal `error` and stopped
  polling with no recovery.)
- **Backend / side-effects:** The failing `GET` (5xx / network). The fetch layer
  raises `JobFetchError(status=5xx|0)`; `useOcrJob` swallows it, sets
  `transientError`, and returns a non-terminal status so `useLongJob` re-arms
  the next poll. No writes. Cleared on the next successful poll.
- **Bad-state / error:** This IS the transient-error path; the good contrast is
  B-RESULTS-001/-002 (successful polls) and the recovery half of the test. A
  404 (terminal) is the distinct sibling — B-RESULTS-011.
- **Tier(s):** A
- **Regression:** yes (fixed in commit `279d4b4` — a transient 5xx/network poll
  error now keeps polling and clears on recovery, distinguished from a terminal
  404 by `JobFetchError.status`)
- **Test:** `tests/e2e/test_click_paths_results.py::test_transient_error_keeps_polling_then_recovers`

### B-RESULTS-013 — Progress message line (pipeline status text)

- **Flow(s):** —
- **Trigger:** The polled job carries a `progress_message`
  (e.g. "Loading OCR engine — first run may download ~200 MB…").
- **Preconditions:** `status.progress_message` is a non-empty string.
- **Observable output:** A `data-testid="job-progress-message"`
  (`APP_TEST_IDS.jobProgressMessage`) line renders with the message text,
  independent of running/succeeded state. Absent/null → the row is not rendered.
- **Backend / side-effects:** `status.progress_message` rides in the
  `GET /api/jobs/{id}` body; the pipeline stamps it into `project.json` and
  `update_page_result` preserves it across per-page updates.
- **Bad-state / error:** Missing/null message → no row.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_results.py::test_progress_message_renders_when_present`,
  `::test_progress_message_absent_when_null`

### B-RESULTS-014 — Delete a job removes ALL artifacts (no ResultsPage UI control)

- **Flow(s):** —
- **Trigger:** `DELETE /api/jobs/{id}`.
  > **There is NO delete control in ResultsPage.tsx.** The shared AppShell jobs
  > dock owns the current delete affordance. This record is the backend contract;
  > the Tier-A test drives the API directly and asserts the observable not-found
  > render when re-navigating to a deleted job.
- **Preconditions:** —
- **Observable output:** None on this screen at delete time (no UI trigger).
  After delete, re-navigating to `/jobs/<id>` renders the
  `data-testid="results-not-found"` block (B-RESULTS-011). API consumers get
  **200** `{"status":"deleted"}` when the project existed, **204** when it
  didn't (idempotent), **400** for a malformed id.
- **Backend / side-effects:** `delete_job` now reads the spec for `output_dir`
  BEFORE rmtree, then removes ALL THREE locations: the canonical project dir
  (`<PROJECTS_ROOT>/<id>/`), the user-visible output mirror (`spec.output_dir`),
  and the per-job meta sidecar (`<JOBS_META_ROOT>/<id>/`). Best-effort removal
  of the id from prefs `recent_projects`. (Previously only the canonical dir was
  removed, orphaning the mirror + meta so a deleted job's ZIP still downloaded.)
- **Bad-state / error:** Malformed id → 400. Deleting an unknown id → 204 no-op
  (idempotent). After delete, `GET /api/jobs/{id}/download` now **404s** (the
  mirror is gone — no orphan to fall back to).
- **Tier(s):** A
- **Regression:** yes (fixed in commit `5b05c11` — delete now also removes the
  output mirror + meta sidecar so a deleted job's ZIP no longer downloads)
- **Test:** `tests/e2e/test_click_paths_results.py::test_delete_removes_all_artifacts_and_blocks_download`,
  `::test_delete_missing_job_is_idempotent_204` (+ backend unit:
  `tests/test_routes_jobs.py::TestDeleteJob::test_delete_removes_output_mirror_and_meta_sidecar`,
  `::test_delete_then_download_is_404`)

## Known regressions

Records tagged `Regression: yes`, each with the fix commit and a one-line note
on what was wrong (load-bearing behaviors with a green covering test):

- **B-RESULTS-004** (`aa6759a`) — a failed job rendered only a bare red pip;
  now surfaces `status.error` text + a "Re-run job" affordance.
- **B-RESULTS-009** (`aa6759a`) — a non-ok `POST /rerun` was silently swallowed;
  now surfaced as an error banner. (Tier B proves rerun regenerates real text.)
- **B-RESULTS-011** (`279d4b4`) — a 404 collapsed into the generic "Error
  fetching job status." (the "Job not found." branch was dead code, because the
  fetch threw on any non-ok); now the fetch layer passes the status code through
  so a 404 renders a distinct "Job not found" block + back-to-home link.
- **B-RESULTS-012** (`279d4b4`) — a transient 5xx/network poll error went
  terminal with no retry; now it keeps polling and clears on recovery,
  distinguished from a terminal 404 via `JobFetchError.status`.
- **B-RESULTS-014** (`5b05c11`) — `DELETE /api/jobs/{id}` only removed the
  canonical project dir, orphaning the output mirror + meta sidecar so a deleted
  job's ZIP still downloaded; now delete removes all three locations.

The download include-filter (B-RESULTS-006/-007) is a NEW feature, not a
regression — it is intentionally untagged.

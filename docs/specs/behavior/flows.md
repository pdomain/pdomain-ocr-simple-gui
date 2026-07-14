---
Status: active
Owner: CT
Created: 2026-05-30
Last verified: 2026-07-14
Kind: spec
---

# Cross-unit flows — pdomain-ocr-simple-gui

## Adversarial Review

- **Stage:** post-implementation
- **Source:** 2026-07-14 docgraph migration; independent read-only review of current code, tests, history, and related docs.
- **Accepted findings:** The review compared the documented contract with current implementation and accepted the material deviations recorded in the architecture and authored context.
- **Effect on result:** Shipped behavior remains active; obsolete UI or workflow assumptions are not treated as current truth.
- **Implementation deviations:** The shared jobs dock and fixed job-level download buttons replaced parts of the earlier projected surfaces. Recent projects are written at job creation. Upload/edit/download coverage does not prove edited text is present in the exported ZIP.
- **Residual risks:** Per-page edits and reruns can leave the job output mirror stale; the download redesign remains deferred.

Flows are named multi-step scenarios that cross units. Each flow chains
already-locked per-unit behavior records (by ID) into one end-to-end
path. Flows are where the most valuable regression coverage lives.

A *unit* here is a screen: home → results → page-view. See
`/workspaces/ocr-container/docs/process/behavior-e2e-capture.md` for the
full process.

## Flows

### F-UPLOAD-OCR-DOWNLOAD-01 — Upload file, run OCR, review, edit, download

- **Units:** home → results → page-view → results
- **Steps (record IDs in order):**
  1. B-HOME-002 — pick PNG via file picker; chosen view + config form appear
  2. B-HOME-011 — submit config form; app navigates to /jobs/:id
  3. B-RESULTS-002 — results page shows progress bar; polls to terminal state
  4. B-RESULTS-003 — job reaches succeeded; per-page table renders
  5. B-RESULTS-010 — click a page-row to open page view
  6. B-PAGEVIEW-010 — edit OCR text and save; toast "Saved"; sidecar updated
  7. B-RESULTS-006 — return to results; click Download (.zip); browser
     download event fires; ZIP contains the edited per-page .txt
- **Expected end state (UI + backend):** ResultsPage has
  `data-testid="results-page"` visible with succeeded status. The managed
  download ZIP (GET /api/jobs/{id}/download) contains `page-001.txt`.
  The per-page sidecar `projects/<id>/pages/<name>.json` has `edited_text`
  set. The textarea on PageViewPage shows the user's saved edit when reopened.
- **Bad-state / error:** Upload API returns non-2xx (e.g. 413 oversize) →
  SourcePicker error alert; no navigation. Job fails (zero supported images)
  → results page shows failed state + error text + rerun affordance
  (B-RESULTS-004). Page edit save fails (PUT 500) → toast "Save failed";
  sidecar unchanged.
- **Tier(s):** A+B
- **Regression:** no
- **Test:** tests/e2e/test_flows.py::test_upload_ocr_download_flow

---

### F-RERUN-01 — Single-page rerun preserves prior edit

- **Units:** results → page-view
- **Steps (record IDs in order):**
  1. B-RESULTS-010 — click a page-row (seeded succeeded job) to open page view
  2. B-PAGEVIEW-010 — type and save an edit; sidecar `edited_text` set
  3. B-PAGEVIEW-013 — click "Re-run DocTR"; toast "Re-run complete"; page
     refreshes with new OCR output
  4. B-PAGEVIEW-010 (verify) — assert sidecar still carries `edited_text`
     from step 2 (rerun must not discard the user's save)
- **Expected end state (UI + backend):** Sidecar `pages/<name>.json` has both
  `text` (fresh OCR output, or preserved from fake dispatcher) and `edited_text`
  (the prior save preserved across the rerun). The textarea shows `edited_text`
  when reopened (GET /api/pages returns edited_text when present). Per-page
  `.txt` reflects the current OCR text from after the rerun.
- **Bad-state / error:** Rerun on a missing project → 404; page view toasts
  "Re-run failed". Source image missing → 404 ("Image file not found").
- **Tier(s):** A+B
- **Regression:** yes
- **Test:** tests/e2e/test_flows.py::test_rerun_preserves_edit_flow

---

### F-PREFS-ROUNDTRIP-01 — Prefs round-trip across reload

- **Units:** app-shell (settings modal) → home → app-shell (reload verify)
- **Steps (record IDs in order):**
  1. B-SHELL-006 — click gear icon; settings modal opens
  2. B-SHELL-008 — click Light theme radio; data-theme="light" applied;
     PUT /api/prefs fires; theme persisted
  3. B-SHELL-009 — click Compact density radio; data-density="compact" applied;
     PUT /api/prefs fires; density persisted
  4. B-SHELL-007 — click close button; settings modal closes
  5. B-SHELL-011 — reload the page; GET /api/prefs returns persisted values;
     shell re-applies theme="light" + density="compact" before first render
- **Expected end state (UI + backend):** After reload, `data-theme="light"` is
  on `documentElement` and `data-density="compact"` is on the `app-shell`
  element. `ui-prefs.json` (at `suite_data/ui-prefs.json`) carries
  `apps.pdomain-ocr-simple-gui.ui_prefs.theme === "light"` and
  `...density === "compact"`. Settings modal is closed.
- **Bad-state / error:** PUT /api/prefs returns 500 → sonner toast
  "Preferences not saved — server error" (B-SHELL-008 regression fix); prefs
  revert to defaults on reload.
- **Tier(s):** A
- **Regression:** yes
- **Test:** tests/e2e/test_flows.py::test_prefs_roundtrip_flow

---

### F-NOTFOUND-01 — Stale recent-project row leads to not-found block

- **Units:** home → results (404 path)
- **Steps (record IDs in order):**
  1. B-HOME-013 — click a recent-project row seeded via PUT /api/prefs with a
     project_id that has no `project.json` on disk; app navigates to /jobs/:id
  2. B-RESULTS-011 — results page polls GET /api/jobs/:id → 404; renders
     distinct "Job not found" block (data-testid="results-not-found") with a
     back-to-home link; polling stops
  3. B-RESULTS-011 (recovery) — click "Back to home" link; app navigates to /;
     home-page renders
- **Expected end state (UI + backend):** Home page is visible
  (`data-testid="home-page"`). Results page is no longer in the DOM. No crash,
  no generic error block, no infinite polling.
- **Bad-state / error:** This flow IS the error path. The happy contrast is
  B-HOME-013 on a job that exists (B-RESULTS-001).
- **Tier(s):** A
- **Regression:** yes
- **Test:** tests/e2e/test_flows.py::test_notfound_recovery_flow

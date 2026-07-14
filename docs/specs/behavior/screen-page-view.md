---
Status: active
Owner: CT
Created: 2026-05-29
Last verified: 2026-07-14
Kind: spec
---

# Behavior unit spec — Page view

## Adversarial Review

- **Stage:** post-implementation
- **Source:** 2026-07-14 docgraph migration; independent read-only review of current code, tests, history, and related docs.
- **Accepted findings:** The review compared the documented contract with current implementation and accepted the material deviations recorded in the architecture and authored context.
- **Effect on result:** Shipped behavior remains active; obsolete UI or workflow assumptions are not treated as current truth.
- **Implementation deviations:** The shared jobs dock and fixed job-level download buttons replaced parts of the earlier projected surfaces. Recent projects are written at job creation. Upload/edit/download coverage does not prove edited text is present in the exported ZIP.
- **Residual risks:** Per-page edits and reruns can leave the job output mirror stale; the download redesign remains deferred.

- **Unit type:** screen
- **Address:** `/jobs/:id/pages/:idx`
- **Implementation:** `frontend/src/pages/PageViewPage.tsx` (zoom layer via
  `frontend/src/components/PageViewerWithZoom.tsx`; image + word overlays via
  `ArtifactViewer` from `@pdomain/pdomain-ui/stages/PageWorkbench`, Konva-backed)
- **Backend / collaborators touched:** `routes/pages.py` (page metadata,
  image, PUT text, single-page rerun), `routes/words.py` (word overlays),
  `routes/jobs.py` (page count + download), `storage.py` (artifact IO)

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path. *Observable output* is whatever the user perceives on this
surface (DOM / toasts / route).

> **STATUS: LOCKED.** Records finalized after the maintainer interview and
> the M5 implementation pass. Tier-A tests live in
> `tests/e2e/test_click_paths_page_viewer.py`; the Tier-B real-engine rerun
> slices live in `tests/e2e/test_real_ocr_rerun.py`. Three records are tagged
> `Regression: yes` with their fix commit (B-PAGEVIEW-012, -013, -015). The
> cheatsheet record (formerly B-PAGEVIEW-018) was dropped to M6 — the `?`
> cheatsheet is owned by the AppShell ShortcutsProvider; this screen's own
> shortcut keys are captured inside its behavior records (nav j/k/←/→, save
> mod+s, rerun mod+r / mod+shift+r, download mod+shift+t/j / mod+d).

### Selectors (confirmed in `frontend/src/lib/testids.ts` + the components)

| Element | Selector | Source |
|---------|----------|--------|
| Page screen root | `data-testid="page-view-page"` | `APP_TEST_IDS.pageViewPage` |
| Canvas wrapper (carries `data-word-count`) | `data-testid="page-image-canvas"` | `APP_TEST_IDS.pageImageCanvas` |
| Zoom viewport (carries `data-zoom` / `data-fit-zoom` / `data-auto-fit`) | `data-testid="page-zoom-viewport"` | literal in `PageViewerWithZoom.tsx` (also `APP_TEST_IDS.pageZoomViewport`) |
| Zoom in / out / fit / 100% | `data-testid="page-zoom-in" \| "page-zoom-out" \| "page-zoom-fit" \| "page-zoom-100"` | literals in `PageViewerWithZoom.tsx` (mirrored in `APP_TEST_IDS`) |
| Prev / Next page | `data-testid="page-prev-button" \| "page-next-button"` | `APP_TEST_IDS.pagePrevButton` / `.pageNextButton` |
| Save edits | `data-testid="page-save-button"` | `APP_TEST_IDS.pageSaveButton` |
| Re-run DocTR / Tesseract | `data-testid="page-rerun-doctr" \| "page-rerun-tesseract"` | `APP_TEST_IDS.pageRerunDoctr` / `.pageRerunTesseract` |
| Download .txt / .json / .zip | `data-testid="page-download-text" \| "page-download-json" \| "page-download-both"` | `APP_TEST_IDS.pageDownloadText` / `.pageDownloadJson` / `.pageDownloadBoth` |
| Job progress message (job in flight) | `data-testid="page-progress-message"` | `APP_TEST_IDS.pageProgressMessage` |
| Editor toolbar | `data-testid="page-editor-toolbar"` | literal in `PageViewPage.tsx` |
| OCR text textarea | `get_by_label("OCR text")` (NOT a testid) | `aria-label="OCR text"` |

> DRAFT-NOTE: **Not every selector is DOM-addressable.** `ArtifactViewer` is
> Konva-backed and drops unknown `data-*` props (per the gotchas doc), so the
> word/image overlays themselves are NOT directly selectable. The wrapper
> `page-image-canvas` carries `data-word-count="N"` as the observable proxy.
> The textarea has no testid — tests select it by `aria-label="OCR text"`.

### On-disk artifacts (confirmed in `storage.py` + `routes/pages.py`)

PageViewPage's backend collaborators read/write the **same canonical project
tree** documented in `screen-results.md`. The page-relevant facts, re-confirmed
against `storage.py`:

- **Per-page sidecar** — `<PROJECTS_ROOT>/<project_id>/pages/<page_name>.json`.
  `<page_name>` is the source image filename (e.g. `scan.png`; the seeded
  fixtures use a bare `page-001`). Carries `text`, `width`, `height`, `words[]`,
  and `edited_text` (see `sidecar-shape-contract`). `GET /api/pages/{id}/{idx}`
  returns `edited_text` if a string (incl. `""`), else `text`, else the
  status `text_preview`.
- **Per-page text** — `<PROJECTS_ROOT>/<project_id>/pages/<page_name>.txt`.
  Rewritten by both save-text and rerun.
- **Combined text** — `<PROJECTS_ROOT>/<project_id>/combined.txt` — all per-page
  `.txt` joined by `\n\n`.
- **Output mirror** — `<spec.output_dir>/<page_stem>.txt`, `<page_stem>.json`,
  and a combined `<sanitized-spec.name>.txt`. **This is what the download zip
  streams.**

> **DOCUMENTED LIMITATION (pending the download-model redesign).**
> `write_combined_txt`, `write_output_combined_txt`, and `write_output_page_files`
> are called **ONLY** from `pipeline.run_project` (grep-confirmed). Neither
> `put_page_text` nor `rerun_page` in `routes/pages.py` regenerate them. So a
> **save** (and a **single-page rerun**) updates only the per-page sidecar
> `.json` + per-page `.txt` — it does **NOT** update `combined.txt` and does
> **NOT** update the `spec.output_dir` mirror (`.txt`/`.json`/combined). The
> download zip therefore serves **stale** text after an edit or rerun. Per the
> maintainer, this is a **pending-design limitation, not a regression** — it is
> NOT regression-tagged. The fix is the original-vs-modified split designed in
> [`docs/specs/2026-05-29-download-model.md`](../2026-05-29-download-model.md):
> a "modified" download reads the live sidecar `edited_text` rather than the
> mirror. The save/download records below assert sidecar + per-page `.txt`
> only and explicitly note the combined/mirror staleness.

### Page-fetch model (`PageViewPage.tsx`, confirmed)

- Three independent fetches on mount / `idx` change:
  `GET /api/jobs/{id}` (page count → enables Next), `GET /api/pages/{id}/{idx}`
  (text/dims), `GET /api/pages/{id}/{idx}/words` (overlays).
- `loading` starts `true` and is only set `false` inside the **success** branch
  of the page fetch. A non-ok page response (`!res.ok`) returns early WITHOUT
  clearing `loading`, so the canvas/editor never render. A network reject (the
  `.catch`) DOES clear `loading`. (See B-PAGEVIEW-014.)

### B-PAGEVIEW-001 — Page view loads (image canvas + editor + nav toolbar)

- **Flow(s):** —
- **Trigger:** Navigate to `/jobs/:id/pages/:idx` (clicking a `page-row` on
  ResultsPage, or a direct URL).
- **Preconditions:** Project exists; `page_idx` is in `status.pages`.
- **Observable output:** `data-testid="page-view-page"` renders a two-panel
  `PageSplitView` — canvas (`page-image-canvas` wrapping the zoom viewport +
  `ArtifactViewer`) on one side, the editor (`page-editor-toolbar` +
  `aria-label="OCR text"` textarea pre-filled with the page text) on the other.
  The nav toolbar shows the page indicator `"<page_name> (<n> / <total>)"`.
- **Backend / side-effects:** `GET /api/jobs/{id}` (page count),
  `GET /api/pages/{id}/{idx}` (text/dims), `GET /api/pages/{id}/{idx}/words`
  (overlays), `GET /api/pages/{id}/{idx}/image` (served by ArtifactViewer).
  No writes.
- **Bad-state / error:** Project missing or out-of-range index → page fetch
  404 → the dedicated `page-not-found` block (B-PAGEVIEW-015). Invalid id
  (banned chars) → backend 400, no crash.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_page_view_loads_canvas_editor_and_indicator`,
  `…::test_page_view_malformed_id_does_not_crash` (bad path)

### B-PAGEVIEW-002 — Word overlays render from the sidecar

- **Flow(s):** —
- **Trigger:** Page view loads with a sidecar that has a `words[]` list.
- **Preconditions:** `pages/<name>.json` exists with ≥1 word (the seeded
  fixtures carry 2 words).
- **Observable output:** The `page-image-canvas` wrapper reports
  `data-word-count="N"` (N ≥ 1); the Konva `ArtifactViewer` draws the bbox
  overlays (not directly DOM-addressable — the attribute is the proxy).
- **Backend / side-effects:** `GET /api/pages/{id}/{idx}/words` → `{words: [{text,
  bbox:{x,y,w,h}, confidence}]}` (normalized 0–1 coords). Prefers the prebaked
  flat `words[]`; falls back to the DocTR-tree walker for legacy sidecars.
  No writes.
- **Bad-state / error:** Words fetch fails / 404 → the `.catch` swallows it,
  `wordBboxes` stays `[]`, `data-word-count="0"`; the image still renders
  (overlays are non-critical). A sidecar with no words → `data-word-count="0"`.
- **Tier(s):** A
- **Regression:** no — word/bbox overlays are **render-only** (assert the
  `page-image-canvas` `data-word-count`). Word-click select/edit is FUTURE
  scope; no interaction test.
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_word_overlays_render_from_sidecar`,
  `…::test_word_overlays_empty_when_words_404` (bad path)

### B-PAGEVIEW-003 — Zoom in

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-zoom-in"` (or `mod` + scroll — n/a;
  no wheel handler).
- **Preconditions:** Page loaded (canvas present).
- **Observable output:** `page-zoom-viewport` `data-zoom` increases by ×1.25
  (clamped at 4.0); `data-auto-fit` flips to `"false"`.
- **Backend / side-effects:** None (client-only CSS transform).
- **Bad-state / error:** At the 4.0 ceiling, further clicks no-op (clamp); zoom
  never exceeds 4.0.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_zoom_in_increases_zoom_and_disables_auto_fit`,
  `…::test_zoom_in_clamps_at_ceiling` (bad path)

### B-PAGEVIEW-004 — Zoom out

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-zoom-out"`.
- **Preconditions:** Page loaded.
- **Observable output:** `data-zoom` decreases by ×0.8 (clamped at 0.1);
  `data-auto-fit` flips to `"false"`.
- **Backend / side-effects:** None.
- **Bad-state / error:** At the 0.1 floor, further clicks no-op (clamp).
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_zoom_out_decreases_zoom`,
  `…::test_zoom_out_clamps_at_floor` (bad path)

### B-PAGEVIEW-005 — Fit page to viewport

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-zoom-fit"`.
- **Preconditions:** Page loaded; viewport measured.
- **Observable output:** `data-auto-fit` becomes `"true"`; `data-zoom` snaps to
  the computed fit factor (`min(cw/pw, ch/ph)`) and re-tracks the fit on resize.
- **Backend / side-effects:** None.
- **Bad-state / error:** Unmeasured / zero-size container → `computeFit` returns
  `1` (safe default), no crash.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_fit_engages_auto_fit`,
  `…::test_fit_is_bad_path_safe_with_no_prior_zoom` (bad path)

### B-PAGEVIEW-006 — Reset to 100%

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-zoom-100"`.
- **Preconditions:** Page loaded (typically after a manual zoom).
- **Observable output:** `data-zoom` becomes exactly `1.0`; `data-auto-fit`
  becomes `"false"` (manual override, stops tracking fit).
- **Backend / side-effects:** None.
- **Bad-state / error:** Idempotent — clicking again leaves zoom at 1.0.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_reset_100_sets_zoom_to_one`,
  `…::test_reset_100_is_idempotent` (bad path)

### B-PAGEVIEW-007 — Default fit-to-page on load

- **Flow(s):** —
- **Trigger:** Page first renders (no manual zoom yet).
- **Preconditions:** Page loaded; viewport measured.
- **Observable output:** `data-auto-fit` starts `"true"`; `data-zoom` equals the
  fit factor (high-DPI scans are fit-to-container, not native size).
- **Backend / side-effects:** None.
- **Bad-state / error:** Before the viewport is measured (size 0), fit factor is
  `1`; once `ResizeObserver` fires it snaps to the real fit. Zoom state does
  **NOT** persist across page navigation (each `idx` remounts the wrapper at
  auto-fit) — confirmed intended.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_default_auto_fit_on_load`,
  `…::test_zoom_resets_to_auto_fit_on_navigation` (bad path — not persisted)

### B-PAGEVIEW-008 — Next page navigation

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-next-button"` (or `ArrowRight` / `j`).
- **Preconditions:** `pageIdx < page_count - 1` (Next enabled).
- **Observable output:** Route changes to `/jobs/:id/pages/:idx+1`; the page
  remounts with the next page's image/text/overlays; the page indicator updates.
- **Backend / side-effects:** Re-fetches `GET /api/pages/{id}/{idx+1}` (+ words +
  image) for the new index. No writes.
- **Bad-state / error:** On the **last** page, Next is `disabled` (`hasNext`
  false). If `GET /api/jobs/{id}` failed, `page_count` defaults to 0 → both
  Prev and Next disabled.
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_next_page_navigates_and_refetches`,
  `…::test_next_disabled_on_last_page` (bad path)

### B-PAGEVIEW-009 — Previous page navigation

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-prev-button"` (or `ArrowLeft` / `k`).
- **Preconditions:** `pageIdx > 0` (Prev enabled).
- **Observable output:** Route changes to `/jobs/:id/pages/:idx-1`; the page
  remounts with the previous page; indicator updates.
- **Backend / side-effects:** Re-fetches the previous index. No writes.
- **Bad-state / error:** On **page 0**, Prev is `disabled` (`hasPrev` false).
- **Tier(s):** A
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_prev_page_navigates_back`,
  `…::test_prev_disabled_on_first_page` (bad path)

### B-PAGEVIEW-010 — Save edited text (button)

- **Flow(s):** F-UPLOAD-OCR-DOWNLOAD-01 (edit step)
- **Trigger:** Edit the `aria-label="OCR text"` textarea, click
  `data-testid="page-save-button"` ("Save edits").
- **Preconditions:** Page loaded; `saveStatus === "idle"`.
- **Observable output:** Button label flips to `"Saving…"` while in flight; on
  success a sonner toast `"Saved"` appears; on failure a toast `"Save failed"`.
  Button re-enables (`saveStatus` → `idle`) in `finally`.
- **Backend / side-effects:** `PUT /api/pages/{id}/{idx}/text` body `{text}` →
  `{"status":"saved"}`. On disk: `pages/<name>.json` gets `edited_text` set, and
  `pages/<name>.txt` is rewritten. **Assert BOTH** via re-query (`GET
  /api/pages/{id}/{idx}` returns the edited text — `edited_text` wins) **and**
  on-disk sidecar `edited_text` + the per-page `.txt`.
- **Bad-state / error:** See B-PAGEVIEW-012 (bad project → 404; out-of-range idx
  → 404 after the fix). No client-side dirty guard / no autosave — Save is
  explicit (button + `mod+s`), server-confirmed; clicking Save with no edits
  PUTs the unchanged text and still toasts "Saved".
- **Tier(s):** A
- **Regression:** no
  > **Limitation (not a regression):** Save writes the sidecar `edited_text` +
  > per-page `.txt` ONLY. It does NOT update `combined.txt` and does NOT update
  > the `spec.output_dir` mirror that the download zip streams — so a download
  > after a save serves stale text. This is pending the download-model redesign
  > ([`2026-05-29-download-model.md`](../2026-05-29-download-model.md)), not a
  > re-broken behavior, so it is NOT regression-tagged. The test asserts the
  > sidecar + per-page `.txt` only.
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_save_button_persists_edit_to_sidecar_and_txt`,
  `…::test_save_bad_index_returns_404_no_write` (bad path)

### B-PAGEVIEW-011 — Save edited text via keyboard (mod+S)

- **Flow(s):** —
- **Trigger:** Press `Ctrl+S` / `⌘S` while on the page (`mod+s` binding).
- **Preconditions:** `!loading && saveStatus === "idle"`.
- **Observable output:** Same as B-PAGEVIEW-010 — `"Saved"` toast; the browser's
  native save dialog is suppressed (the shortcut handler intercepts).
- **Backend / side-effects:** Identical to B-PAGEVIEW-010 (`PUT .../text`).
- **Bad-state / error:** While `loading` or `saveStatus === "saving"`, the
  binding's `when` guard is false → keypress no-ops. A non-ok PUT toasts
  "Save failed".
- **Tier(s):** A
- **Regression:** no
  > Confirmed: `mod+s` fires and persists even with focus inside the textarea
  > (the e2e test edits the field, then presses `Control+s`, and the edit lands
  > on disk). Same combined.txt/mirror staleness limitation as B-PAGEVIEW-010.
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_save_via_mod_s_persists_edit`,
  `…::test_save_failure_toasts_save_failed` (bad path)

### B-PAGEVIEW-012 — Save bad-state (missing project / out-of-range page)

- **Flow(s):** —
- **Trigger:** `PUT /api/pages/{id}/{idx}/text` for a missing project, or an
  out-of-range `page_idx`.
- **Preconditions:** Project absent OR `page_idx` not in `status.pages`.
- **Observable output:** Driven at the API layer (the UI never lets you reach a
  bad project URL from a valid job). The frontend `handleSave` toasts
  `"Save failed"` on any non-ok response.
- **Backend / side-effects:** Missing project → **404** `"Project not found"`,
  no disk write. Out-of-range idx → **404** `"Page not found"` after the fix
  (was an uncaught `FileNotFoundError` → **500**), no stray sidecar/`.txt`
  written. Malformed id → **400**.
- **Bad-state / error:** This record *is* the bad path.
- **Tier(s):** A
- **Regression:** yes (fixed in commit `0adf03e` — `put_page_text` now resolves
  the page index against the project's pages list and returns a clean 404
  before any disk mutation; an out-of-range index previously raised an uncaught
  `FileNotFoundError` from `_page_name_for_idx`, surfacing as a 500)
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_out_of_range_save_is_clean_404`,
  `…::test_save_missing_project_returns_404` (bad path);
  `tests/test_routes_pages.py::TestPutPageText::test_put_text_on_out_of_range_index_returns_404_no_write`

### B-PAGEVIEW-013 — Re-run single page (DocTR)

- **Flow(s):** F-RERUN-01
- **Trigger:** Click `data-testid="page-rerun-doctr"` ("Re-run DocTR") (or
  `mod+r`).
- **Preconditions:** Page loaded; `rerunStatus === "idle"`; the page's source
  image file exists on disk.
- **Observable output:** Button label flips to `"Re-running…"` while in flight;
  on success the textarea is refetched/updated with the new OCR text and a toast
  `"Re-run complete"` appears; on failure a toast `"Re-run failed"`.
- **Backend / side-effects:** `POST /api/pages/{id}/{idx}/rerun` body
  `{engine:"doctr"}` → re-runs OCR **inline** through the dispatcher (fake in
  Tier A, real in Tier B), reorganizes + normalizes, then rewrites
  `pages/<name>.json` (fresh `build_sidecar_payload`) + `pages/<name>.txt`, and
  updates the per-page `state` in `project.json` (running → succeeded). Returns
  the updated `PageResult`; the handler then `GET /api/pages/{id}/{idx}` to
  refresh the editor. **The rerun PRESERVES the user's `edited_text`** — the
  refreshed OCR lands in the sidecar `text` + `words`, but a previously-saved
  `edited_text` is carried over (so GET, where `edited_text` wins, still returns
  the edit). Same combined.txt / output-mirror staleness limitation as the save
  records (pending the download-model redesign; not regression-tagged here).
- **Bad-state / error:** Missing project → 404; out-of-range idx → 404
  ("Page not found"); missing source image → 404 ("Image file not found").
  An OCR exception is caught and recorded as a per-page `state:"failed"`
  (response still 200 with `state:"failed"`) — the UI toasts "Re-run complete"
  on any 2xx. Engine omitted → falls back to `spec.engine`.
- **Tier(s):** A and B
  > Tier B: the real engine re-OCRs the actual source image (a genuine real-OCR
  > producer). The Tier-B citation lives on `tests/e2e/test_real_ocr_rerun.py`.
- **Regression:** yes (fixed in commit `d0edd9d` — `rerun_page` rewrote the
  sidecar via `build_sidecar_payload`, a fresh dict with no `edited_text`
  carry-over, silently discarding the user's saved edit; it now carries
  `edited_text` over from the prior sidecar)
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_rerun_doctr_toasts_and_preserves_saved_edit`,
  `…::test_rerun_doctr_missing_project_404` (bad path);
  `tests/test_routes_pages.py::TestPostPageRerun::test_rerun_preserves_edited_text`;
  Tier B: `tests/e2e/test_real_ocr_rerun.py::test_real_ocr_rerun_doctr_regenerates_text`

### B-PAGEVIEW-014 — Re-run single page (Tesseract)

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-rerun-tesseract"` ("Re-run Tesseract")
  (or `mod+shift+r`).
- **Preconditions:** Same as B-PAGEVIEW-013.
- **Observable output:** Same observable contract as B-PAGEVIEW-013 — toast +
  refreshed textarea.
- **Backend / side-effects:** `POST .../rerun` body `{engine:"tesseract"}` —
  identical write path (including the `edited_text` preservation from
  B-PAGEVIEW-013), but the dispatcher runs the Tesseract engine.
- **Bad-state / error:** Same as B-PAGEVIEW-013.
- **Tier(s):** A and B
  > Tier B: tesseract 5.3.0 + pytesseract 0.3.13 are installed, so a real
  > Tesseract rerun is viable. The Tier-B citation lives on
  > `tests/e2e/test_real_ocr_rerun.py`.
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_rerun_tesseract_toasts`,
  `…::test_rerun_tesseract_out_of_range_404` (bad path);
  Tier B: `tests/e2e/test_real_ocr_rerun.py::test_real_ocr_rerun_tesseract_regenerates_text`

### B-PAGEVIEW-015 — Page-fetch failure surfaces a not-found / error block

- **Flow(s):** —
- **Trigger:** Navigate to `/jobs/:id/pages/:idx` where the page fetch fails.
- **Preconditions:** `GET /api/pages/{id}/{idx}` returns non-ok (404 missing
  project / out-of-range idx; or other non-ok) OR the request rejects at the
  network layer.
- **Observable output:** A **404** page fetch renders the dedicated
  `data-testid="page-not-found"` block ("Page not found…" + a "Back to job"
  button); **any other** non-ok status (e.g. a 400/5xx) or a network reject
  renders the generic `data-testid="page-error"` block. In both cases `loading`
  is cleared and NO canvas (`page-image-canvas`) renders. Mirrors ResultsPage's
  `results-not-found` / `results-error` blocks.
- **Backend / side-effects:** `GET /api/pages/{id}/{idx}` → 404 / 400 / 5xx. No
  writes.
- **Bad-state / error:** This record *is* the bad path.
- **Tier(s):** A
- **Regression:** yes (fixed in commit `f9b8621` — a failed page fetch used to
  early-return without clearing `loading`, leaving the screen stuck on a blank
  shell with an empty disabled editor and no image; it now surfaces a
  `page-not-found` block on 404 and a `page-error` block otherwise. Two new
  testids registered in `frontend/src/lib/testids.ts`.)
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_page_fetch_404_shows_not_found_block`,
  `…::test_page_fetch_error_shows_error_block` (bad path — non-404);
  `frontend/src/pages/__tests__/PageViewPage.test.tsx` ("page-not-found" /
  "page-error" cases)

### B-PAGEVIEW-016 — Download from the page (txt / json / zip)

- **Flow(s):** —
- **Trigger:** Click `data-testid="page-download-text"` / `page-download-json`
  / `page-download-both` (or `mod+shift+t` / `mod+shift+j` / `mod+d`).
- **Preconditions:** `!loading`.
- **Observable output:** Browser navigates to (downloads) the job-level zip;
  no in-page state change. `.txt` → `?include=text`; `.json` → `?include=json`;
  `.zip` → `?include=text,json`.
- **Backend / side-effects:** `GET /api/jobs/{id}/download?include=<tokens>`
  streams the `spec.output_dir` mirror as a zip filtered by include tokens
  (same contract as B-RESULTS-006/-007 on ResultsPage). These per-page buttons
  are **whole-job** downloads exposed on the page screen, NOT a single-page
  download — see the download-model stub
  ([`2026-05-29-download-model.md`](../2026-05-29-download-model.md)), which
  designs a genuine per-page scope + an "original vs modified" split. Because
  the mirror is only refreshed by `run_project`, this serves stale text after a
  save/rerun (the same documented limitation as B-PAGEVIEW-010/-013).
- **Bad-state / error:** Output dir missing → 404 `"job output not found"`;
  unknown/empty token → 400. (Whole-job download, NOT per-page.)
- **Tier(s):** A
  > Captured here as the page-screen affordance; the full ZIP-membership
  > assertion is on B-RESULTS-006/-007 — this test asserts only that the button
  > triggers the download (Playwright download event) + the endpoint serves a
  > ZIP, to avoid duplicating the membership coverage.
- **Regression:** no
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_page_download_triggers_job_zip`,
  `…::test_page_download_unknown_token_400` (bad path)

### B-PAGEVIEW-017 — Job-progress message while a job is still running

- **Flow(s):** —
- **Trigger:** Open a page while the job state is `queued` or `running` and a
  `progress_message` is set.
- **Preconditions:** `jobStatus.state ∈ {queued, running}` AND
  `progress_message` non-empty.
- **Observable output:** `data-testid="page-progress-message"` renders the
  `jobStatus.progress_message` text in the nav toolbar.
- **Backend / side-effects:** Driven by the single `GET /api/jobs/{id}` fetch
  (no polling on this screen). No writes.
- **Bad-state / error:** Job not in flight, or no message → the span is absent.
- **Tier(s):** A
- **Regression:** no
  > PageViewPage fetches job status ONCE (no polling), so the message is a
  > single snapshot, not live — confirmed intended for the page screen.
- **Test:** `tests/e2e/test_click_paths_page_viewer.py::test_progress_message_renders_for_running_job`,
  `…::test_progress_message_absent_for_succeeded_job` (bad path)

> **Dropped: keyboard-cheatsheet record (formerly B-PAGEVIEW-018).** The `?`
> cheatsheet and `ShortcutsProvider` are owned by the AppShell, so the
> cheatsheet behavior moves to M6 (`screen-app-shell.md`). This screen's own
> shortcut keys (nav ←/→ + j/k, save `mod+s`, rerun `mod+r` / `mod+shift+r`,
> download `mod+shift+t/j` / `mod+d`) are captured inside the records above
> (B-PAGEVIEW-008/-009/-011/-013/-014/-016). The B-PAGEVIEW-018 slot is
> intentionally retired and not reused.

## Known regressions

Three records on this screen are tagged `Regression: yes`, each with its fix
commit and a green covering test:

- **B-PAGEVIEW-012** — out-of-range save returned **500** (uncaught
  `FileNotFoundError`); now a clean **404** with no disk write. Fix `0adf03e`.
- **B-PAGEVIEW-013** — single-page rerun silently discarded the user's saved
  `edited_text`; now preserved across the rerun. Fix `d0edd9d`.
- **B-PAGEVIEW-015** — a failed page fetch left the screen stuck on a blank
  loading shell; now surfaces a `page-not-found` (404) / `page-error` block.
  Fix `f9b8621`.

**Documented limitation (NOT regression-tagged):** save + single-page rerun
update only the per-page sidecar `.json` + `.txt`; they do NOT regenerate
`combined.txt` or the `spec.output_dir` mirror, so the download zip serves
stale text after an edit/rerun. This is pending the download-model redesign
([`2026-05-29-download-model.md`](../2026-05-29-download-model.md)).

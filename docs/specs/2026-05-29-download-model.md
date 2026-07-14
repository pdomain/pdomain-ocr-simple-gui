---
Status: draft
Owner: CT
Created: 2026-05-29
Last verified: 2026-07-14
Kind: spec
---

# Download model — design (stub / future)

## Adversarial Review

- **Stage:** design
- **Source:** 2026-07-14 docgraph migration; independent read-only review of current code, tests, history, and related docs.
- **Accepted findings:** The review compared the documented contract with current implementation and accepted the material deviations recorded in the architecture and authored context.
- **Effect on result:** Shipped behavior remains active; obsolete UI or workflow assumptions are not treated as current truth.
- **Implementation deviations:** The shared jobs dock and fixed job-level download buttons replaced parts of the earlier projected surfaces. Recent projects are written at job creation. Upload/edit/download coverage does not prove edited text is present in the exported ZIP.
- **Residual risks:** Per-page edits and reruns can leave the job output mirror stale; the download redesign remains deferred.

- **Date:** 2026-05-29
- **Repo:** pdomain-ocr-simple-gui
- **Status:** stub / future — not scheduled, no implementation

## Motivation

The download surface conflates two things the maintainer wants to separate:
the OCR engine's **original** output and the user's **modified** text.

Today every download — the per-page buttons on PageViewPage (`B-PAGEVIEW-016`)
and the "Download results" button on ResultsPage (`B-RESULTS-006` /
`B-RESULTS-007`) — hits the same job-level endpoint
`GET /api/jobs/{id}/download?include=<tokens>` and streams the `spec.output_dir`
mirror as a ZIP. That mirror is written **only** by `pipeline.run_project`; it
is never refreshed by a save-text edit or a single-page rerun
(`B-PAGEVIEW-010` / `B-PAGEVIEW-013` backend notes). So after a user edits a
page or reruns one, the ZIP serves **stale** text. This is a documented
limitation, not a re-broken behavior (so it is NOT regression-tagged).

The deeper reason a naive "just regenerate the mirror on save" fix is wrong:
arbitrary user edits to the flat text **cannot be reflected back into the
bounding-box JSON** (the word geometry no longer matches the edited string).
So a single ZIP can't honestly carry both "the engine's word-boxed JSON" and
"the user's hand-edited text" as one coherent artifact.

## The proposed model

Split download into two intents, at two scopes:

### Two intents (what's in the ZIP)

- **Original download** — a ZIP of the engine output exactly as produced:
  per-page `.json` (bbox sidecars) **+** per-page `.txt` (the engine's text)
  **+** images. This is reproducible and self-consistent: the JSON and the
  `.txt` describe the same OCR pass.
- **Modified download** — **text only** (`.txt`, and/or a combined `.txt`).
  No JSON, because the user's edits can't be mapped back onto the word boxes.
  This is the "give me my corrected transcript" path. It reflects
  `edited_text` where the user saved one, otherwise the engine text.

### Two scopes (which pages)

- **Per-page download** (PageViewPage, `B-PAGEVIEW-016`) — just the page the
  user is looking at. Today the per-page buttons actually trigger the
  **whole-job** ZIP; the new model gives them a genuine single-page scope.
- **Project-level "Download all"** (ResultsPage, `B-RESULTS-006/007`) — every
  page in the job, as one archive.

## Reconciliation with M4's managed-only include-filter (load-bearing)

M4 just shipped (`B-RESULTS-006`, commit `aa6759a`) a managed-mode-only
**include-filter**: text/json checkboxes on the ResultsPage download button
that drive the `?include=text,json` query param (images always included). That
filter is a *member selector on the single combined ZIP* — it is the seam this
download model has to grow out of, not replace blindly. When this spec is
picked up it MUST reconcile with that filter:

- The "original vs modified" intent is a **superset** of today's text/json
  toggle: "original" ≈ `include=text,json(+images)`, "modified" ≈
  `include=text` but sourced from the **live sidecar `edited_text`**, not the
  stale `output_dir` mirror.
- The filter currently renders **only** in managed output mode
  (`showDownload = state==='succeeded' && output_mode==='managed'`); the new
  model has to decide whether per-page / non-managed downloads get the same
  intent split or stay mirror-based.
- The staleness fix is implicit in "modified": a modified download must read
  the canonical projects tree (`pages/<name>.json` `edited_text` + per-page
  `.txt`), not the `output_dir` mirror that only `run_project` refreshes.

## Scope (when picked up)

- A backend endpoint (or `?mode=original|modified` on the existing download
  route) that streams from the canonical projects tree for "modified" and the
  mirror (or freshly-regenerated mirror) for "original".
- A per-page download scope distinct from the whole-job scope.
- UI: distinct affordances for original vs modified on both PageViewPage and
  ResultsPage; fold the M4 text/json filter into the original intent.
- Behavior records updated: `B-PAGEVIEW-010` (save backend effect),
  `B-PAGEVIEW-016` (per-page download), `B-RESULTS-006/007` (project download)
  re-pointed at the new model; the stale-mirror limitation note retired.

## Out of scope for this stub

- No implementation, no tests, no endpoint yet.
- Mapping edited text back onto word boxes (explicitly impossible for
  arbitrary edits — that is *why* "modified" is text-only).

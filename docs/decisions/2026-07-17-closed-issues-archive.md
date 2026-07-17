---
Status: retired
Owner: CT
Created: 2026-07-17
Last verified: 2026-07-17
Kind: decision
---

<!-- markdownlint-disable -->
<!-- Verbatim archive of deleted GitHub issues; issue bodies keep their
     original headings and code fences, so lint rules are disabled. -->

# Closed-Issue Archive — 37 issues

## Agent Index

- **Kind:** decision
- **Status:** retired
- **Read when:** you need the text of a `pdomain-ocr-simple-gui` GitHub issue that was deleted from the tracker on 2026-07-17.
- **Search terms:** closed issues, archive, tombstone, deleted issues, backlog, issue history, #NNN

## Context

The `pdomain-ocr-simple-gui` GitHub tracker
(`github.com/pdomain/pdomain-ocr-simple-gui`) held 37 issues, all
closed as `COMPLETED`. Unlike a normal completion, **the work was not
implemented** — most items are open bugs, security findings, and chores that
were closed without a fix and without being migrated anywhere.

Before deletion, the still-open work was carried forward into
[`../roadmap.md`](../roadmap.md) (2026-07-17), each item tagged with its
originating `#NNN`. This file preserves the full text — body and comments
verbatim — so the detail behind each roadmap line survives.

## Decision

Delete all 37 issues from GitHub and preserve their full text here.
Per this repo's docs convention (see [`../README.md`](../README.md)), the
archive is committed and then removed from the working tree in a follow-up
commit: **Git history is the tombstone.** The working tree stays clean; the
record is permanent.

## Consequences

- The complete text survives in Git history even though the file is removed from
  the tree and the GitHub issues are gone. To read it, find the commit that
  added this file and run
  `git show <sha>:docs/decisions/2026-07-17-closed-issues-archive.md`.
- GitHub issue links (`#NNN` and `/issues/NNN` URLs) no longer resolve; the
  numbers are preserved here and in [`../roadmap.md`](../roadmap.md) for
  cross-reference.
- The forward-tracking of open work now lives only in `../roadmap.md`; keep it
  current.

## Supersedes / Superseded-by

Supersedes nothing; superseded by nothing.

Issues archived (by number): #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20, #21, #22, #23, #24, #25, #26, #27, #28, #29, #30, #31, #32, #33, #34, #36, #37, #38.

---

## #1 — bug: rerun_page corrupts page 0 when re-running any page != 0

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/1

**Body**

## Summary

`rerun_page` in `routes/pages.py` creates a `single_image_spec` pointing at the target image file, then calls `run_project` with it. `run_project` iterates images starting at `idx=0` and calls `update_page_result(page_idx=0)`. This overwrites page 0 in the stored project. The target page (at `page_idx`) is set to "queued" at line 122 but is never updated by `run_project`; the re-read workaround on lines 135–138 reads the corrupted state.

**Impact:** Every re-run of any page other than page 0 silently corrupts page 0 and leaves the target page stuck as "queued".

## Location

`src/pd_ocr_simple_gui/routes/pages.py:83–138`

---

## #2 — bug: get_page_image always 404 when source_path is a single file

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/2

**Body**

## Summary

`get_page_image` computes `image_path = Path(spec.source_path) / page_name` (lines 58–59). When `source_path` is a file (not a directory), this produces an invalid nested path such as `/scans/foo.png/foo.png`, which never exists on disk.

**Impact:** Single-file projects cannot display page images — every `GET /api/pages/{id}/{idx}/image` returns 404.

## Location

`src/pd_ocr_simple_gui/routes/pages.py:57–62`

---

## #3 — bug: ResultsPage JobStatus interface has name/output_dir fields that don't exist in backend ProjectStatus

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/3

**Body**

## Summary

`ResultsPage.tsx` declares a `JobStatus` interface with `name: string` (line 18) and `output_dir?: string` (line 22). `GET /api/jobs/{project_id}` returns `status.model_dump()` from `ProjectStatus`, which has no `name` or `output_dir` field — only `project_id`, `state`, `page_count`, `pages_done`, `pages`.

**Impact:**
- `<h1>{name}</h1>` (line 135) always renders blank — the results page has no title.
- The `state === "succeeded" && output_dir` guard (line 152) is always falsy — the "Open folder" link is permanently hidden even after a successful run.

## Location

`frontend/src/pages/ResultsPage.tsx:16–24`, `:128–155`
`src/pd_ocr_simple_gui/models.py:37–44`

**Comments (1)**

- **ConcaveTrillion** (2026-05-19):
  Fixed: `ProjectStatus` model already has `name` and `output_dir` fields; `get_job` enriches via `model_copy`. `JobStatus` TS interface in `ResultsPage.tsx` already matches backend schema. CI green.

---

## #4 — bug: ResultsPage PageRow uses name but backend PageResult has page_name

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/4

**Body**

## Summary

`ResultsPage.tsx` declares a `PageRow` interface with `name: string` (line 11), but `PageResult` in `models.py` uses `page_name: str` (line 31). The backend serialises with model field names, so `page.name` is always `undefined` at runtime.

**Impact:** Every row in the results table has a blank page-name cell; `aria-label` says "Open page undefined".

## Location

`frontend/src/pages/ResultsPage.tsx:9–14`, `:200–202`
`src/pd_ocr_simple_gui/models.py:31`

**Comments (1)**

- **ConcaveTrillion** (2026-05-19):
  Fixed: `PageRow` interface in `ResultsPage.tsx` already uses `page_name` matching backend `PageResult.page_name`. CI green.

---

## #5 — bug: PageViewPage PageData interface doesn't match GET /api/pages/{id}/{idx} response

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/5

**Body**

## Summary

`PageViewPage.tsx` expects `PageData` with `text`, `name`, `state`, `width`, `height` (lines 19–26). `get_page` in `routes/pages.py` returns `read_page_sidecar(spec, page_idx)` — the raw doctr page dict — which has no top-level `text`, `name`, `state`, `width`, or `height` fields.

**Impact:**
- OCR text textarea always starts blank (`data.text ?? ""` → `undefined`).
- Canvas dimensions always fall back to 800×1200 (`pageData?.width ?? 800`).
- Page name and state display nothing.

## Location

`frontend/src/pages/PageViewPage.tsx:19–26`, `:75–78`, `:152–155`
`src/pd_ocr_simple_gui/routes/pages.py:29–38`

**Comments (1)**

- **ConcaveTrillion** (2026-05-19):
  Fixed: `routes/pages.py` `get_page` already returns `PageResponse` with `page_name`, `state`, `text`, `width`, `height`. `PageData` interface in `PageViewPage.tsx` matches. CI green.

---

## #6 — bug: JobConfigDialog initialises language as "eng" (Tesseract) but DocTR expects "en"

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/6

**Body**

## Summary

`JobConfigDialog.tsx` initialises language state as `"eng"` (line 32) — a Tesseract 3-letter code. `ProjectSpec` defaults `language` to `"en"` and passes it directly to the OCR dispatcher. DocTR uses ISO-639-1 codes (`"en"`), not Tesseract codes (`"eng"`).

**Impact:** Default DocTR jobs receive an invalid language code, likely causing a language-lookup error or silent fallback.

## Location

`frontend/src/components/JobConfigDialog.tsx:32`
`src/pd_ocr_simple_gui/models.py` (`ProjectSpec.language`)

---

## #7 — ci: make ci omits frontend-test — Vitest suite never runs in CI

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/7

**Body**

## Summary

The `ci:` Makefile target (line 109) is `setup lint typecheck test smoke frontend-build`. It does not include `frontend-test` (the Vitest suite). Both peer FastAPI+SPA repos (`pd-prep-for-pgdp`, `pd-ocr-labeler-spa`) include `frontend-test` in their `ci` target.

**Impact:** All Vitest tests are silently skipped in every CI run.

## Location

`Makefile:109`

---

## #8 — ci: make ci omits pre-commit-check — hooks never run in CI

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/8

**Body**

## Summary

The `ci:` Makefile target (line 109) does not include `pre-commit-check`. The workspace canonical pattern (followed by `pd-book-tools`, `pd-prep-for-pgdp`, `pd-ocr-labeler-spa`) wires `pre-commit-check` into `ci`.

**Impact:** gitleaks, check-*, uv-lock-check, basedpyright hooks are never exercised in CI.

## Location

`Makefile:109`

---

## #9 — bug: app.py StaticFiles mount baked at import time — cannot be patched in tests, broken in CI

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/9

**Body**

## Summary

`app.py` lines 130–131:
\`\`\`python
if (_FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR / "assets"), name="assets")
\`\`\`

This runs at module import time using the real `_FRONTEND_DIR`. The `test_routes_root.py` fixture patches `_FRONTEND_DIR` via `monkeypatch`, but by then the mount decision has already been made. In any CI run where the frontend hasn't been built, `/assets` is never mounted — even if the test creates the directory.

**Fix:** Pass `check_dir=False` to `StaticFiles` and always register the mount unconditionally (matching the pattern in `pd-prep-for-pgdp`).

## Location

`src/pd_ocr_simple_gui/app.py:129–131`
`tests/test_routes_root.py`

---

## #10 — bug: rerun_page blocks asyncio event loop for full OCR duration

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/10

**Body**

## Summary

`rerun_page` (line 133) calls `await run_project(single_image_spec, dispatcher, _cb)` directly in the route handler. Single-page DocTR OCR takes several seconds of CPU-bound work. This starves all other requests during re-run.

**Fix:** Enqueue as a `BackgroundTasks` task (or `asyncio.to_thread`) and return `202 Accepted` immediately, consistent with how `create_job` works.

## Location

`src/pd_ocr_simple_gui/routes/pages.py:133`

---

## #11 — api: POST /api/jobs returns 200 OK for an async-queued job (should be 202 Accepted)

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/11

**Body**

## Summary

`POST /api/jobs` enqueues OCR as a `BackgroundTask` and returns `200 OK` (default, no `status_code=` annotation on the route). The job is not yet complete when the response is sent. `pd-prep-for-pgdp` uses `202 Accepted` for all job-submission endpoints.

**Impact:** Clients that distinguish `200` (done) from `202` (queued) will misinterpret the response.

## Location

`src/pd_ocr_simple_gui/routes/jobs.py:94`

---

## #12 — api: all FastAPI route handlers missing response_model= declarations

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/12

**Body**

## Summary

All 9+ route handlers across `routes/jobs.py`, `routes/pages.py`, and `routes/prefs.py` lack `response_model=` on their `@router.*` decorators. Without it, FastAPI emits `{}` response schemas in the OpenAPI spec and performs no response-shape validation at runtime.

**Affected routes:** `create_job`, `list_jobs`, `get_job`, `delete_job`, `rerun_job`, `get_page`, `put_page_text`, `rerun_page`, `get_prefs`, `put_prefs`.

## Location

`src/pd_ocr_simple_gui/routes/jobs.py`
`src/pd_ocr_simple_gui/routes/pages.py`
`src/pd_ocr_simple_gui/routes/prefs.py`

---

## #13 — style: remove # --- divider banners from e2e and smoke test files

`author:` ConcaveTrillion · `created:` 2026-05-19 · `closed:` 2026-05-19 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/13

**Body**

## Summary

`tests/e2e/test_job_flow.py` and `tests/smoke/test_e2e.py` use `# -----------` divider lines as visual section separators. The workspace CONVENTIONS.md classifies these as high-confidence auto-fix violations: function names and blank lines provide sufficient structure.

**Lines to remove:**
`tests/e2e/test_job_flow.py`: lines 29, 31, 53, 55, 101, 103
`tests/smoke/test_e2e.py`: lines 21, 23, 51, 53

## Location

`tests/e2e/test_job_flow.py`
`tests/smoke/test_e2e.py`

---

## #14 — chore: document all lint-rule suppressions (lint-deviations.md)

`author:` ConcaveTrillion · `created:` 2026-05-21 · `closed:` 2026-05-22 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/14

**Body**

## Summary

Apply the workspace `CONVENTIONS.md` rule **"Document every lint-rule
suppression"** to `pd-ocr-simple-gui`. `pd-book-tools` is the reference implementation.

Part of the cross-cut rollout tracked in ConcaveTrillion/ocr-container-meta#291.

## Tasks

- [ ] Grep for all standing suppressions: `# pyright: ignore`, `# type: ignore`,
      `# noqa`, and ruff `[tool.ruff.lint]` `ignore` / `per-file-ignores`, and TS `eslint-disable` / `@ts-expect-error` / `@ts-ignore`.
- [ ] Add a concise inline rationale at each suppression point (or remove the
      suppression and fix the underlying issue if it isn't warranted).
- [ ] Create `docs/conventions/lint-deviations.md` cataloguing every remaining
      deviation (rule, tool, file locations, justification). Tag any genuinely
      unclear case "needs review" rather than inventing a rationale.
- [ ] Prefer tool-native codes correctly
      (`# pyright: ignore[reportRuleName]`, not `# type: ignore[mypy-code]`).

## Reference

- Rule: workspace `CONVENTIONS.md` → "Document every lint-rule suppression"
- Reference implementation: `pd-book-tools/docs/conventions/lint-deviations.md`
- Cross-cut tracking issue: ConcaveTrillion/ocr-container-meta#291

**Comments (1)**

- **ConcaveTrillion** (2026-05-22):
  docs/conventions/lint-deviations.md created in docs/drift-audit-2026-05-22 branch (commit 663f252). Documents all standing ruff global ignores, per-file ignores, inline noqa/type:ignore suppressions, and frontend eslint-disable comments with justifications.

---

## #15 — Re-align frontend to current @concavetrillion/pd-ui API

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-22 · `state:` CLOSED (COMPLETED)

`labels:` (none)

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/15

**Body**

The frontend build and vitest suite fail against the current `@concavetrillion/pd-ui` due to upstream export drift (see ConcaveTrillion/pd-ui issue for the breaking changes: JobStatusPip->StatusPip, JobState removed, BaseJobConfigDialog/BaseJobConfig/PageSplitView removed).

Re-align frontend imports to the current pd-ui export surface and update vitest mocks accordingly. ~28 vitest failures, confirmed pre-existing (not caused by the meta#291 lint-rationale work). Blocked on the pd-ui side decision (restore exports vs. migration note).

**Comments (1)**

- **ConcaveTrillion** (2026-05-22):
  Fixed in commit 9cd1378 on feat/pd-ui-api-realign. Bumped pd-ui to 0.1.0-alpha.1 and replaced broken pnpm-workspace.yaml placeholder. All 46 vitest tests pass; make ci green.

---

## #16 — security: encoded project_id traversal can delete the project store

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-23 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:high

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/16

**Body**

## Finding
Encoded `project_id` path traversal can recursively delete the project store.

## Evidence
- `src/pd_ocr_simple_gui/storage.py:15` joins `_PROJECTS_ROOT / project_id` directly.
- `src/pd_ocr_simple_gui/routes/jobs.py:143` exposes `DELETE /api/jobs/{project_id}`.
- `src/pd_ocr_simple_gui/routes/jobs.py:148` checks the derived path.
- `src/pd_ocr_simple_gui/storage.py:111` calls `shutil.rmtree(proj_dir)`.

## Impact
`DELETE /api/jobs/%2e` deletes the projects root because the decoded route parameter is joined directly into `_PROJECTS_ROOT` and passed to `shutil.rmtree()`. Any client that can reach the API can delete outside the intended per-project directory.

## Recommended fix
Validate `project_id` as a UUID on every route, reject decoded dot segments/separators, resolve the target, and require it to be a direct child of `_PROJECTS_ROOT`. Add regression tests for encoded dot segments.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-23):
  Fixed in commit 7e04fa9 on branch fix/security-16-project-id-traversal. Added validate_project_id() in storage.py with allowlist + path containment check; applied to all 7 endpoints in routes/jobs.py and routes/pages.py; regression tests in tests/test_security_project_id.py.

---

## #17 — security: caller-controlled source_path can disclose local image files

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:medium

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/17

**Body**

## Finding
Arbitrary local image disclosure through caller-controlled `source_path`.

## Evidence
- `src/pd_ocr_simple_gui/routes/jobs.py:25` accepts `source_path`.
- `src/pd_ocr_simple_gui/routes/jobs.py:99` persists the client-supplied path.
- `src/pd_ocr_simple_gui/pipeline.py:36` resolves that path directly.
- `src/pd_ocr_simple_gui/routes/pages.py:81` reconstructs the image path.
- `src/pd_ocr_simple_gui/routes/pages.py:91` returns it with `FileResponse`.

## Impact
Any client that can reach the API can create a job pointing at readable local image files or directories and then stream page image bytes through the app.

## Recommended fix
Add a per-launch capability token/auth gate, canonicalize and allowlist source roots, reject symlinks/out-of-root files, and validate served file types.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #18 — security: unauthenticated OCR endpoints allow resource exhaustion

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:medium

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/18

**Body**

## Finding
Unauthenticated OCR job and rerun endpoints allow CPU/GPU denial of service.

## Evidence
- `src/pd_ocr_simple_gui/routes/jobs.py:94` exposes unauthenticated job creation.
- `src/pd_ocr_simple_gui/routes/jobs.py:119` starts background OCR work.
- `src/pd_ocr_simple_gui/pipeline.py:42` collects matching image children without limits.
- `src/pd_ocr_simple_gui/pipeline.py:142` runs OCR per image.
- `src/pd_ocr_simple_gui/routes/pages.py:112` and `:156` expose inline reruns.

## Impact
Repeated submissions or reruns against large directories can consume OCR workers, CPU/GPU, and disk.

## Recommended fix
Add auth/capability checks, rate limits, queue limits, max page/file-size limits, OCR timeouts, and cancellation.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #19 — security: suite launch API can spawn local processes without auth

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:medium

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/19

**Body**

## Finding
Mounted suite launch API allows unauthenticated local process spawning.

## Evidence
- `src/pd_ocr_simple_gui/app.py:94` mounts suite routes.
- `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:47` exposes `POST /api/suite/launch`.
- `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:55` calls the launcher.
- `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/sibling_spawn.py:92` builds the command.
- `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/sibling_spawn.py:93` calls `subprocess.Popen`.

## Impact
Reachable clients can launch enabled suite apps from the local registry, consuming resources and exposing additional local services.

## Recommended fix
Protect suite routes with the same auth/capability token and consider disabling launch routes unless explicitly configured.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #20 — deps: upgrade Vite for dev-server path traversal advisory

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:medium, area:deps

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/20

**Body**

## Finding
Vite dev server path traversal advisory is present.

## Evidence
- `frontend/package.json:29` declares Vite.
- `frontend/pnpm-lock.yaml:51` resolves `vite` to `5.4.21`.
- `frontend/pnpm-lock.yaml:1881` and `:3890` confirm the locked package.
- `pnpm audit` reports `GHSA-4w7w-66w2-5vf9`.

## Impact
Affected Vite dev servers can expose optimized dependency source map files outside the intended project boundary under advisory conditions.

## Recommended fix
Upgrade Vite to a patched line and update compatible frontend tooling pins.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-27):
  Closed by feat/reconciliation-b3.2-b4.1-b4.2 — Vite upgraded to 7.3.3 (patches GHSA-4w7w-66w2-5vf9). Also upgraded vitest 1→3 so it resolves vite 7 instead of pulling in vite 5.

---

## #21 — deps: upgrade esbuild via Vite toolchain for CORS advisory

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:medium, area:deps

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/21

**Body**

## Finding
esbuild dev server CORS advisory is present via Vite.

## Evidence
- `frontend/pnpm-lock.yaml:3190` locks `esbuild@0.21.5`.
- `frontend/pnpm-lock.yaml:3890` shows it is pulled through Vite.
- `pnpm audit` reports `GHSA-67mh-4wv8-2f99`.

## Impact
Malicious websites can read responses from the esbuild development server, disclosing local dev-served source content.

## Recommended fix
Upgrade the Vite toolchain so `esbuild` resolves to a patched version, or add a compatible `pnpm` override.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-27):
  Closed by feat/reconciliation-b3.2-b4.1-b4.2 — esbuild now resolves to 0.27.7 via Vite 7.3.3 (^0.27.0 dep), patching GHSA-67mh-4wv8-2f99. pnpm audit now reports 0 vulnerabilities.

---

## #22 — deps: add integrity hashes for private pd-book-tools artifacts

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:medium, area:deps

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/22

**Body**

## Finding
Private `pd-book-tools` artifacts are locked without integrity hashes.

## Evidence
- `uv.lock:1770` resolves `pd-book-tools==0.13.0` from the private index.
- `uv.lock:1795` records the source artifact URL without a hash.
- `uv.lock:1797` records the wheel artifact URL without a hash.

## Impact
The lockfile does not cryptographically bind the private release artifacts; a changed release asset or compromised private index could be consumed without the same hash protection used for PyPI artifacts.

## Recommended fix
Publish private simple-index entries with hash fragments/metadata or pin direct artifacts with hash verification and regenerate the lock.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #23 — security: metadata and prefs APIs are unauthenticated

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/23

**Body**

## Finding
Project metadata and preferences are readable/writable without authentication.

## Evidence
- `src/pd_ocr_simple_gui/routes/jobs.py:123` lists all projects.
- `src/pd_ocr_simple_gui/routes/jobs.py:128` returns project names and output paths.
- `src/pd_ocr_simple_gui/routes/prefs.py:14` reads prefs.
- `src/pd_ocr_simple_gui/routes/prefs.py:28` writes prefs.
- `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:58` and `:63` expose suite prefs.

## Impact
Reachable clients can read project names, output paths, recent-project data, and suite preferences, then modify preferences.

## Recommended fix
Require auth/capability checks and avoid returning absolute local paths where not needed.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #24 — privacy: self-host or remove third-party Google Fonts

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/24

**Body**

## Finding
The local UI loads third-party Google Fonts.

## Evidence
- `frontend/index.html:7` and `:9`.
- `src/pd_ocr_simple_gui/frontend/index.html:7` and `:9`.

## Impact
Opening the local OCR app makes third-party network requests that disclose IP, user agent, and usage timing.

## Recommended fix
Self-host bundled fonts or use system fonts; add a restrictive CSP once external font loading is removed.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-27):
  Closed by feat/reconciliation-b3.2-b4.1-b4.2 — vendored Inter v20 + JetBrains Mono v24 latin woff2 into frontend/public/fonts/, replaced Google Fonts CDN links with local @font-face rules.

---

## #25 — privacy: avoid exposing output_dir as raw file URL

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/25

**Body**

## Finding
Output directory is exposed as a raw `file://` href.

## Evidence
- `frontend/src/pages/ResultsPage.tsx:153` conditionally renders the output action.
- `frontend/src/pages/ResultsPage.tsx:156` sets `href={`file://${output_dir}`}`.

## Impact
Full local paths are exposed in the DOM and link target, leaking usernames and directory structure to browser extensions, screenshots, or copied links.

## Recommended fix
Replace the raw link with a backend open-folder action keyed by project ID, or render only sanitized path text.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #26 — frontend: suite launcher opens tabs without noopener

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/26

**Body**

## Finding
Suite launcher opens new tabs without `noopener`.

## Evidence
- `frontend/src/App.tsx:91` enables the launcher.
- `frontend/node_modules/@concavetrillion/pd-ui/dist/RightPanel-Z4PwHl58.js:19` calls `window.open(url, "_blank")`.

## Impact
A launched sibling app can keep a `window.opener` reference and navigate the OCR GUI tab.

## Recommended fix
Update the launcher to use `noopener,noreferrer` and explicitly null `opener` if needed. This may need an upstream `@concavetrillion/pd-ui` fix plus a dependency bump here.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #27 — deps: replace editable pd-ocr-ops sibling dependency with immutable pin

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:low, area:deps

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/27

**Body**

## Finding
`pd-ocr-ops` is an unversioned editable sibling dependency.

## Evidence
- `pyproject.toml:17` declares `pd-ocr-ops` without a version constraint.
- `pyproject.toml:56` maps it to `../pd-ocr-ops` editable.
- `uv.lock:1801` locks it as an editable source.

## Impact
Builds and audits depend on mutable workspace state outside this repo rather than an immutable artifact, version, or commit.

## Recommended fix
Depend on a versioned `pd-ocr-ops` artifact or pinned git commit; keep editable use as a local override.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-27):
  Verified: pdomain-ocr-ops was already pinned to pdomain-index-pip registry (>=0.2.2, resolved to 0.2.3). No editable/path reference remains. Issue is closed as resolved.

---

## #28 — ci: pin GitHub Actions and uv version

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-27 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:low, area:ci

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/28

**Body**

## Finding
CI uses mutable action/tool references.

## Evidence
- `.github/workflows/ci.yml:20` uses `actions/checkout@v4`.
- `.github/workflows/ci.yml:21` uses `astral-sh/setup-uv@v4`.
- `.github/workflows/ci.yml:23` sets `version: latest`.

## Impact
CI behavior can change when action tags or the latest `uv` release move. A compromised mutable tag or tool release would execute in CI.

## Recommended fix
Pin third-party actions to commit SHAs and pin `uv` to an exact reviewed version.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #29 — security: log suite unregister failures instead of swallowing them

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-26 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/29

**Body**

## Finding
Bandit B110 reported a swallowed exception.

## Evidence
- `src/pd_ocr_simple_gui/__main__.py:52`

## Impact
Unregister failures can leave stale suite registry entries without operator visibility.

## Recommended fix
Log the exception at debug/warning level or return a clear CLI error where appropriate.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

---

## #30 — security: log suite self-registration failures

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-26 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/30

**Body**

## Finding
Bandit B110 reported a swallowed exception.

## Evidence
- `src/pd_ocr_simple_gui/app.py:61`

## Impact
Startup can silently skip suite registration, making local routing/launch state hard to audit.

## Recommended fix
Log the exception with context while preserving best-effort startup behavior.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-26):
  Shipped in B1 logging-hygiene milestone (commit 4bf9440, merged via 91b021c). Each swallowed-exception site now uses logger.exception() with structured context; graceful-degradation flows preserved.

---

## #31 — security: log suite route mounting failures

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-26 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/31

**Body**

## Finding
Bandit B110 reported a swallowed exception.

## Evidence
- `src/pd_ocr_simple_gui/app.py:99`

## Impact
Suite API and health-route availability can silently diverge from expectations.

## Recommended fix
Log the exception with context and expose health diagnostics for disabled suite routes.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-26):
  Shipped in B1 logging-hygiene milestone (commit 4bf9440, merged via 91b021c). Each swallowed-exception site now uses logger.exception() with structured context; graceful-degradation flows preserved.

---

## #32 — security: log failed-status persistence failures

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-26 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/32

**Body**

## Finding
Bandit B110 reported a swallowed exception.

## Evidence
- `src/pd_ocr_simple_gui/routes/jobs.py:90`

## Impact
A background OCR failure can leave stale queued/running state with no durable error trail.

## Recommended fix
Log the secondary persistence failure and retain the original job failure context.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-26):
  Shipped in B1 logging-hygiene milestone (commit 4bf9440, merged via 91b021c). Each swallowed-exception site now uses logger.exception() with structured context; graceful-degradation flows preserved.

---

## #33 — security: log recent-project preference update failures

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-26 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/33

**Body**

## Finding
Bandit B110 reported a swallowed exception.

## Evidence
- `src/pd_ocr_simple_gui/routes/jobs.py:200`

## Impact
Deleted projects can remain in recent-project metadata without visibility.

## Recommended fix
Log the prefs update failure at debug/warning level.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-26):
  Shipped in B1 logging-hygiene milestone (commit 4bf9440, merged via 91b021c). Each swallowed-exception site now uses logger.exception() with structured context; graceful-degradation flows preserved.

---

## #34 — security: log unreadable project directories skipped from listings

`author:` ConcaveTrillion · `created:` 2026-05-22 · `closed:` 2026-05-26 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/34

**Body**

## Finding
Bandit B110 reported a swallowed exception.

## Evidence
- `src/pd_ocr_simple_gui/storage.py:106`

## Impact
Malformed or tampered project records disappear from listings without audit visibility.

## Recommended fix
Log skipped project directories with enough context for troubleshooting.

Report: `docs/research/2026-05-22-deep-code-review-security-scan.md`

**Comments (1)**

- **ConcaveTrillion** (2026-05-26):
  Shipped in B1 logging-hygiene milestone (commit 4bf9440, merged via 91b021c). Each swallowed-exception site now uses logger.exception() with structured context; graceful-degradation flows preserved.

---

## #36 — security: PDOMAIN_OCR_FAKE_DISPATCHER test seam active in production binary with no warning

`author:` ConcaveTrillion · `created:` 2026-05-31 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low, area:tests

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/36

**Body**

## Finding

`app.py:58–61` checks `os.environ.get("PDOMAIN_OCR_FAKE_DISPATCHER")` at startup and, if set to any non-empty value, silently replaces the real `LocalStageDispatcher` with `FakeStageDispatcher`. The fake dispatcher is shipped inside `src/pdomain_ocr_simple_gui/testing/` and is therefore included in the production wheel.

Any operator who accidentally sets this env var (e.g., by copying a `.env.test` template) will get deterministic fake OCR output with no error or warning.

## Evidence

- `src/pdomain_ocr_simple_gui/app.py:58–61` — unconditional env-var branch in production startup path
- `src/pdomain_ocr_simple_gui/testing/fake_dispatcher.py` — test artifact included in the production package

## Recommendation

- Emit a loud `logger.warning()` (or raise a startup error) when `PDOMAIN_OCR_FAKE_DISPATCHER` is set
- Consider moving `testing/` to a dev-only extras group so it is excluded from production installs
- Document the variable in the runbook as test-only

## Source

Identified in 2026-05-31 security gap analysis (post-behavior-e2e-pilot review).

---

## #37 — test: e2e prefs-reset fixture can overwrite real user prefs if PD_SUITE_DATA_DIR is unset

`author:` ConcaveTrillion · `created:` 2026-05-31 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:bug, status:backlog, priority:low, area:tests

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/37

**Body**

## Finding

The e2e `conftest.py` correctly redirects all storage env vars to per-worker tmp dirs and uses a `reset_prefs` autouse fixture to reset prefs via `PUT /api/prefs` before each test. However, if a developer runs `make e2e-browser` without `PD_SUITE_DATA_DIR` set to a tmp path, and a real `pdomain-ops` suite installation exists on the machine, the prefs reset fixture will overwrite the real `ui-prefs.json` file.

This is a developer environment integrity hazard, not a production security issue.

## Evidence

- `tests/e2e/conftest.py` — `reset_prefs` autouse fixture; `live_server_url` fixture does not assert `PD_SUITE_DATA_DIR` is a tmp path before starting the server

## Recommendation

Assert that `PD_SUITE_DATA_DIR` is set to a tmp path in the session-scoped fixture before starting the live server; fail loudly if absent or if it resolves to a path under `~/.local/share/`.

## Source

Identified in 2026-05-31 security gap analysis (post-behavior-e2e-pilot review).

---

## #38 — chore: fake_dispatcher.py uses getattr() on typed request object

`author:` ConcaveTrillion · `created:` 2026-05-31 · `closed:` 2026-05-31 · `state:` CLOSED (COMPLETED)

`labels:` kind:chore, status:backlog, priority:low, area:tests

`url:` https://github.com/pdomain/pdomain-ocr-simple-gui/issues/38

**Body**

## Finding

`src/pdomain_ocr_simple_gui/testing/fake_dispatcher.py` uses `getattr(req, \"images\", None)` on the batch request object, which drops static typing to `Any`. This is test-seam-only code with no direct production risk, but it establishes a pattern inconsistent with workspace convention (see `feedback_avoid_getattr_on_typed.md`).

## Recommendation

Replace with an `isinstance` narrowing check + direct attribute access, or annotate the parameter with the correct concrete type so `req.images` is statically safe.

## Source

Identified in 2026-05-31 security gap analysis (post-behavior-e2e-pilot review). Informational severity — test code only.

---

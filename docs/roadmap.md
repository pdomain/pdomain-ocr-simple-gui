---
Status: active
Owner: CT
Created: 2026-07-17
Last verified: 2026-07-17
Kind: plan
---

<!-- markdownlint-configure-file { "MD024": { "siblings_only": true } } -->

# pdomain-ocr-simple-gui Roadmap

## Agent Index

- **Kind:** plan
- **Status:** active
- **Read when:** deciding what to work on next in `pdomain-ocr-simple-gui`.
- **Search terms:** roadmap, backlog, now next later, open priorities, contract mismatch, security, deps, CI

This roadmap is the source of truth for planned work in
`pdomain-ocr-simple-gui`. It absorbs the repository's GitHub issue backlog,
migrated 2026-07-17. Each item keeps its originating `#NNN` for cross-reference
with the verbatim issue archive preserved in Git history — see
[`decisions/2026-07-17-closed-issues-archive.md`](decisions/2026-07-17-closed-issues-archive.md)
(committed then removed; retrieve with `git show <sha>:<path>`).

The 37 source issues were closed as `COMPLETED` but were **not** implemented;
this file carries the still-open work forward so nothing is lost.

## Goal

Maintain the standing list of open priorities for the OCR GUI: FastAPI routes,
the React/Vite front end, the contracts between them, CI, dependency hygiene,
and local-server security. Keep reusable OCR and dispatch logic upstream in
`pdomain-book-tools` and `pdomain-ops`; this repository owns the web app and its
integration behavior.

## Architecture

`pdomain-ocr-simple-gui` is a local web server: a FastAPI backend serves a
React/Vite single-page app and drives OCR through `pdomain-ops`'
`LocalStageDispatcher`, which wraps `pdomain-book-tools`. The app opens the
user's browser on launch. It is the Phase 3 reference consumer that validates
the dispatcher.

## Tech Stack

Python FastAPI backend with Pydantic models; React plus TypeScript on Vite for
the front end, tested with Vitest; `pdomain-book-tools` for OCR and
`pdomain-ops` for suite plumbing. Development and verification run through `uv`,
pytest, Ruff, and basedpyright.

## Global Constraints

Keep reusable OCR and dispatch logic upstream — the GUI owns routes, UI, and
glue only. **Backend and front end share contracts:** every TypeScript
interface must match the Pydantic model it consumes, and every route should
declare its `response_model`. The app is an unauthenticated local server, so
treat caller-controlled paths and IDs as untrusted. Run `make ci AI=1` before
committing.

## Work clusters

Several open items are one piece of work split across issues. Do them together:

- **Frontend/backend contract alignment:** #3, #4, #5, #12 — the React
  interfaces (`JobStatus`, `PageRow`, `PageData`) drifted from the Pydantic
  models (`ProjectStatus`, `PageResult`, page payloads), and no route declares
  `response_model`. Fix the models and interfaces in one pass so they can't
  drift again.
- **`rerun_page` correctness:** #1, #10 — the single-page rerun both corrupts
  page 0 and blocks the event loop for the full OCR duration. One rewrite of the
  rerun path addresses both.
- **CI coverage gaps:** #7, #8, #28 — `make ci` skips the Vitest suite and
  pre-commit hooks, and actions/uv are unpinned. One pass over the `ci` target
  and workflow closes all three.
- **Vite toolchain advisories:** #20, #21 — the Vite dev-server path-traversal
  and esbuild CORS advisories both clear by upgrading the Vite toolchain once.
- **Suite-plumbing failure logging (Bandit B110):** #29, #30, #31, #32, #33,
  #34 — six swallowed exceptions across suite register/unregister, route
  mounting, status persistence, and preference/listing reads. One sweep replaces
  bare `except: pass` with logging.

---

## Now — highest priority

### Contract & correctness bugs

- [bug/high] Fix `rerun_page` corrupting page 0 when re-running any page != 0 (#1)
- [bug/high] Fix `get_page_image` 404 when `source_path` is a single file (#2)
- [bug/high] Align `ResultsPage` `JobStatus` interface with backend `ProjectStatus` (#3)
- [bug/high] Align `ResultsPage` `PageRow` (`name`) with backend `PageResult` (`page_name`) (#4)
- [bug/high] Align `PageViewPage` `PageData` with the `GET /api/pages/{id}/{idx}` response (#5)
- [bug/high] Fix `JobConfigDialog` language init (`"eng"` Tesseract vs DocTR `"en"`) (#6)
- [bug/high] Stop baking the `StaticFiles` mount at import time so tests and CI can patch it (#9)
- [bug/high] Re-align the front end to the current `@concavetrillion/pd-ui` API (build + Vitest fail) (#15)

### Security

- [bug/high] Block encoded `project_id` path traversal that can delete the project store (#16)

## Next — medium priority

### Contract & API correctness

- [bug/medium] Stop `rerun_page` blocking the asyncio event loop for the full OCR duration (#10)
- [api/medium] Return `202 Accepted` for async-queued `POST /api/jobs` (currently `200`) (#11)
- [api/medium] Declare `response_model=` on all FastAPI route handlers (#12)

### CI

- [ci/medium] Include `frontend-test` (Vitest) in the `make ci` target (#7)
- [ci/medium] Include `pre-commit-check` in the `make ci` target (#8)

### Security

- [bug/medium] Prevent caller-controlled `source_path` from disclosing local image files (#17)
- [bug/medium] Authenticate or rate-limit OCR endpoints against resource exhaustion (#18)
- [bug/medium] Require auth before the suite-launch API can spawn local processes (#19)

### Dependency hygiene

- [chore/medium] Upgrade Vite for the dev-server path-traversal advisory (#20)
- [chore/medium] Upgrade esbuild via the Vite toolchain for the CORS advisory (#21)
- [chore/medium] Add integrity hashes for private `pd-book-tools` artifacts (#22)

## Later — low priority

### Security & privacy

- [bug/low] Authenticate the project metadata and preferences APIs (#23)
- [chore/low] Self-host or remove third-party Google Fonts (#24)
- [bug/low] Stop exposing `output_dir` as a raw `file://` URL (#25)
- [bug/low] Add `noopener` to suite-launcher tabs (#26)
- [bug/low] Log suite unregister failures instead of swallowing them (#29)
- [bug/low] Log suite self-registration failures (#30)
- [bug/low] Log suite route-mounting failures (#31)
- [bug/low] Log failed-status persistence failures (#32)
- [bug/low] Log recent-project preference update failures (#33)
- [bug/low] Log unreadable project directories skipped from listings (#34)
- [bug/low] Warn when the `PDOMAIN_OCR_FAKE_DISPATCHER` test seam is active in a production binary (#36)

### Dependencies

- [chore/low] Replace the editable `pd-ocr-ops` sibling with an immutable pin (#27)
- [ci/low] Pin GitHub Actions and the uv version (#28)

### Tests & style

- [bug/low] Stop the e2e prefs-reset fixture from overwriting real prefs when `PD_SUITE_DATA_DIR` is unset (#37)
- [chore/low] Replace `getattr()` on the typed request object in `fake_dispatcher.py` (#38)
- [style/low] Remove `# ---` divider banners from e2e and smoke test files (#13)
- [chore/low] Document all lint-rule suppressions in `lint-deviations.md` (#14)

## Ideas

_No untriaged requests._

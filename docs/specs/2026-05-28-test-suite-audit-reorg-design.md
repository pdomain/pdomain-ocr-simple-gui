# Test suite audit, reorganization & full UI coverage — design

- **Date:** 2026-05-28
- **Repo:** pdomain-ocr-simple-gui
- **Status:** design (approved); plan to follow via writing-plans

## Problem

The repo has substantial test volume (168 backend pytest functions across 28
files; 83 vitest cases across 11 files; 7 hybrid Playwright files) but three
structural weaknesses:

1. **Duplicated setup.** Per-test fixtures (`client`, `client_with_source`,
   `project_with_image`, `secured_client`, `projects_root`, mocked-prefs
   clients) are redefined across ~7 backend files. There is no shared backend
   `conftest.py` — only one under `tests/e2e/`. Frontend specs re-stub config,
   prefs, and the fetch/api layer by hand in each file.
2. **Inconsistent organization and a duplicate.** Frontend specs are split
   between `__tests__/` subdirs and co-located files. `pages/PageViewPage.test.tsx`
   (13 cases) and `pages/__tests__/PageViewPage.test.tsx` (5 cases) are a
   duplicate pair.
3. **The UI is not exercised end-to-end.** The 7 Playwright tests are
   **hybrid**: they create jobs via the httpx API, then only assert that a page
   renders. The real interactive click paths — drag-drop upload, file-picker
   upload, path input, config form, submit, settings/prefs forms,
   recent-projects click-through, download buttons — are never driven through
   the browser.

Additionally, an unknown number of tests are low-value: tautological,
asserting a mock rather than behavior, or lacking an explicit bad-state case
validated against a good state.

## Goals

- A committed **coverage & quality matrix** that is the source of truth for
  every later change and is checkable during execution.
- Shared backend fixtures and frontend test utilities; no hand-rolled setup
  duplication.
- One canonical, consistently-located spec per unit; the duplicate removed.
- Every weak test **strengthened in place** to assert real behavior with an
  explicit good state and a bad state validated against it.
- **Full UI click-path coverage** via Playwright driving the real browser
  against a stubbed OCR backend — fast, hermetic, CI-runnable on every push —
  with one real-OCR smoke test retained in the opt-in slow/e2e group.

## Non-goals

- No application/runtime code changes beyond what is required to inject a fake
  OCR dispatcher for e2e (dependency override / env seam).
- No change to the product's feature set or UI.
- No reorganization purely for style where the audit shows no duplication or
  gap — but consolidation of proven duplication IS in scope (approved).

## Design

### Section 1 — Audit pass (diagnostic layer)

Produce a coverage & quality matrix, committed under `docs/` (e.g.
`docs/research/2026-05-28-test-audit-matrix.md`):

- **Backend:** each of the 168 tests mapped to (module under test, behavior
  asserted, mock depth, has-good-state?, has-bad-state?), with a reason code
  for weak tests: `tautological`, `asserts-mock`, `no-bad-case`, `duplicate`,
  `over-coupled`.
- **Frontend:** same columns for the 83 vitest cases.
- **Click-path matrix:** every interactive element × coverage level
  (`none` / `unit` / `hybrid-e2e` / `full-e2e`). Elements: drag-drop, file
  upload, path input, engine select, language select, output toggles
  (save_json, combined_txt), submit, recent-projects rows, status badge,
  download zip, download txt, retry, page-row nav, zoom in/out, pan,
  fit-to-screen, prev/next page, settings/prefs forms.

This matrix gates the rest: execution is checked against it.

### Section 2 — Backend consolidation

- Create `tests/conftest.py` hoisting the duplicated fixtures into shared,
  parametrizable fixtures.
- Add factory helpers (`make_project_spec`, `make_page_result`,
  `write_seeded_project`) so tests stop hand-rolling Pydantic objects and tmp
  layouts.
- Standardize the `AsyncClient` + `ASGITransport` + `monkeypatch.setenv`
  storage-root pattern into one fixture.

### Section 3 — Frontend consolidation & restructure

- Remove the duplicate `pages/PageViewPage.test.tsx`; merge into one canonical
  spec under `__tests__/`.
- Normalize layout: all specs in `__tests__/` next to their unit.
- Add a shared test-utils module (`renderWithProviders`, fetch/api mock
  handlers, fixture builders) consumed by every spec.

### Section 4 — Strengthen weak tests in place

For every test tagged in Section 1: rewrite to assert real behavior with an
explicit **good state** (valid input → expected output/state) and a **bad
state validated against it** (invalid/edge input → specific error, not "didn't
crash"). Reduce mocks toward real collaborators where cheap (e.g. real storage
round-trips on tmp dirs). Delete only proven duplicates.

### Section 5 — Full UI click-path e2e (stubbed OCR, real browser)

- Add a **fake OCR dispatcher** injected via FastAPI dependency override / env,
  returning deterministic fixture pages — fast, hermetic, CI on every push.
- Playwright tests drive the real UI for every click path in the Section-1
  matrix, replacing the hybrid API-driven shortcuts: drag-drop upload,
  file-picker upload, path input (local mode), config form → submit, status
  polling → succeeded, download zip + txt, recent-projects click-through,
  page-row nav, zoom/pan/prev-next, settings/prefs forms.
- Retain one real-OCR smoke test in the opt-in `slow`/`e2e` group.
- Wire the stubbed click-path suite into `make ci` as a fast browser tier;
  real-OCR stays opt-in.

### Section 6 — Best-practice guardrails (cross-cutting)

One behavior per test; `test_<behavior>_<condition>_<expected>` naming; AAA
structure; no logic in tests; deterministic (no real sleeps/clocks/network);
good-vs-bad pairing as a reviewable rule; honest markers (`slow`/`e2e`).

## Sequencing

Section 1 (audit) → Sections 2 & 3 (consolidate, parallelizable) → Section 4
(strengthen) → Section 5 (e2e). Section 6 is applied throughout. Each section
is a reviewable milestone.

## Testing / verification

- After each section: `make ci AI=1` green (lint, typecheck, frontend-build,
  backend tests, frontend tests).
- New fast browser e2e tier green in CI.
- Real-OCR smoke retained and runnable via `make e2e-browser`.
- Coverage matrix re-checked: every `none`/`hybrid-e2e` click path moved to
  `full-e2e`; every weak-tagged test resolved (strengthened or proven-duplicate
  deleted).

## Risks

- Fake-dispatcher seam must mirror the real dispatcher's contract or e2e gives
  false confidence — validate the seam against the retained real-OCR smoke.
- Playwright browser tier adds CI time; mitigated by stubbed backend.
- Strengthening tests may surface real product bugs — expected; triage as
  found.

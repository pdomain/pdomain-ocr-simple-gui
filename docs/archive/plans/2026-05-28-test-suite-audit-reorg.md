# Test Suite Fixture Consolidation & DoD Gate — Implementation Plan (Revised)

> **Preamble:** The original six-milestone plan (M1–M6) was written 2026-05-28.
> The behavior-E2E pilot (merged 2026-05-29, commit `c6af2ee`) shipped M1
> (audit matrix), M4 (weak-test strengthening), and M5 (fake-OCR seam +
> Playwright click-paths) in full. This revised plan covers only the remaining
> work: M2 (backend inline-client cleanup), M3 (frontend test-utils adoption),
> and M6 (DoD gate). Three milestones instead of six.

**Spec:** `docs/archive/specs/2026-05-28-test-suite-audit-reorg-design.md`

**Repo rules:** always `make ci AI=1` before committing; `uv run pytest` not
`python -m pytest`; TDD-first; commit locally, no push.

---

## M2 — Backend inline-client cleanup

**Goal:** Eliminate inline `AsyncClient` blocks that M4 added to test files
but never migrated to shared conftest fixtures. The behaviors are already
tested — this is pure fixture migration. Tests must pass identically after
each task.

**Background:** `tests/conftest.py` already provides: `projects_root`,
`async_client`, `client_with_source`, `project_with_image`, `secured_client`,
`client_with_mock_prefs`, `client_no_prefs`, `use_fake_dispatcher`. Use these
instead of inline `async with AsyncClient(transport=ASGITransport(app=app), ...)`
blocks.

### Task 2.A — Migrate `test_routes_prefs.py` (5 inline clients)

**Files:** `tests/test_routes_prefs.py`

- [ ] **Step 1:** Read the 5 test methods that hand-roll
  `async with AsyncClient(...)`. For each, identify which conftest fixture
  covers it (`client_with_mock_prefs`, `client_no_prefs`). Note any
  `monkeypatch` calls — keep those before the fixture usage.
- [ ] **Step 2:** Replace each inline client block with the matching fixture
  parameter. Verify argument names match what conftest provides.
- [ ] **Step 3:** Run: `uv run pytest tests/test_routes_prefs.py -v`
  Expected: all tests PASS, same count as before.
- [ ] **Step 4:** Commit:
  `git add tests/test_routes_prefs.py && git commit -m "test: adopt shared fixtures in test_routes_prefs (M4 additions)"`

### Task 2.B — Migrate `test_routes_jobs.py` (12 inline clients)

**Files:** `tests/test_routes_jobs.py`

- [ ] **Step 1:** For each inline block, determine the correct shared fixture:
  `async_client` for basic job API calls, `client_with_source` for
  source-path tests, `project_with_image` for seeded-project tests. For any
  test that monkeypatches module-level state before the app is instantiated
  and genuinely cannot use a shared fixture, add an inline comment
  `# legitimate: <reason>` instead of migrating.
- [ ] **Step 2:** Migrate inline clients to shared fixtures. Keep `monkeypatch`
  calls that precede client usage.
- [ ] **Step 3:** Run: `uv run pytest tests/test_routes_jobs.py -v`
  Expected: all tests PASS, same count.
- [ ] **Step 4:** Commit:
  `git add tests/test_routes_jobs.py && git commit -m "test: adopt shared fixtures in test_routes_jobs (M4 additions)"`

### Task 2.C — Migrate `test_routes_pages.py` and `test_suite.py` (3 + 1 inline clients)

**Files:** `tests/test_routes_pages.py`, `tests/test_suite.py`

- [ ] **Step 1:** Apply the same approach as 2.A/2.B to the 3 inline clients
  in `test_routes_pages.py` and 1 in `test_suite.py`.
- [ ] **Step 2:** Run:
  `uv run pytest tests/test_routes_pages.py tests/test_suite.py -v`
  Expected: all tests PASS.
- [ ] **Step 3:** Commit each file separately:
  `git commit -m "test: adopt shared fixtures in test_routes_pages (M4 additions)"`
  `git commit -m "test: adopt shared fixtures in test_suite (M4 additions)"`

### Task 2.D — Verification gate

- [ ] **Step 1:** Run:
  `grep -rn "async with AsyncClient" tests --include=*.py | grep -v conftest.py`
  Expected: no output (or only lines carrying an explicit `# legitimate: ...`
  comment).
- [ ] **Step 2:** Run: `make ci AI=1`
  Expected: green.
- [ ] **Step 3:** Commit any residual cleanup found.

---

## M3 — Frontend test-utils adoption (targeted)

**Goal:** Migrate `HomePage`, `PageViewPage`, `App`, and `AppSettingsSlot` to
use `renderWithProviders` or `makeTestQueryClient` from
`frontend/src/test/test-utils.tsx` instead of hand-rolled provider wrappers.
Explicitly accept `SourcePicker`, `OutputConfigPanel`, `ConfigContext`,
`useOcrJob`, and `AppPrefsError` as correct with bare `render()` — these are
isolated components or hooks that do not need router/query providers.

### Task 3.A — Migrate `HomePage.test.tsx`

**Files:** `frontend/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1:** Read the local `renderTree()` and `makeQueryClient()` helpers.
  Note that `renderWithProviders` wraps `QueryClientProvider` + `MemoryRouter`
  but not `ConfigProvider`. Since `HomePage` needs `ConfigProvider`, the
  correct migration is: import `makeTestQueryClient` from test-utils, delete
  the local `makeQueryClient()`, and keep a local `renderTree()` that wraps
  `<ConfigProvider>` around `<MemoryRouter>` using a test-utils QueryClient.
  Alternatively, if `renderWithProviders` can accept an optional wrapper, use
  that.
- [ ] **Step 2:** Apply the migration. Do not change any assertions.
- [ ] **Step 3:** Run:
  `cd frontend && pnpm vitest run src/pages/__tests__/HomePage.test.tsx`
  Expected: all cases PASS, same count.
- [ ] **Step 4:** Commit:
  `git add frontend/src/pages/__tests__/HomePage.test.tsx && git commit -m "test(frontend): adopt test-utils makeTestQueryClient in HomePage"`

### Task 3.B — Migrate `PageViewPage.test.tsx`

**Files:** `frontend/src/pages/__tests__/PageViewPage.test.tsx`

- [ ] **Step 1:** Read the local render helpers. They wrap
  `<MemoryRouter initialEntries={[...]}><Routes><Route .../></Routes></MemoryRouter>`.
  Check whether `PageViewPage` uses `useParams` (requires `Routes`+`Route`
  tree). If so, add a `renderPageView(jobId, pageIdx)` helper to
  `test-utils.tsx`; if not, use `renderWithProviders` with a `route` param.
- [ ] **Step 2:** Apply the migration. Keep assertions identical.
- [ ] **Step 3:** Run:
  `cd frontend && pnpm vitest run src/pages/__tests__/PageViewPage.test.tsx`
  Expected: PASS.
- [ ] **Step 4:** Commit per file.

### Task 3.C — Migrate `App.test.tsx` and `AppSettingsSlot.test.tsx`

**Files:** `frontend/src/__tests__/App.test.tsx`,
`frontend/src/__tests__/AppSettingsSlot.test.tsx`

- [ ] **Step 1:** Both already import `makeTestQueryClient` from test-utils.
  Check whether they still construct a local `QueryClientProvider` wrapper.
  Replace any local provider construction with `renderWithProviders` or
  consistent use of the imported `makeTestQueryClient`.
- [ ] **Step 2:** Apply migration. Keep assertions identical.
- [ ] **Step 3:** Run vitest on both files. Expected: PASS.
- [ ] **Step 4:** Commit per file.

### Task 3.D — Verification gate

- [ ] **Step 1:** Run:
  `grep -rn "new QueryClient\|makeQueryClient" frontend/src --include=*.test.tsx | grep -v test-utils`
  Expected: no local `new QueryClient` or `makeQueryClient` definitions
  outside `test-utils.tsx`.
- [ ] **Step 2:** Run:
  `grep -rn "MemoryRouter" frontend/src --include=*.test.tsx`
  Expected: hits only in `PageViewPage.test.tsx` (route-parameterized
  rendering — documented exception if `renderWithProviders` cannot cover it)
  and `test-utils.tsx` itself. All other files use `renderWithProviders`.
- [ ] **Step 3:** Run:
  `cd frontend && pnpm run test && pnpm exec tsc --noEmit`
  Expected: green.
- [ ] **Step 4:** Commit if any cleanup was needed.

---

## M6 — Definition-of-Done Gate

Run after M2 and M3 are both complete.

### Task 6.1 — Deferral artifact scan

- [ ] Run:
  `grep -rn "pytest.mark.skip\|pytest.mark.xfail\|@pytest.mark.todo\|\bpass\b *# *TODO\|raise NotImplementedError" tests --include=*.py | grep -v smoke/test_e2e`
  Expected: no hits.
- [ ] Run:
  `grep -rn "it\.skip\|it\.todo\|describe\.skip\|xit(\|xdescribe(\|test\.skip\|test\.todo" frontend/src --include=*.test.tsx`
  Expected: no hits.
- [ ] Run:
  `grep -rn "TODO\|FIXME\|add later" tests frontend/src --include=*.py --include=*.test.tsx | grep -v "\.pyc"`
  Expected: only hits in legitimate comments (none in test logic or assertion
  bodies).

### Task 6.2 — No inline AsyncClient outside conftest

- [ ] Run:
  `grep -rn "async with AsyncClient" tests --include=*.py | grep -v conftest.py`
  Expected: no output (or only lines with an explicit `# legitimate: ...`
  comment).

### Task 6.3 — No local provider boilerplate outside test-utils

- [ ] Run:
  `grep -rn "new QueryClient\|makeQueryClient" frontend/src --include=*.test.tsx | grep -v test-utils`
  Expected: no hits.
- [ ] Run:
  `grep -rn "MemoryRouter" frontend/src --include=*.test.tsx`
  Expected: hits only in `PageViewPage.test.tsx` and `test-utils.tsx`.

### Task 6.4 — Audit matrix complete

- [ ] Run:
  `grep -n "^- \[ \]" docs/research/2026-05-28-test-audit-matrix.md`
  Expected: no output (all boxes checked).
- [ ] Confirm all 35 click-path matrix rows show `full-e2e` by reading the
  matrix table.

### Task 6.5 — Full suite green

- [ ] Run: `make ci AI=1`
  Expected: green (backend unit/integration + lint + typecheck + frontend
  build + vitest + behavior-coverage + smoke + e2e-fast).
- [ ] Run: `make e2e-browser AI=1` or `make ci-full AI=1`
  Expected: full e2e tier (browser smoke + all 14 click-path tests) green.
- [ ] (Optional, GPU required) Run: `make e2e-real-ocr`
  Expected: Tier B real-OCR tests pass or xfail only for missing model
  weights.

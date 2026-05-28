# Test Suite Audit, Reorg & Full UI Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit every test in pdomain-ocr-simple-gui, consolidate duplicated setup into shared fixtures/utilities, strengthen weak tests to an explicit good/bad standard, and drive every UI click path end-to-end through a real browser against a stubbed OCR backend — with no half-work and no deferred stubs.

**Architecture:** Six sequential milestones. M1 produces a committed coverage & quality matrix (the source of truth). M2/M3 hoist shared backend fixtures and frontend test-utils. M4 strengthens every weak-tagged test (driven by the M1 matrix). M5 adds a fake-OCR dependency seam plus Playwright tests covering every interactive element. M6 enforces the Definition of Done.

**Tech Stack:** pytest + pytest-asyncio + httpx AsyncClient/ASGITransport (backend), vitest + @testing-library/react (frontend), pytest-playwright + Chromium (e2e), FastAPI dependency overrides (fake-OCR seam), uv, pnpm.

**Spec:** `docs/specs/2026-05-28-test-suite-audit-reorg-design.md`

**Repo rules (from CLAUDE.md):** always `make ci AI=1` before committing; never `python -m pytest` — use `uv run pytest` or `make test`; TDD-first; commit locally, do not push.

---

## File Structure

**M1 — audit artifact (new):**

- Create: `docs/research/2026-05-28-test-audit-matrix.md` — backend table, frontend table, click-path matrix, and a task appendix listing every weak-tagged test by `path::test_name` + reason code.

**M2 — backend shared setup (new + modify):**

- Create: `tests/conftest.py` — shared fixtures (`async_client`, `client_with_source`, `project_with_image`, `secured_client`, `projects_root`, `client_with_mock_prefs`, `client_no_prefs`).
- Create: `tests/factories.py` — `make_project_spec`, `make_page_result`, `write_seeded_project`.
- Modify: every backend test file that currently defines its own copy of those fixtures (per the audit; known candidates: `test_routes_jobs.py`, `test_routes_pages.py`, `test_routes_prefs.py`, `test_routes_root.py`, `test_security_project_id.py`, `test_storage.py`, `test_suite.py`).

**M3 — frontend shared setup (new + modify + delete):**

- Delete: `frontend/src/pages/PageViewPage.test.tsx` (duplicate of `pages/__tests__/PageViewPage.test.tsx`).
- Create: `frontend/src/test/test-utils.tsx` — `renderWithProviders`, api/fetch mock handlers, fixture builders.
- Move/normalize: any co-located `*.test.tsx` into the sibling `__tests__/` directory.
- Modify: every spec that hand-rolls config/prefs/api stubs to consume `test-utils`.

**M5 — fake-OCR seam + e2e (new + modify):**

- Create: `src/pdomain_ocr_simple_gui/testing/fake_dispatcher.py` — deterministic fake stage dispatcher.
- Modify: app wiring to allow a dependency override / env-selected dispatcher (exact seam located in M5 Task 1).
- Modify: React components to add `data-testid` attributes on every interactive element in the click-path matrix.
- Create: `tests/e2e/test_click_paths_*.py` — one file per click-path group.
- Modify: `tests/e2e/conftest.py` to start the server with the fake dispatcher; `Makefile` + `.github/workflows/ci.yml` for the fast browser tier.

---

## Cross-cutting guardrails (apply to every task in every milestone)

- One behavior per test; name `test_<behavior>_<condition>_<expected>` (backend) / `<element> <condition> <expected>` (frontend `it`).
- Arrange-Act-Assert; no branching/loops/computation in test bodies.
- Deterministic: no real `sleep`, wall-clock, or network. Fake time / poll on UI state.
- Good-state and bad-state pair for behavior tests.
- Markers honest: `slow`/`e2e` only where truly required (the one real-OCR smoke).
- No deferral artifacts (`skip`/`xfail`/`todo`/placeholder bodies/`TODO`-as-test). M6 greps for these.

---

## Milestone 1 — Audit pass & coverage/quality matrix

Produces the artifact that gates M4 and M6. No production or test-code changes here — only the committed matrix.

### Task 1.1: Classify backend tests

**Files:**

- Create: `docs/research/2026-05-28-test-audit-matrix.md`

- [ ] **Step 1: Enumerate every backend test**

Run: `uv run pytest tests --collect-only -q | sed -n '1,400p'`
Expected: a flat list of `tests/<file>.py::<test_name>` (≈168 items, excludes `slow`/`e2e` by config — add `-m "slow or e2e"` in a second pass to capture those too).

- [ ] **Step 2: Build the backend table**

For each collected test, add a row to a `## Backend` table with columns:

```markdown
| Test (path::name) | Module under test | Behavior asserted | Mock depth (none/shallow/deep) | Good state? | Bad state? | Reason code |
```

Reason code is one of: `ok`, `tautological`, `asserts-mock`, `no-bad-case`, `duplicate`, `over-coupled`. Use `ok` for tests that already meet the good/bad standard. Read each test body to fill the row — do not guess from the name.

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-05-28-test-audit-matrix.md
git commit -m "docs(research): backend test audit table"
```

### Task 1.2: Classify frontend tests

**Files:**

- Modify: `docs/research/2026-05-28-test-audit-matrix.md`

- [ ] **Step 1: Enumerate every frontend test**

Run: `cd frontend && pnpm vitest list` (or `pnpm vitest --run --reporter=verbose` and read the `it` titles)
Expected: ≈83 `it`/`test` titles across 11 files.

- [ ] **Step 2: Build the frontend table**

Add a `## Frontend` table with the same columns as Task 1.1 (Module under test = component/hook). Read each spec body to classify. Explicitly tag the `pages/PageViewPage.test.tsx` ⇄ `pages/__tests__/PageViewPage.test.tsx` overlap as `duplicate`.

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-05-28-test-audit-matrix.md
git commit -m "docs(research): frontend test audit table"
```

### Task 1.3: Build the click-path matrix + weak-test appendix

**Files:**

- Modify: `docs/research/2026-05-28-test-audit-matrix.md`

- [ ] **Step 1: Enumerate interactive elements**

From `frontend/src` components, list every interactive element. Seed list (verify against source, add any missing): drag-drop zone, file-picker upload, path input, engine select, language select, save_json toggle, combined_txt toggle, submit button, recent-projects row, status badge, download-zip button, download-txt button, retry button, page-row nav, zoom-in, zoom-out, pan, fit-to-screen, prev-page, next-page, settings/prefs form fields, shortcuts-help button.

- [ ] **Step 2: Build the click-path matrix**

```markdown
| Interactive element | Component | Current coverage (none/unit/hybrid-e2e/full-e2e) | Target |
```

Target is `full-e2e` for every row. Map each existing `tests/e2e/*` test to the path(s) it currently covers (mark `hybrid-e2e` where it's API-driven + render-assert).

- [ ] **Step 3: Build the weak-test appendix**

```markdown
## Appendix: weak-tagged tests (M4 worklist)
- [ ] tests/test_x.py::test_y — <reason code> — <one-line fix intent>
```

One checkbox row per test whose reason code is not `ok`. This list IS the M4 worklist; M6 verifies every box is checked.

- [ ] **Step 4: Commit**

```bash
git add docs/research/2026-05-28-test-audit-matrix.md
git commit -m "docs(research): click-path matrix + weak-test worklist"
```

---

## Milestone 2 — Backend fixture consolidation

Hoist duplicated setup into `tests/conftest.py` + `tests/factories.py`, then adopt them everywhere, deleting the per-file copies. TDD note: these are test-infrastructure changes — the "test" is that the existing suite still passes after each file is migrated (no behavior change, no coverage loss).

### Task 2.1: Create shared factories

**Files:**

- Create: `tests/factories.py`

- [ ] **Step 1: Write factories**

```python
"""Test object + on-disk fixture factories (no production imports beyond models)."""
from __future__ import annotations

from pathlib import Path

from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec
from pdomain_ocr_simple_gui import storage


def make_project_spec(project_id: str = "proj-1", **overrides) -> ProjectSpec:
    base = dict(project_id=project_id, engine="doctr", language="en")
    base.update(overrides)
    return ProjectSpec(**base)


def make_page_result(page: int = 1, text: str = "hello", **overrides) -> PageResult:
    base = dict(page=page, text=text, words=[])
    base.update(overrides)
    return PageResult(**base)


def write_seeded_project(projects_root: Path, spec: ProjectSpec | None = None) -> ProjectSpec:
    spec = spec or make_project_spec()
    storage.write_project(projects_root, spec)
    return spec
```

> NOTE: confirm exact `ProjectSpec` / `PageResult` field names and `storage` function signatures against `src/pdomain_ocr_simple_gui/models.py` and `storage.py` in M2 Task 1 Step 0 before writing — adjust kwargs to match. Do not invent fields.

- [ ] **Step 2: Smoke-import the module**

Run: `uv run python -c "import tests.factories"`
Expected: no error (run from repo root; if `tests` is not importable, call the functions from a throwaway test instead).

- [ ] **Step 3: Commit**

```bash
git add tests/factories.py
git commit -m "test: add shared test object/fixture factories"
```

### Task 2.2: Create shared conftest fixtures

**Files:**

- Create: `tests/conftest.py`

- [ ] **Step 1: Read the current per-file fixtures**

Read the fixture definitions flagged in M1 (in `test_routes_jobs.py`, `test_routes_pages.py`, `test_routes_prefs.py`, `test_routes_root.py`, `test_security_project_id.py`, `test_storage.py`, `test_suite.py`). Capture their exact construction (env vars set, app import path, mock targets) so the shared versions are behavior-identical.

- [ ] **Step 2: Write `tests/conftest.py`**

```python
"""Shared backend test fixtures. Mirrors the per-file fixtures they replace."""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Import path + env var names confirmed against the app in Step 1.
from pdomain_ocr_simple_gui.app import app  # adjust if app is a factory


@pytest.fixture
def projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PDOMAIN_OCR_PROJECTS_ROOT", str(root))  # confirm exact env var in Step 1
    return root


@pytest.fixture
async def async_client(projects_root: Path) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

Add the remaining shared fixtures (`client_with_source`, `project_with_image`, `secured_client`, `client_with_mock_prefs`, `client_no_prefs`) using the exact bodies captured in Step 1. Where a fixture builds on-disk state, use `tests/factories.py`.

- [ ] **Step 3: Run the full suite (must still pass — name collision proves fixtures resolve)**

Run: `make test AI=1`
Expected: PASS, same test count as before (shared + per-file fixtures coexist for now; pytest prefers the closest scope).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared backend conftest fixtures"
```

### Task 2.3: Migrate each file to shared fixtures (one commit per file)

**Files:**

- Modify: each backend test file with a now-duplicated local fixture.

Repeat the following loop for each file in the M1 list:

- [ ] **Step 1: Delete the file's local fixture definition(s)** that are now provided by `conftest.py`, and update any references (e.g. rename `client` → `async_client` if the shared name differs).

- [ ] **Step 2: Run that file's tests**

Run: `uv run pytest tests/<file>.py -v`
Expected: PASS, same count as before the edit.

- [ ] **Step 3: Commit**

```bash
git add tests/<file>.py
git commit -m "test: adopt shared fixtures in <file>"
```

### Task 2.4: Verify no duplication remains

- [ ] **Step 1: Grep for leftover local definitions**

Run: `grep -rn "def client\|ASGITransport\|setenv.*PROJECTS_ROOT" tests --include=*.py | grep -v conftest.py`
Expected: no fixture-definition hits outside `conftest.py` (call sites are fine; a hit that is a fixture `def` is a miss to fix).

- [ ] **Step 2: Full gate**

Run: `make ci AI=1`
Expected: green.

- [ ] **Step 3: Commit (if grep prompted any cleanup)**

```bash
git add -A tests
git commit -m "test: remove residual duplicated backend setup"
```

---

## Milestone 3 — Frontend consolidation & restructure

### Task 3.1: Remove the duplicate PageViewPage spec

**Files:**

- Delete: `frontend/src/pages/PageViewPage.test.tsx`
- Modify: `frontend/src/pages/__tests__/PageViewPage.test.tsx` (absorb any unique cases first)

- [ ] **Step 1: Diff the two files** and copy any test case present only in `pages/PageViewPage.test.tsx` into `pages/__tests__/PageViewPage.test.tsx`. (The co-located file has 13 cases vs 5 — most coverage may live in the file being deleted, so migrate carefully, not blindly.)

- [ ] **Step 2: Delete the co-located duplicate**

```bash
git rm frontend/src/pages/PageViewPage.test.tsx
```

- [ ] **Step 3: Run the merged spec**

Run: `cd frontend && pnpm vitest run src/pages/__tests__/PageViewPage.test.tsx`
Expected: PASS, case count = union of the two originals.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/pages
git commit -m "test(frontend): merge duplicate PageViewPage specs"
```

### Task 3.2: Add shared frontend test-utils

**Files:**

- Create: `frontend/src/test/test-utils.tsx`

- [ ] **Step 1: Read `frontend/src/test/setup.ts`** and a couple of existing specs to capture how providers (ConfigContext, router, pdomain-ui) and api/fetch mocks are currently stubbed.

- [ ] **Step 2: Write `test-utils.tsx`**

```tsx
import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement, ReactNode } from "react";
// import the real providers used by the app (ConfigProvider etc.) — confirm names in Step 1

export function renderWithProviders(
  ui: ReactElement,
  { route = "/", ...options }: { route?: string } & RenderOptions = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>;
  }
  return render(ui, { wrapper: Wrapper, ...options });
}

export const fixtures = {
  config: () => ({ mode: "local", is_containerized: false }),
  projectStatus: () => ({ project_id: "proj-1", state: "succeeded", pages: [] }),
};
```

Add fetch/api mock helpers matching the existing stubbing approach (e.g. a `mockFetchJson(url, body)` helper) so specs stop re-implementing them.

- [ ] **Step 3: Type-check the util**

Run: `cd frontend && pnpm exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/test/test-utils.tsx
git commit -m "test(frontend): add shared render + fixtures test-utils"
```

### Task 3.3: Migrate specs to test-utils + normalize layout (one commit per spec)

**Files:**

- Modify/move: each frontend spec.

Loop per spec:

- [ ] **Step 1:** Replace hand-rolled `render(...)` + provider wrapping with `renderWithProviders`, and local stubs with the `test-utils` fixtures/mock helpers.
- [ ] **Step 2:** If the spec is co-located, move it into the sibling `__tests__/` directory (`git mv`).
- [ ] **Step 3: Run it**

Run: `cd frontend && pnpm vitest run <spec path>`
Expected: PASS, same case count.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src && git commit -m "test(frontend): adopt test-utils in <spec>"
```

### Task 3.4: Verify

- [ ] **Step 1: Grep for residual local provider wrappers**

Run: `grep -rn "MemoryRouter\|render(" frontend/src --include=*.test.tsx | grep -v test-utils`
Expected: only `renderWithProviders` call sites, no raw `render(<...>)` with manual providers.

- [ ] **Step 2: Full frontend gate**

Run: `cd frontend && pnpm run test && pnpm exec tsc --noEmit`
Expected: green, no co-located `*.test.tsx` remaining outside `__tests__/`.

- [ ] **Step 3: Commit (if cleanup needed)**

```bash
git add -A frontend/src && git commit -m "test(frontend): finish layout normalization"
```

---

## Milestone 4 — Strengthen every weak-tagged test

Driven entirely by the M1 weak-test appendix. **Every** unchecked box must be resolved here; M6 verifies none remain. Work file-by-file. For each weak test, apply the matching pattern below, then run and commit.

### Reason-code patterns (apply per test)

**`tautological` / `asserts-mock`** — the test asserts the mock or a constant, not behavior. Replace the mock with a real collaborator where it needs no new product code (e.g. real `storage` round-trip on a tmp dir), then assert the observable result.

```python
# BEFORE (asserts-mock): patches storage.read_project to return X, asserts X back.
# AFTER (real round-trip):
async def test_get_pages_returns_persisted_page(async_client, projects_root):
    spec = write_seeded_project(projects_root, make_project_spec(project_id="p1"))
    storage.write_page_sidecar(projects_root, "p1", make_page_result(page=1, text="alpha"))

    resp = await async_client.get("/api/pages/p1")

    assert resp.status_code == 200
    assert resp.json()["pages"][0]["text"] == "alpha"  # good state: real persisted value
```

**`no-bad-case`** — add the paired failure assertion validated against the good state.

```python
async def test_get_pages_unknown_project_returns_404(async_client, projects_root):
    resp = await async_client.get("/api/pages/does-not-exist")
    assert resp.status_code == 404                      # bad state
    assert "not found" in resp.json()["detail"].lower()  # specific error, not just non-200
```

**`over-coupled`** — the test asserts internal call counts / private structure. Re-target to the public observable (response body, persisted file, rendered DOM).

**`duplicate`** — delete; ensure the surviving test covers the behavior (note the survivor's `path::name` in the commit message).

### Task 4.N: Strengthen weak tests in `tests/<file>.py` (one task per file with weak rows)

**Files:**

- Modify: `tests/<file>.py`

- [ ] **Step 1:** For each weak row in this file (from the appendix), rewrite per the matching pattern. Add the missing good/bad half; reduce mocks to real collaborators where no new product code is required.
- [ ] **Step 2: Run the file**

Run: `uv run pytest tests/<file>.py -v`
Expected: PASS; each formerly-weak test now has explicit good + bad assertions.

- [ ] **Step 3:** Check off the corresponding appendix boxes in `docs/research/2026-05-28-test-audit-matrix.md`.
- [ ] **Step 4: Commit**

```bash
git add tests/<file>.py docs/research/2026-05-28-test-audit-matrix.md
git commit -m "test: strengthen <file> to good/bad standard"
```

### Task 4.F: Strengthen weak frontend specs (one task per spec with weak rows)

**Files:**

- Modify: `frontend/src/**/__tests__/<spec>.test.tsx`

- [ ] **Step 1:** Rewrite each weak `it` to assert rendered/behavioral outcome (not that a mock was called). Add the bad-state case (e.g. error boundary shows message on failed fetch) validated against the good render.

```tsx
it("shows error message when job fetch fails", async () => {
  mockFetchJson("/api/jobs/p1", { ok: false, status: 500 });
  renderWithProviders(<ResultsPage />, { route: "/jobs/p1" });
  expect(await screen.findByTestId("results-error")).toHaveTextContent(/failed/i);
});
```

- [ ] **Step 2: Run**

Run: `cd frontend && pnpm vitest run <spec>`
Expected: PASS.

- [ ] **Step 3:** Check off appendix boxes.
- [ ] **Step 4: Commit**

```bash
git add -A frontend/src docs/research/2026-05-28-test-audit-matrix.md
git commit -m "test(frontend): strengthen <spec> to good/bad standard"
```

### Task 4.Z: Verify no weak tags remain

- [ ] **Step 1: Grep the appendix for unchecked boxes**

Run: `grep -n "^- \[ \]" docs/research/2026-05-28-test-audit-matrix.md`
Expected: no output (every weak test resolved).

- [ ] **Step 2: Full gate**

Run: `make ci AI=1`
Expected: green.

---

## Milestone 5 — Full UI click-path e2e (stubbed OCR, real browser)

This is the mandatory FastAPI+SPA browser-verification milestone. It replaces the hybrid API-driven shortcuts with real browser interaction, backed by a deterministic fake dispatcher.

### Task 5.1: Locate the dispatcher seam

**Files:**

- Read: `src/pdomain_ocr_simple_gui/pipeline.py`, `app.py`, route modules that construct/inject the `LocalStageDispatcher`.

- [ ] **Step 1:** Identify exactly where the OCR dispatcher is constructed and how a request reaches it (FastAPI dependency, module global, or pipeline arg). Record the precise injection point — this determines the override mechanism. Do not write code yet.

### Task 5.2: Build the fake dispatcher

**Files:**

- Create: `src/pdomain_ocr_simple_gui/testing/fake_dispatcher.py`
- Test: `tests/test_fake_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher


def test_fake_dispatcher_returns_deterministic_page_text():
    disp = FakeStageDispatcher(text="lorem")
    result = disp.run_page(image_path="anything.png")  # match real dispatcher signature from 5.1
    assert result.text == "lorem"
    assert result.words  # non-empty deterministic words for overlay rendering
```

- [ ] **Step 2: Run it (fails — module missing)**

Run: `uv run pytest tests/test_fake_dispatcher.py -v`
Expected: FAIL, ImportError.

- [ ] **Step 3: Implement the fake** to satisfy the real dispatcher's protocol (signatures confirmed in 5.1), returning fixed text + word boxes with no model load.

- [ ] **Step 4: Run it (passes)**

Run: `uv run pytest tests/test_fake_dispatcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pdomain_ocr_simple_gui/testing/fake_dispatcher.py tests/test_fake_dispatcher.py
git commit -m "test: add deterministic fake OCR dispatcher"
```

### Task 5.3: Wire the override seam

**Files:**

- Modify: the injection point from 5.1 (dependency override or env-selected factory).

- [ ] **Step 1: Write the failing test** — an API test proving the override produces fake output end-to-end through a real job run:

```python
async def test_job_runs_with_fake_dispatcher(async_client, projects_root, use_fake_dispatcher):
    # use_fake_dispatcher: fixture that applies app.dependency_overrides (added this task)
    create = await async_client.post("/api/jobs", json={"engine": "doctr", "language": "en", "source": {...}})
    pid = create.json()["project_id"]
    # poll job state to succeeded (deterministic + fast under fake)
    status = await async_client.get(f"/api/jobs/{pid}")
    assert status.json()["state"] == "succeeded"
    pages = await async_client.get(f"/api/pages/{pid}")
    assert pages.json()["pages"][0]["text"] == "lorem"
```

- [ ] **Step 2: Run (fails)** — Run: `uv run pytest tests/test_routes_jobs.py -k fake_dispatcher -v` → FAIL.
- [ ] **Step 3: Implement the seam** + the `use_fake_dispatcher` fixture in `conftest.py` (`app.dependency_overrides[...] = lambda: FakeStageDispatcher(...)`).
- [ ] **Step 4: Run (passes).**
- [ ] **Step 5: Commit**

```bash
git add src tests/conftest.py tests/test_routes_jobs.py
git commit -m "feat(testing): dependency-override seam for fake OCR dispatcher"
```

### Task 5.4: Add data-testid attributes to every interactive element

**Files:**

- Modify: React components per the M1 click-path matrix.

- [ ] **Step 1:** For each element in the matrix, add a stable `data-testid` (e.g. `drop-zone`, `file-input`, `path-input`, `engine-select`, `language-select`, `toggle-save-json`, `toggle-combined-txt`, `submit-job`, `recent-project-row`, `status-badge`, `download-zip`, `download-txt`, `retry-job`, `page-row`, `zoom-in`, `zoom-out`, `fit-screen`, `prev-page`, `next-page`, `results-page`, `home-page`, `page-view`). Also add `results-error` etc. used by M4 frontend tests.
- [ ] **Step 2: Type-check + frontend tests**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm run test`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add -A frontend/src
git commit -m "feat(frontend): data-testid contract for e2e click paths"
```

### Task 5.5: Update e2e conftest to launch with the fake dispatcher

**Files:**

- Modify: `tests/e2e/conftest.py`

- [ ] **Step 1:** Change `live_server_url` to start uvicorn with the fake dispatcher selected (env var the seam reads, e.g. `PDOMAIN_OCR_FAKE_DISPATCHER=1`), so browser tests need no model weights and run fast.
- [ ] **Step 2: Sanity-run an existing e2e test**

Run: `make e2e-browser AI=1` (after `playwright install chromium`)
Expected: existing e2e tests still pass against the fake-backed server.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/conftest.py
git commit -m "test(e2e): launch server with fake dispatcher for fast browser tests"
```

### Task 5.6+: One e2e test per click-path group (TDD, one commit each)

Create `tests/e2e/test_click_paths_<group>.py` for each group below. Each test drives the **real browser** (Playwright `page`), uses `data-testid` selectors, and asserts observable UI state.

Groups (each its own task, written test-first against the running fake-backed server):

- [ ] **5.6 Upload via drag-drop** → home → `drop-zone` receives files → `submit-job` → redirect to results → `status-badge` reaches "succeeded" → a `page-row` is visible.
- [ ] **5.7 Upload via file-picker** → `file-input` set_input_files → submit → results populated.
- [ ] **5.8 Local path input** (local mode) → `path-input` filled → submit → results populated.
- [ ] **5.9 Config form** → toggle `toggle-save-json` / `toggle-combined-txt`, choose `engine-select` / `language-select` → submit → assert config reflected in results/download options.
- [ ] **5.10 Downloads** → from results, click `download-zip` and `download-txt` → assert Playwright download events fire with non-empty files.
- [ ] **5.11 Recent projects** → `recent-project-row` click → navigates to that job's results.
- [ ] **5.12 Page viewer** → click `page-row` → `page-view` visible → `zoom-in`/`zoom-out`/`fit-screen`/`prev-page`/`next-page` change state → word overlays rendered.
- [ ] **5.13 Settings/prefs** → open prefs form → change a field → assert persisted (reload, value retained).

Per-task loop:

- [ ] **Step 1: Write the failing browser test** (Playwright, `data-testid` selectors, AAA).
- [ ] **Step 2: Run (fails if a testid/route is missing)** — Run: `make e2e-browser AI=1` (or `uv run pytest tests/e2e/test_click_paths_<group>.py -m e2e --no-cov -v`). Fix any missing testid in the component (commit separately).
- [ ] **Step 3: Run (passes).**
- [ ] **Step 4: Commit** — `git commit -m "test(e2e): full click-path coverage for <group>"`.

### Task 5.14: Remove hybrid API-driven shortcuts

**Files:**

- Modify/Delete: the original `tests/e2e/test_*.py` hybrid tests now superseded by 5.6–5.13.

- [ ] **Step 1:** For each original hybrid test, confirm its click path is now covered full-e2e (check the matrix), then delete it. Keep exactly one real-OCR smoke test (the existing `tests/smoke/test_e2e.py` or equivalent), marked `slow`/`e2e`.
- [ ] **Step 2:** Update the click-path matrix: every row now `full-e2e`.
- [ ] **Step 3: Run the full e2e tier**

Run: `make e2e-browser AI=1`
Expected: green; no hybrid tests remain.

- [ ] **Step 4: Commit**

```bash
git add -A tests/e2e docs/research/2026-05-28-test-audit-matrix.md
git commit -m "test(e2e): remove hybrid shortcuts; click paths now full-e2e"
```

### Task 5.15: Wire the fast browser tier into CI

**Files:**

- Modify: `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml` (`[dependency-groups] e2e` with `pytest-playwright>=0.5` if not present).

- [ ] **Step 1:** Ensure `pytest-playwright>=0.5` is in the `e2e` dependency group; add `playwright install chromium` to `make setup`. Add a `make e2e-browser` target if missing (it exists per CLAUDE.md — confirm it runs the fake-backed click-path suite without `--no-cov` excluding them from the gate intent).
- [ ] **Step 2:** Make the fake-backed click-path suite part of `make ci` (fast tier — no model weights). The single real-OCR smoke stays opt-in under `make ci-full` / `make e2e-browser` with the real backend.
- [ ] **Step 3:** Add a CI job step running the fast browser tier (Chromium installed) on every push.
- [ ] **Step 4: Run the full gate locally**

Run: `make ci AI=1`
Expected: green, including the fast browser tier.

- [ ] **Step 5: Commit**

```bash
git add Makefile .github/workflows/ci.yml pyproject.toml uv.lock
git commit -m "ci: run fast browser click-path tier on every push"
```

---

## Milestone 6 — Definition-of-Done enforcement

Mechanical verification that no in-scope work was deferred. Any failure here means an earlier milestone is incomplete — go fix it, do not file a follow-up.

### Task 6.1: No deferral artifacts

- [ ] **Step 1: Grep backend**

Run: `grep -rn "pytest.mark.skip\|pytest.mark.xfail\|@pytest.mark.todo\|\bpass\b *# *TODO\|raise NotImplementedError" tests --include=*.py | grep -v "smoke/test_e2e\|tests/smoke"`
Expected: no hits (the one allowed real-OCR smoke may carry `slow`/`e2e`, never `skip`/`xfail`).

- [ ] **Step 2: Grep frontend**

Run: `grep -rn "it.skip\|it.todo\|describe.skip\|xit(\|xdescribe(\|test.skip\|test.todo" frontend/src --include=*.test.tsx`
Expected: no hits.

- [ ] **Step 3: Grep for placeholder bodies / TODO-as-test**

Run: `grep -rn "TODO\|FIXME\|add later\|placeholder" tests frontend/src --include=*.py --include=*.test.tsx`
Expected: no hits in test files.

### Task 6.2: Matrix fully resolved

- [ ] **Step 1: No unchecked weak-test boxes**

Run: `grep -n "^- \[ \]" docs/research/2026-05-28-test-audit-matrix.md`
Expected: no output.

- [ ] **Step 2: Every click path full-e2e**

Read the click-path matrix; confirm no row's "Current coverage" is `none` or `hybrid-e2e`. Confirm no `unknown` rows remain in the backend/frontend tables.

### Task 6.3: No residual duplicated setup

- [ ] **Step 1:** Re-run the M2.4 and M3.4 greps — expect no fixture/provider duplication outside `conftest.py` / `test-utils.tsx`.

### Task 6.4: Full suite green with everything enabled

- [ ] **Step 1: Backend + frontend + fast browser tier**

Run: `make ci AI=1`
Expected: green.

- [ ] **Step 2: Real-OCR smoke (opt-in) still runs**

Run: `make ci-full AI=1` (or `make e2e-browser AI=1` with real backend)
Expected: the retained real-OCR smoke passes (or xfails only where weights are genuinely absent, per existing `make smoke` behavior — not a new skip).

- [ ] **Step 2 note:** A green `make ci` that is green because work was skipped is a failure of this milestone. Cross-check counts against the M1 matrix totals.

---

## Self-Review (completed by plan author)

- **Spec coverage:** Section 1 → M1; Section 2 → M2; Section 3 → M3; Section 4 → M4; Section 5 → M5; Section 6 (guardrails) → cross-cutting block + enforced in M6; Definition of Done → M6. All covered.
- **FastAPI+SPA browser milestone:** present (M5), wired into CI (5.15), with data-testid contract (5.4), app-loads + happy-path + route coverage (5.6–5.13).
- **Placeholder honesty:** M2.1/M2.2/M3.2/M5.2 carry explicit "confirm exact signatures/env-var/import in Step 0/1" notes because real field names and the dispatcher seam must be read from source — these are verification steps, not deferred work. M4 task bodies are intentionally generated from the M1 matrix (the only honest way to enumerate 168 diagnoses); the per-tag patterns and the M6 gate make completeness checkable.
- **Naming consistency:** `async_client`, `projects_root`, `FakeStageDispatcher`, `renderWithProviders`, `use_fake_dispatcher`, and the `data-testid` set are used consistently across tasks.

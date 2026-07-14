---
Status: draft
Owner: CT
Created: 2026-07-14
Last verified: 2026-07-14
Kind: plan
---

# Review-Fixes Implementation Plan (2026-07-14, rev 2 — post red team)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Agent Index

- **Kind:** plan
- **Status:** draft
- **Read when:** executing or reviewing the 2026-07-14 multi-lens review
  fixes (security, correctness, UI wiring, device vocabulary, docs).
- **Search terms:** review fixes, uploads auth, rerun semaphore, device
  vocabulary, cuda local sentinel, update policy, drop-zone copy, release gate,
  apiFetch token wrapper, zip bomb, suite protected paths.

## Goal

Fix every confirmed finding from the 2026-07-14 multi-lens review — auth gaps (including two the red team added: unauthenticated suite mutations and a frontend that never sends tokens), rerun semaphore bypass, dispatcher timeout, zip-extraction hardening, device-vocabulary corruption in pdomain-ops, suite mount misconfiguration (`app_id="unknown"`), unwired UI, stale docs — filing cross-repo issues and gating on a pdomain-ops release where required.

This plan was red-teamed by three adversarial reviewers (technical, process, security) on 2026-07-14; rev 2 incorporates all confirmed findings.

## Architecture

Three work streams. Phase A fixes everything self-contained in this repo, executed **strictly one task at a time** (multiple tasks share `routes/jobs.py`, `routes/uploads.py`, `App.tsx`, and `jobCreationMachine.ts` — parallel dispatch would collide). Phase B fixes the device vocabulary at its source in `pdomain-ops` (worktree cut **from `origin/master`**, not the current checkout), followed by a human-approved release gate (Phase C) and the dependent wiring here (Phase D). Phase E files deferred-work issues; Phase F updates stale docs and runs the docgraph postflight.

## Tech Stack

FastAPI + Pydantic + pytest (backend), React + Vite + TS + vitest (frontend), uv, docgraph, gh CLI.

## Global Constraints

- Run `make ci AI=1` in the touched repo before every commit batch; never `python -m pytest` — always `uv run pytest` or `make test AI=1`.
- TDD: failing test first for every behavior change (copy-only and comment-only changes exempt).
- Phase A dispatches **sequentially** — one implementation subagent at a time, merged before the next starts. Phase B may run concurrently with Phase A (separate repos).
- Work in isolated worktrees (`superpowers:using-git-worktrees`); pass `isolation: "worktree"` to implementation subagents. Exceptions: Phase C's dep bump and Phase D run in the interactive checkout (see those phases for why — ocr-container-meta issue #386).
- Commit locally; **never push** and **never release** without explicit human approval. Phase C is a HUMAN GATE.
- Cross-repo issues go to `ConcaveTrillion/ocr-container-meta`.
- After editing any doc under `docs/`, reindex docgraph same-turn; final gate is `docgraph check --strict` with **no blocking issues** (advisories on untouched legacy files don't block; advisories on files this plan touches must be resolved).
- Sibling checkout state at plan time: `/workspaces/pdomain/pdomain-ops` is checked out on branch `plan/issues-to-docs-roadmap-migration` (4 commits unmerged to master); `master` is **12 commits** past tag `v0.11.0`. `/workspaces/pdomain/pdomain-ui` needs **no changes and no release** (verified: no ComputeTargetPanel changes since v0.11.0; update-policy persistence already exists in pdomain-ops suite prefs).
- This repo pins `pdomain-ops>=0.10.0` (pip, registry `pdomain-index-pip`) and `@pdomain/pdomain-ui ^0.11.0` (npm). Phase C/D bump the pip floor to `>=0.11.1`.
- Default binding is `127.0.0.1` (`__main__.py:48`), so Phase A's auth fixes are defense-in-depth; they become the actual boundary only under `--host 0.0.0.0`. That scenario is exactly where Task 5 (suite mutations) matters most.
- Backend test-file names in this repo do NOT follow `test_routes_*`: the real files are `tests/test_uploads.py`, `tests/test_words_route.py`, `tests/test_config_route.py`, `tests/test_security_auth_token.py` (async, `secured_app_client`/`open_app_client` httpx fixtures, all asserting 401), `tests/conftest.py` fixtures: `async_client`, `client_with_source`, `secured_client`, `client_with_mock_prefs`, `client_no_prefs`. There is no repo-wide `client` or `client_with_token` fixture; several test files build `TestClient(create_app())` inline. Every task below names the real file and fixture to use.

---

## Phase A — pdomain-ocr-simple-gui (sequential)

### Task 1: Shared authenticated fetch wrapper (prerequisite for Tasks 2, 4, 13)

**Why first:** no fetch call in `frontend/src` sends `Authorization`/`X-API-Token` (verified: zero grep hits). Every already-protected mutation (`POST /api/jobs`, `DELETE /api/jobs/{id}`, `PUT /api/pages/.../text`, `POST .../rerun`) is **broken today** whenever `PDOMAIN_API_TOKEN` is set. Tasks 2/4 extend token coverage, so the wrapper must land first or the app becomes fully non-functional under a token.

**Files:**

- Create: `frontend/src/api/apiFetch.ts`
- Modify: every hand-rolled `fetch(` under `frontend/src` (enumerate with `rg -n "fetch\(" frontend/src` — includes `jobCreationMachine.ts:50-82` `defaultLoadConfig`/`defaultUploadFiles`/`defaultCreateJob`, `App.tsx:563`, `HomePage.tsx:56,70`, `useOcrJob.ts:151`, `PageViewPage.tsx`, `ResultsPage.tsx:47`, `ModelCacheSettings.tsx`, `JobsLocationSettings.tsx`, `RecentProjectsList.tsx`, `JobConfigInline.tsx`, `ConfigContext.tsx`)
- Test: `frontend/src/api/__tests__/apiFetch.test.ts`
- Modify: `docs/runbooks/install.md` (document the token knob)

**Interfaces:**

- Produces: `apiFetch(input: RequestInfo, init?: RequestInit): Promise<Response>` — reads `localStorage.getItem("pdomain.apiToken")` once per call; when non-empty, merges `Authorization: Bearer <token>` into headers; otherwise behaves exactly like `fetch`. All API calls go through it.
- Token source is deliberately minimal (localStorage, documented in the install runbook: `localStorage.setItem('pdomain.apiToken', '<token>')` in the browser console). A proper Settings field is Phase E issue 5 — do not build UI here.

- [ ] **Step 1: Failing test:**

```tsx
it("attaches bearer token from localStorage when present", async () => {
  localStorage.setItem("pdomain.apiToken", "sekrit");
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
  await apiFetch("/api/jobs", { method: "POST" });
  expect(new Headers(spy.mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer sekrit");
});

it("adds no header when token is unset", async () => {
  localStorage.removeItem("pdomain.apiToken");
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
  await apiFetch("/api/jobs");
  expect(new Headers(spy.mock.calls[0][1]?.headers).get("Authorization")).toBeNull();
});
```

- [ ] **Step 2:** `make frontend-test AI=1` → FAIL (module missing). Implement `apiFetch` (~15 lines). PASS.
- [ ] **Step 3:** Mechanically replace every direct `fetch(` API call with `apiFetch(` (import per file). `rg -n "fetch\(" frontend/src` afterward must show only `apiFetch.ts` itself and non-API uses (none expected).
- [ ] **Step 4:** `make frontend-test AI=1` + `make frontend-build AI=1` → PASS. Commit — `feat(frontend): shared apiFetch with optional bearer token`.

### Task 2: Require token on upload mutations

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/uploads.py:56,101`
- Test: `tests/test_security_auth_token.py` (async convention; `secured_app_client` fixture)

- [ ] **Step 1: Failing tests** (match the file's existing async style):

```python
async def test_post_uploads_requires_token(secured_app_client: AsyncClient) -> None:
    resp = await secured_app_client.post(
        "/api/uploads",
        files={"files": ("a.png", b"fake-bytes", "image/png")},
    )
    assert resp.status_code == 401


async def test_delete_uploads_requires_token(secured_app_client: AsyncClient) -> None:
    resp = await secured_app_client.delete("/api/uploads/deadbeef")
    assert resp.status_code == 401
```

- [ ] **Step 2:** `uv run pytest tests/test_security_auth_token.py -k uploads -v` → FAIL (non-401).
- [ ] **Step 3: Implement** — add `dependencies=[Depends(require_token)]` to both route decorators (`from pdomain_ocr_simple_gui.auth import require_token`).
- [ ] **Step 4:** `uv run pytest tests/test_security_auth_token.py tests/test_uploads.py -v` → PASS (Task 1 already made the frontend token-capable).
- [ ] **Step 5: Commit** — `fix(auth): require token on upload mutations`.

### Task 3: Close the path-traversal read in the words route

**This is a security fix, not a consistency nit:** `words.py:197-198` suppresses the `ValueError` from `validate_project_id` and **continues** into `read_project(job_id)` with the unsanitized id — an off-root file-read primitive (schema-constrained to `project.json` shape). Every other route fails closed (`downloads.py:73-76`).

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/words.py:197-198,217-221`
- Test: `tests/test_words_route.py` (builds `TestClient(create_app())` inline — follow that pattern)

- [ ] **Step 1: Failing tests** — status code AND a proof the off-root read is gone:

```python
def test_words_rejects_traversal_id(tmp_path, monkeypatch) -> None:
    # Plant a valid project.json OUTSIDE the projects root, reachable via "..".
    outside = tmp_path / "outside-root" / "project.json"
    ...  # write a schema-valid project.json at `outside`
    monkeypatch.setenv("PDOMAIN_OCR_PROJECTS_ROOT", str(tmp_path / "projects"))
    client = TestClient(create_app())
    resp = client.get("/api/pages/..%2Foutside-root/0/words")
    assert resp.status_code == 400  # rejected BEFORE any filesystem read
```

(Use the projects-root env/monkeypatch mechanism the existing tests in this file already use; the essential assertion is 400, proving validation halts the request.)

- [ ] **Step 2:** run → FAIL (today: 404/500 after attempting the read).
- [ ] **Step 3: Implement** — in the `get_words` route (`words.py:217-221`), validate before calling the helper, mirroring `get_job`:

```python
    try:
        validate_project_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

In `load_page_words`, delete the `with contextlib.suppress(ValueError):` wrapper (let it raise if ever called unvalidated); drop the `contextlib` import if now unused.

- [ ] **Step 4:** `uv run pytest tests/test_words_route.py -v` → PASS.
- [ ] **Step 5: Commit** — `fix(security): block path traversal in words route`.

### Task 4: Require token on GET /api/jobs/{project_id}

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/jobs.py:366`
- Test: `tests/test_security_auth_token.py`

- [ ] **Step 1: Failing test:**

```python
async def test_get_job_by_id_requires_token(secured_app_client: AsyncClient) -> None:
    resp = await secured_app_client.get("/api/jobs/0123456789abcdef")
    assert resp.status_code == 401
```

- [ ] **Step 2:** run → FAIL. Implement: `@router.get("/{project_id}", response_model=ProjectStatus, dependencies=[Depends(require_token)])`.
- [ ] **Step 3:** The app's own pollers (`useOcrJob.ts:151`, `PageViewPage.tsx:130`, `ResultsPage.tsx:47`) now send the token via Task 1's wrapper — verify with `make frontend-test AI=1`. `make test AI=1` → PASS.
- [ ] **Step 4: Commit** — `fix(auth): protect per-id job status GET`.

### Task 5: Protect all mutating /api/suite/* routes (red-team finding, critical)

`auth.py:32-37` hardcodes `SUITE_PROTECTED_PATHS = {"/api/suite/launch", "/api/suite/stop"}`. `/api/suite/stop` does not exist anywhere in pdomain-ops (phantom entry), while the four suite routes that actually mutate state are unprotected even with a token set: `PUT /api/suite/device` (`pdomain_ops/suite/device_routes.py:70`), `PUT /api/suite/prefs/common` (`suite/routes.py:64`), `PUT /api/suite/prefs/apps/{app_id}` (`suite/routes.py:69`), `POST /api/suite/update` (`suite/update_routes.py:67`). Anyone who can reach the server can rewrite prefs, force the compute device, or trigger the update flow.

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/auth.py:32-37,84-92`
- Test: `tests/test_security_auth_token.py` (extend the existing `TestSuiteAuth` pattern)

- [ ] **Step 1: Failing tests** — one per mutating route:

```python
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PUT", "/api/suite/device"),
        ("PUT", "/api/suite/prefs/common"),
        ("PUT", "/api/suite/prefs/apps/some-app"),
        ("POST", "/api/suite/update"),
        ("POST", "/api/suite/launch"),  # already protected — regression guard
    ],
)
async def test_mutating_suite_routes_require_token(
    secured_app_client: AsyncClient, method: str, path: str
) -> None:
    resp = await secured_app_client.request(method, path, json={})
    assert resp.status_code == 401
```

- [ ] **Step 2:** run → FAIL for the four new paths. Implement: replace the exact-match set with a method+prefix rule in `suite_token_middleware` — any request with method in `{POST, PUT, DELETE, PATCH}` whose path starts with `/api/suite/` requires the token (this future-proofs against new suite mounts instead of hand-maintaining a list); delete the phantom `/api/suite/stop` entry and the now-dead `SUITE_PROTECTED_PATHS` constant (or repoint it to the prefix rule with a comment). GETs stay open.
- [ ] **Step 3:** `uv run pytest tests/test_security_auth_token.py -v` → PASS (including existing launch tests).
- [ ] **Step 4: Commit** — `fix(auth): all mutating suite routes require the API token`.

### Task 6: Route rerun through the job semaphore

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/jobs.py:458-499`
- Test: `tests/test_security_auth_token.py` (`TestMaxConcurrentJobs` class)

There is no reusable exhaust helper or `succeeded_project` fixture — the existing cap test (`test_max_concurrent_jobs_returns_429`, `tests/test_security_auth_token.py:298-328`) monkeypatches `jobs_mod._job_semaphore = asyncio.Semaphore(0)` inline and that is the pattern to copy. Author the succeeded-project setup inside the test using this file's existing project-creation helpers.

- [ ] **Step 1: Failing test:**

```python
async def test_rerun_respects_concurrency_cap(open_app_client, monkeypatch, tmp_path) -> None:
    project_id = await create_succeeded_project(open_app_client, tmp_path)  # local helper: create job with fake dispatcher, wait for succeeded
    monkeypatch.setattr(jobs_mod, "_job_semaphore", asyncio.Semaphore(0))
    resp = await open_app_client.post(f"/api/jobs/{project_id}/rerun")
    assert resp.status_code == 429
```

- [ ] **Step 2:** run → FAIL (202).
- [ ] **Step 3: Implement** — **placement anchor:** the acquire goes after the `assert_job_transition` guard succeeds (line ~477) and **before** `write_project(spec, reset_status)`, so a 429 leaves the stored state untouched. Copy `create_job`'s structure exactly: the `_job_semaphore._value <= 0` pre-check + acquire (`jobs.py:284-286`), `try/except` around everything from `write_project` onward that releases and re-raises, and `background_tasks.add_task(_pipeline_run_job_with_semaphore, spec)` instead of `_pipeline_run_job`.
- [ ] **Step 4:** `uv run pytest tests/test_security_auth_token.py -v` → PASS.
- [ ] **Step 5: Commit** — `fix(jobs): rerun respects PDOMAIN_MAX_CONCURRENT_JOBS`.

### Task 7: Timeout around dispatcher calls (partial mitigation — scope honestly)

**What this does:** stops a hung engine from wedging the job in "running" forever and permanently leaking a semaphore slot.
**What this does NOT do (document in code + changelog):** `run_ocr_batch` executes OCR in a thread-pool (`pdomain-ops local_stage.py:161-169`); `asyncio.wait_for` cancels the awaiting coroutine but **cannot stop the executor thread**, which keeps running and mutates the lock-free module-level `_predictor_cache` from a detached thread — a real race with later jobs. The cache lock belongs in pdomain-ops (Phase E issue 4). This task converts a permanent wedge into a bounded failure plus a known background-thread leak.

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/pipeline.py:429`, `src/pdomain_ocr_simple_gui/routes/pages.py:311`
- Test: `tests/test_pipeline.py`, `tests/test_routes_pages.py` (check the real pages test filename with `ls tests/ | grep pages` and use it)

**Interfaces:** `PDOMAIN_OCR_BATCH_TIMEOUT_S` env knob (float, default 900.0 per chunk; `<=0` disables). Python 3.11 unifies `TimeoutError`/`asyncio.TimeoutError`, and the existing per-chunk `except Exception` at `pipeline.py:502` / `pages.py:382` already marks pages failed — no new except clause needed, only a log message naming the timeout.

- [ ] **Step 1: Failing test** (use the file's own `_make_spec(tmp_path)` helper; `run_project(spec, dispatcher, status_callback)` returns `None` — read state back with `read_project`):

```python
async def test_run_project_times_out_hung_dispatcher(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PDOMAIN_OCR_BATCH_TIMEOUT_S", "0.05")

    class HungDispatcher:
        async def run_ocr_batch(self, req):
            await asyncio.sleep(30)

    spec = _make_spec(tmp_path)
    await run_project(spec, HungDispatcher(), lambda *_: None)
    _, status = read_project(spec.project_id)
    assert status.state == "failed"
    assert all(p.state == "failed" for p in status.pages)
```

- [ ] **Step 2:** run → FAIL (test itself would hang without the fix; keep the sleep at 30s so a regression fails fast via pytest timeout rather than hanging CI).
- [ ] **Step 3: Implement** the `_batch_timeout_s()` helper (module-level in `pipeline.py`, reused by `pages.py`) and wrap both call sites in `asyncio.wait_for(..., timeout=_batch_timeout_s())`. Add the honest limitation comment at the wrap site (executor thread survives; see ocr-container-meta issue Phase E issue 4).
- [ ] **Step 4:** `uv run pytest tests/test_pipeline.py -v` plus the pages test file → PASS.
- [ ] **Step 5: Commit** — `fix(pipeline): bound dispatcher waits with PDOMAIN_OCR_BATCH_TIMEOUT_S`.

### Task 8: Route update_page_result through the statechart

**Red-team correction folded in:** `pages.py::rerun_page` never gates on project state, so single-page rerun is legal from `failed` aggregate state too — the new transition must cover **both** `succeeded.to(running)` and `failed.to(running)` or this task regresses failed-job page rerun.

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/storage.py:318-345`, `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`
- Test: `tests/test_job_lifecycle_statechart.py`, `tests/test_storage.py`

**Interfaces:**

- `aggregate_pages_state(pages: list[PageResult], current: JobState) -> JobState` in `job_lifecycle.py`. Design (concrete, not "validate reachability"): compute the target with the existing precedence (running > failed > all-succeeded > queued > keep current — preserving `storage.py:324-333` order exactly), then map `(current, target)` to a machine event via an explicit table and fire it through `transition_job_state`; identical `current == target` short-circuits with no event:

```python
_AGG_EVENT: dict[tuple[str, str], str] = {
    ("queued", "running"): "start",
    ("running", "succeeded"): "succeed",
    ("running", "failed"): "fail",
    ("queued", "failed"): "fail",
    ("succeeded", "running"): "page_rerun",
    ("failed", "running"): "page_rerun",
    ("succeeded", "queued"): "rerun_requested",
    ("failed", "queued"): "rerun_requested",
    ("cancelled", "queued"): "rerun_requested",
}
```

An unmapped pair raises `InvalidJobTransition` — surfacing (not masking) any new divergence.

- New machine transition: `page_rerun = succeeded.to(running) | failed.to(running)` with a comment that it models in-place single-page rerun.

- [ ] **Step 1: Failing tests** — the parametrize table locks CURRENT precedence (including running-beats-failed) and adds both rerun paths:

```python
@pytest.mark.parametrize(
    ("page_states", "current", "expected"),
    [
        (["running", "queued"], "running", "running"),
        (["running", "failed"], "running", "running"),   # running wins over failed (current behavior)
        (["failed", "succeeded"], "running", "failed"),
        (["succeeded"], "running", "succeeded"),
        (["queued", "succeeded"], "succeeded", "queued"),
        (["running", "succeeded"], "succeeded", "running"),  # page rerun of a done job
        (["running", "succeeded"], "failed", "running"),     # page rerun of a failed job — regression guard
    ],
)
def test_aggregate_pages_state(page_states, current, expected) -> None: ...
```

- [ ] **Step 2:** run → FAIL (function undefined). Implement per the design above; `update_page_result` calls it and the `# type: ignore` at `storage.py:337` goes away. Check `tests/test_job_lifecycle_statechart.py` for any test asserting the complete transition set and extend it with `page_rerun`.
- [ ] **Step 3:** `uv run pytest tests/test_job_lifecycle_statechart.py tests/test_storage.py -v` plus the pages route tests → PASS.
- [ ] **Step 4: Commit** — `fix(statechart): single validated aggregation path for per-page updates`.

### Task 9: Delete stale device-forwarding comments

**Files:** `src/pdomain_ocr_simple_gui/pipeline.py:59-65,87-89,329-334`; test `tests/test_pipeline.py:604`.

Comment-only rewrite: `OcrBatchRequest.device` **is** populated from `resolve_device(spec.device)` at `pipeline.py:426` and consumed by `LocalStageDispatcher.run_ocr_batch`. Also note the "Wave-3 batch seam (ocr-container-meta)" issue referenced in the old comment was never actually filed (tracker checked) — delete the reference entirely. Extend `test_run_ocr_batch_request_fields` to assert `req.device is None` for `device="auto"` and `"cpu"` for `"cpu"`.

- [ ] Update comments, extend the assertion, `uv run pytest tests/test_pipeline.py -v` → PASS, commit — `docs(pipeline): device forwarding is wired; assert it`.

### Task 10: Zip extraction hardening (red-team findings: bomb cap + event loop)

Two gaps in `uploads.py`: (a) the 2 GiB cap applies to **compressed** upload bytes only — `_extract_in_place` (`uploads.py:129-142`) calls `extractall` with no check on decompressed size (zip bomb); (b) extraction runs synchronously inside `async def post_upload` (`uploads.py:87`), stalling the event loop for every concurrent client.

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/uploads.py:79-142`
- Test: `tests/test_uploads.py`

**Interfaces:** `PD_OCR_SIMPLE_GUI_UPLOAD_MAX_EXTRACTED_BYTES` env knob (int, default = same value as `_max_bytes()`); exceeding it → 413 before any entry is extracted.

- [ ] **Step 1: Failing tests:**

```python
async def test_zip_bomb_rejected(async_client, monkeypatch) -> None:
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_MAX_EXTRACTED_BYTES", "1024")
    bomb = make_zip({"a.png": b"\0" * 10_000})  # 10 KB declared, tiny compressed
    resp = await async_client.post("/api/uploads", files={"files": ("b.zip", bomb, "application/zip")})
    assert resp.status_code == 413


async def test_zip_extraction_offloaded(async_client, monkeypatch) -> None:
    # extraction must run via asyncio.to_thread — assert with a monkeypatched marker
    called = {}
    real = asyncio.to_thread
    async def spy(fn, *a, **kw):
        called["fn"] = getattr(fn, "__name__", "?")
        return await real(fn, *a, **kw)
    monkeypatch.setattr(asyncio, "to_thread", spy)
    resp = await async_client.post("/api/uploads", files={"files": ("c.zip", make_zip({"a.png": b"x"}), "application/zip")})
    assert resp.status_code == 200 and called["fn"] == "_extract_in_place"
```

- [ ] **Step 2:** run → FAIL. Implement: in `_extract_in_place`, before extracting, `total = sum(i.file_size for i in zf.infolist())`; raise `HTTPException(413, "zip expands beyond extraction cap")` when over the knob; call site becomes `await asyncio.to_thread(_extract_in_place, target)` (HTTPException raised inside the thread propagates — verify, else raise a sentinel and translate).
- [ ] **Step 3:** `uv run pytest tests/test_uploads.py -v` → PASS.
- [ ] **Step 4: Commit** — `fix(security): cap zip extraction size; extract off the event loop`.

### Task 11: Truthful drop-zone copy driven by backend limits

**Corrections folded in:** the env var is `PD_OCR_SIMPLE_GUI_UPLOAD_MAX_BYTES` (`uploads.py:42` — `PD_OCR`, not `PDOMAIN_OCR`); the helpers are private `_max_bytes()`/`_max_files()` (`uploads.py:40-47`) — **rename them** to public `upload_max_bytes()`/`upload_max_files()` (update their in-file callers) rather than importing underscore names; the config test file is `tests/test_config_route.py` (sync `TestClient(create_app())` pattern); the config route is `routes/config.py` with `ConfigResponse{mode, is_containerized, detected_device, gpu_available, ocr_engines}`.

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/routes/config.py`, `src/pdomain_ocr_simple_gui/routes/uploads.py:40-47`
- Modify: `frontend/src/components/SourcePicker.tsx:179-181,206-208`, `frontend/src/statecharts/jobCreationMachine.ts` (config shape), `frontend/src/pages/HomePage.tsx` (prop pass-through)
- Test: `tests/test_config_route.py`, `frontend/src/components/__tests__/SourcePicker.test.tsx`

- [ ] **Step 1: Failing backend test:**

```python
def test_config_reports_upload_limits(monkeypatch) -> None:
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_MAX_BYTES", str(3 * 1024**3))
    client = TestClient(create_app())
    body = client.get("/api/config").json()
    assert body["upload_max_bytes"] == 3 * 1024**3
    assert body["upload_max_files"] == 5000
```

- [ ] **Step 2:** run → FAIL (KeyError). Add `upload_max_bytes: int` / `upload_max_files: int` to `ConfigResponse`, populated from the renamed helpers. PASS.
- [ ] **Step 3: Failing frontend test:**

```tsx
it("renders backend-provided size cap and zip in the formats line", () => {
  render(<SourcePicker {...baseProps} uploadMaxBytes={2 * 1024 ** 3} />);
  expect(screen.getByText(/ZIP/)).toBeInTheDocument();
  expect(screen.getByText(/max 2 GiB/)).toBeInTheDocument();
});
```

- [ ] **Step 4: Implement copy** — heading paragraph: `PDF, multi-page TIFF, ZIP, or a folder of images. Pages are queued and OCR'd in the background.` Formats line: `` `PDF | TIFF | JP2 | PNG | JPG | ZIP | max ${formatBytes(uploadMaxBytes)}` `` with a local `formatBytes` (GiB, `2 GiB` not `2.0 GiB`); when the prop is absent render the line without the `| max …` segment. Optional `uploadMaxBytes?: number` prop threaded from the config load (extend the TS config type with the two new fields — additive, non-breaking).
- [ ] **Step 5:** `make frontend-test AI=1` + `make test AI=1` → PASS. Commit — `fix(ui): drop-zone copy tells the truth (zip + real cap)`.

### Task 12: Remove dead header controls (bell, user menu, fake search)

**Files:**

- Modify: `frontend/src/App.tsx:492-542`
- Test: `frontend/src/__tests__/App.test.tsx`

Pre-verified: no behavior spec or test cites `app-header-bell`/`app-header-user`/the Search button (`rg` over `docs/ tests/ frontend/src` — only the plan doc mentions them).

- [ ] **Step 1: Failing test:**

```tsx
it("renders no dead header affordances", () => {
  renderApp();
  expect(screen.queryByTestId("app-header-bell")).toBeNull();
  expect(screen.queryByTestId("app-header-user")).toBeNull();
  expect(screen.queryByLabelText("Search")).toBeNull();
});
```

- [ ] **Step 2:** run → FAIL. Delete the three `<button>` blocks; keep layout intact (replace the search column with a flexible spacer so brand stays left, actions right). Remove their testid constants from `frontend/src/lib/testids.ts` if present.
- [ ] **Step 3:** `make frontend-test AI=1` → PASS. Commit — `fix(ui): remove dead bell/user/search header controls`.

### Task 13: Wire the update-policy selector to suite prefs

**Files:**

- Modify: `frontend/src/App.tsx:142-153` (`UpdatePanelContent`)
- Test: `frontend/src/__tests__/AppSettingsPanels.test.tsx`

**Interfaces:** `GET /api/suite/prefs` → `{ common: { update_policy: "notify"|"auto"|"manual"|null, ... } }`; `PUT /api/suite/prefs/common` (204) with the **full** common object (the route replaces `common` wholesale — a partial body would blank sibling fields, so read-modify-write). After Task 5 this PUT requires the token; use `apiFetch` (Task 1) for both calls. Error/loading rendering mirrors `ComputePanelContent` (`App.tsx:100-120`, `role="alert"` paragraph).

- [ ] **Step 1: Failing test:**

```tsx
it("loads and persists update policy via suite prefs", async () => {
  mockFetchSuitePrefs({ common: { update_policy: "manual" } });
  renderUpdatePanel();
  expect(await screen.findByDisplayValue(/manual/i)).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText(/policy/i), "auto");
  expect(lastPutBody("/api/suite/prefs/common")).toMatchObject({ update_policy: "auto" });
});
```

- [ ] **Step 2:** run → FAIL (policy hardcoded to "notify", `onPolicyChange` is `() => undefined`). Implement: `useState` + mount effect GET (404/error → keep `"notify"`, disable selector, render error text); on change: GET fresh `common`, set `update_policy`, PUT whole object.
- [ ] **Step 3:** `make frontend-test AI=1` → PASS. Commit — `fix(settings): update policy selector persists to suite prefs`.

### Task 14: Frontend dead code — failed state, stale testid, visible config-fetch failure

**Files:**

- Modify: `frontend/src/statecharts/jobCreationMachine.ts:319`, `frontend/src/lib/testids.ts:27-28`, `frontend/src/App.tsx` (banner), `frontend/src/runtime/ConfigContext.tsx:49-86`
- Modify: `docs/specs/behavior/screen-app-shell.md:59` — the doc cites `APP_TEST_IDS.jobsPillPopover`; deleting the constant without touching this line ships a dangling doc reference (red-team catch). Update the spec's selector table in the same commit and reindex docgraph.
- Test: `frontend/src/runtime/__tests__/ConfigContext.test.tsx`, `frontend/src/__tests__/App.test.tsx`

- [ ] **Step 1:** Delete the unreachable `failed: {}` state and the `jobsPillPopover` constant + comment (scope check: `rg jobsPillPopover frontend/src docs/` — expect exactly the testids.ts definition and the screen-app-shell.md citation; fix both). `make frontend-test AI=1` → PASS.
- [ ] **Step 2: Failing test:**

```tsx
it("shows a banner when /api/config cannot be loaded", async () => {
  mockFetchConfigFailure();
  renderApp();
  expect(await screen.findByText(/could not load app configuration/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Implement** — consume `useConfigStatus()` in the App shell: on `error`, render a dismissible banner ("Could not load app configuration — some options are hidden. Retry") wired to `reload()`. Deduplicate `ConfigContext.tsx`'s copy-pasted fetch logic (mount effect calls the same `load()` callback).
- [ ] **Step 4:** `make frontend-test AI=1` → PASS; reindex docgraph (spec touched). Commit — `fix(ui): surface config load failures; drop dead state/testid`.

### Task 15: Remove dead AppPrefs fields

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/models.py:81-82`
- Test: `tests/test_models.py`, `tests/test_routes_prefs.py` (verify the real prefs test filename with `ls tests/ | grep prefs`)

- [ ] **Step 1: Failing test** (old prefs.json files containing the fields must still parse — confirm `AppPrefs.model_config` doesn't set `extra="forbid"`; if it does, set `extra="ignore"` for this model):

```python
def test_prefs_ignores_removed_fields(tmp_prefs_root, monkeypatch) -> None:
    write_prefs_json({"save_json_default": False, "combined_txt_default": True})
    prefs = load_prefs()
    assert not hasattr(prefs, "save_json_default")
```

- [ ] **Step 2:** run → FAIL. Remove both fields; fix every reference (`rg -l "save_json_default|combined_txt_default" src/ tests/ frontend/` first).
- [ ] **Step 3:** `make test AI=1` → PASS. Commit — `chore(prefs): drop write-only save_json/combined_txt fields`.

---

## Phase B — pdomain-ops: device vocabulary + batch resolver

Executed by a subagent in a worktree of `/workspaces/pdomain/pdomain-ops`. **Critical setup correction (red team):** the interactive checkout sits on branch `plan/issues-to-docs-roadmap-migration` — a worktree cut from HEAD would drag 4 unrelated commits toward the release. Cut explicitly from master:

```bash
git -C /workspaces/pdomain/pdomain-ops fetch origin
git -C /workspaces/pdomain/pdomain-ops worktree add <path> -b fix/device-vocabulary origin/master
```

Follow pdomain-ops's own CLAUDE.md/CONVENTIONS.md and Make targets. **Changelog convention (red team):** pdomain-ops maintains an `[Unreleased]` section in `CHANGELOG.md` and every release ships a changelog commit — Tasks 16/17 must add their entries there.

### Task 16: Canonical device vocabulary

**Files (relative to the pdomain-ops worktree):**

- Modify: `pdomain_ops/gpu/device.py`, `pdomain_ops/gpu/local_stage.py:83-91,126`, `pdomain_ops/suite/device_routes.py:63-68`, `CHANGELOG.md` (`[Unreleased]`)
- Test: `tests/gpu/test_pick_device.py`, `tests/gpu/test_local_stage_dispatcher.py`, `tests/gpu/test_local_stage_device_pref.py`, `tests/suite/test_device_routes.py` (real filenames — there is no `tests/gpu/test_device.py`)

**Interfaces produced in `pdomain_ops/gpu/device.py`:**

```python
def canonical_execution_device(device: str | None) -> str | None:
    """Map any accepted device id to registry vocabulary ('local'/'mps'/'cpu').

    'cuda', 'cuda:0', 'cuda:1', ... -> 'local'; passthrough otherwise; None -> None.
    """

def display_device_id(execution_device: str, available_ids: list[str]) -> str:
    """Map 'local' to the first matching 'cuda:N' in available_ids (else return unchanged)."""
```

Rationale for normalizing at the consumers (not inside `resolve_effective_device`): resolution stays pure, a stored `"cuda:0"` pref round-trips unchanged for display, and each boundary applies its own vocabulary (route = display ids, dispatcher = registry keys `"cpu"/"local"/"mps"` — the only keys `register_default_stages` registers, `default_stages.py:77-79`).

- [ ] **Step 1: Failing unit tests** for both helpers (`"cuda:0"→"local"`, `"cuda"→"local"`, `"cpu"→"cpu"`, `None→None`; `display_device_id("local", ["cuda:0","cpu"]) == "cuda:0"`, `display_device_id("local", ["cpu"]) == "local"`, `display_device_id("cpu", [...]) == "cpu"`).
- [ ] **Step 2: Failing integration tests with the REAL vocabulary** (the untested gap that let this ship):

```python
def test_get_device_translates_auto_local_to_cuda_id(monkeypatch, client) -> None:
    monkeypatch.setattr(device_routes, "list_devices", lambda: [fake_cuda0(), fake_cpu()])
    monkeypatch.setattr(device_prefs, "pick_device", lambda: "local")
    body = client.get("/api/suite/device").json()
    assert body["current"] == "cuda:0"
    assert body["current"] in {d["id"] for d in body["available"]}


async def test_run_stage_accepts_cuda_id(dispatcher_with_local_stage) -> None:
    result = await dispatcher_with_local_stage.run_stage("ocr", "p1", device="cuda:0")
    assert result.device == "local"  # registry hit, no silent cpu fallback


async def test_run_stage_canonicalizes_resolver_output() -> None:
    # red-team catch: the resolver path must be canonicalized too, or a stored
    # "cuda:0" pref reintroduces the exact silent-cpu-fallback bug this fixes
    d = LocalStageDispatcher(device_resolver=lambda: "cuda:0")
    register_fake_stage(d, "ocr", devices=("local", "cpu"))
    result = await d.run_stage("ocr", "p1")
    assert result.device == "local"
```

- [ ] **Step 3: Implement** — `run_stage` (`local_stage.py:83-84`) must canonicalize **every** candidate, mirroring Task 17's OR-chain:

```python
        device = canonical_execution_device(device) or (
            canonical_execution_device(self._device_resolver()) if self._device_resolver else None
        ) or pick_device()
```

`device_routes.get_device`: `current=display_device_id(resolve_effective_device(prefs, app_id, snapshot=snap), [d.id for d in devices])`.

- [ ] **Step 4:** pdomain-ops full gate (its own `make ci AI=1`-equivalent) → PASS. Add the `[Unreleased]` changelog entry. Commit — `fix(gpu): one device vocabulary at both boundaries`.

### Task 17: run_ocr_batch honors device_resolver

**Files:** `pdomain_ops/gpu/local_stage.py:126`; test `tests/gpu/test_local_stage_dispatcher.py`; `CHANGELOG.md`.

- [ ] **Step 1: Failing test:**

```python
async def test_batch_uses_device_resolver_when_request_has_no_device(monkeypatch) -> None:
    d = LocalStageDispatcher(device_resolver=lambda: "cpu")
    captured = {}
    monkeypatch.setattr(local_stage, "run_doctr_batch", capture_into(captured))
    await d.run_ocr_batch(OcrBatchRequest(images=[b"x"], source_identifiers=["s/0"], engine="doctr", language="en"))
    assert captured["device"] == "cpu"
```

- [ ] **Step 2: Implement:**

```python
        device = canonical_execution_device(req.device) or (
            canonical_execution_device(self._device_resolver()) if self._device_resolver else None
        ) or pick_device()
```

- [ ] **Step 3:** repo gate → PASS. Changelog entry. Commit. Hand back **worktree path + branch** for `finishing-a-development-branch`; merge target is pdomain-ops **master**; do not push (pushing happens via the Phase C release, human-gated).

---

## Phase C — RELEASE GATE (HUMAN APPROVAL REQUIRED)

- [ ] **Gate C1 (human):** approve merging `fix/device-vocabulary` into pdomain-ops master and running `make release-patch` there. Disclose accurately (red-team corrections): master is **12 commits** past `v0.11.0` — the release ships those too; separately, the branch `plan/issues-to-docs-roadmap-migration` (4 commits) stays unmerged and unreleased. `release-patch` runs `ci-slow`, tags `v0.11.1`, and **pushes**. Note `ocr-container-meta#210` (workspace-wide release-discipline spec, open) — this ad-hoc release should be mentioned there if #210 lands conventions later.
- [ ] **Registry propagation (red team):** `release-patch` does NOT synchronously update `pdomain-index-pip`. The release workflow pings the index only if `PDOMAIN_INDEX_DISPATCH` is configured; otherwise the index regenerates on its daily cron (03:17 UTC). After the release: trigger the index's `workflow_dispatch` manually (or wait for the dispatch/cron), and poll until `make update-pdomain-deps` stops failing with "sibling not yet seeded".
- [ ] **Run the dep bump in the interactive checkout, NOT a worktree** — `update-pdomain-deps.sh` resolves the canonical repo root via `git-common-dir` and edits the main checkout regardless of cwd (open bug `ocr-container-meta#386`); running it from a worktree strands the diff in the wrong tree. In `/workspaces/pdomain/pdomain-ocr-simple-gui`: `make update-pdomain-deps`, review the diff, bump the floor in `pyproject.toml:17` to `pdomain-ops>=0.11.1`, `make ci AI=1`, commit — `chore: require pdomain-ops with device vocabulary fix`.
- **Phase D cannot start before this gate completes** (red-team correction): `make local-dev` only overlays the canonical checkout's `.venv`; worktrees carry their own `.venv` synced from the registry pin, so there is no supported way to develop Phase D in an isolated worktree against unreleased pdomain-ops. Phase D therefore runs after the registry bump, in the interactive checkout, sequentially.

## Phase D — this repo: settings preference reaches execution

### Task 18: Fix the suite mount wiring (pre-existing bug, red-team find)

**The premise fix:** `app.py:163` calls `_mount_suite_routes(_app)` with no `adapters` and no `suite_app`. Per `pdomain_ops/suite/routes.py:16-19,104-108`, that mounts device routes with a **fresh** `SuiteAdapters.local()` (a different `PrefsAdapter` instance than app.py's own `_prefs_adapter`) and `app_id="unknown"` — so the Settings panel persists the compute pref under `apps["unknown"]` today. Without this task, Task 19's resolver would read a key nobody writes.

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/app.py:157-163`
- Test: `tests/test_app_suite_mount.py` (new; TestClient inline pattern)

- [ ] **Step 1: Failing test:**

```python
def test_device_put_persists_under_real_app_id(tmp_prefs, monkeypatch) -> None:
    client = TestClient(create_app())
    client.put("/api/suite/device", json={"scope": "app", "device": "cpu"})
    snap = read_prefs_snapshot(tmp_prefs)
    assert snap.apps.get("pdomain-ocr-simple-gui", {}).get("compute_device") == "cpu"
    assert "unknown" not in snap.apps
```

- [ ] **Step 2: Implement** — build the suite mount with shared state: construct `SuiteAdapters` around the app's existing `_prefs_adapter` and pass a `suite_app` whose `app_id` is `"pdomain-ocr-simple-gui"` (reuse the `_APP_ID` constant from `routes/jobs.py:43` — move it to a shared module, e.g. `pdomain_ocr_simple_gui/constants.py`, imported by both). Check `SuiteAdapters`/`SuiteApp` constructor signatures in the *released* pdomain-ops before coding. Add a one-time migration: on startup, if `apps["unknown"].compute_device` exists and the real app key has none, copy it over and delete the `unknown` entry (users who already set a device keep it).
- [ ] **Step 3:** `make ci AI=1` → PASS. Commit — `fix(suite): mount routes with real app id and shared prefs adapter`.

### Task 19: Construct dispatcher with device_resolver

**Files:**

- Modify: `src/pdomain_ocr_simple_gui/app.py:80-96` (both `LocalStageDispatcher()` constructions — primary and the bare fallback in the `except` branch)
- Test: `tests/test_app_suite_mount.py` (extend)

- [ ] **Step 1: Failing test:**

```python
def test_dispatcher_resolver_follows_suite_pref(tmp_prefs) -> None:
    app = create_app()
    write_app_pref(tmp_prefs, "pdomain-ocr-simple-gui", "compute_device", "cpu")
    assert app.state.dispatcher._device_resolver() == "cpu"
```

- [ ] **Step 2: Implement:**

```python
            _dispatcher = LocalStageDispatcher(
                device_resolver=lambda: resolve_effective_device(_prefs_adapter, APP_ID)
            )
```

(`resolve_effective_device` from `pdomain_ops.suite.device_prefs`; the lambda defers the prefs read to call time, so construction order doesn't matter.)

- [ ] **Step 3:** `make ci AI=1` → PASS. Commit — `feat(compute): suite device preference governs OCR execution`.
- [ ] **Step 4: End-to-end verification (verify skill):** `make run`; Settings → Compute → Force CPU; run a small job; confirm the logged chosen device is `cpu`. Reset to auto on a CUDA machine: panel highlights `cuda:0`, header reads "Active: cuda:0 (via auto)", logged device is `local`.

## Phase E — file cross-repo issues (`ConcaveTrillion/ocr-container-meta`)

Checked against the live tracker: none of these duplicate an existing issue.

- [ ] **Issue 1 — pdomain-ui: ComputeTargetPanel test realism + friendly active-device label.** Fixtures only use `current: 'cuda:0'`, never the pre-fix backend reality `current: 'local'` (`ComputeTargetPanel.test.tsx:6-13,129,158`); add a contract test pinning `current ∈ available ids`; consider a friendly label ("NVIDIA GeForce … (auto)") instead of the raw id. No release urgency.
- [ ] **Issue 2 — simple-gui: job cancellation endpoint (deferred).** `cancelled` modeled end-to-end (`job_lifecycle.py:33,39`) but no route fires `cancel`; frontend no-ops it (`useOcrJob.ts:97-98`). Decide ship-or-strip.
- [ ] **Issue 3 — simple-gui: deduplicate the two /api/config fetchers** (`ConfigContext` vs `jobCreationMachine.defaultLoadConfig`); Task 14 made failures visible; unification is cosmetic follow-up.
- [ ] **Issue 4 — pdomain-ops: lock `_predictor_cache` (thread-safety).** `run_ocr_batch` mutates the module-level dict lock-free from executor threads (`local_stage.py:123,129-150`); after this plan's Task 7, a timed-out batch's abandoned thread can race a later job's predictor build. Needs a `threading.Lock` around read-check-write.
- [ ] **Issue 5 — simple-gui: Settings field for the API token.** Task 1 ships localStorage-only token entry (console command, documented in the install runbook); a proper Settings input with masked display is follow-up UI work.
- [ ] File each with `gh issue create --repo ConcaveTrillion/ocr-container-meta ...` after checking label/milestone shape via `gh issue list --repo ConcaveTrillion/ocr-container-meta --limit 5`. Backfill issue numbers: #2 → Task 21's intent-map entry + the statechart comment; #4 → Task 7's code comment.

## Phase F — docs refresh + governance postflight

### Task 20: Re-verify the two stale behavior specs

**Files:** `docs/specs/behavior/screen-page-view.md`, `docs/specs/behavior/screen-results.md`

- [ ] Rewrite the download sections against the post-Task-9 (commit `8d49ad3`) UI: two buttons `download-images-text` / `download-images-text-json`, shortcuts `mod+shift+t` / `mod+d`; delete `page-download-text|json|both`, `download-results-button`, `download-filter-text|json` and the checkbox prose. Verify every selector named in each spec against `rg -o 'data-testid="[^"]+"' frontend/src | sort -u`. Update `Last verified` honestly; regenerate coverage (`make behavior-coverage` target or `uv run python -m scripts.behavior_coverage`) and confirm `tests/test_behavior_coverage.py` passes.
- [ ] Commit — `docs(specs): re-verify download behavior against Task-9 UI`.

### Task 21: Fix current-state.md, log decisions, mark cancel deferred

**Files:** `docs/context/current-state.md`, `docs/context/decisions.md` (append-only), `docs/context/intent-map.md`, `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py:39`

- [ ] current-state: replace the "docs/docgraph-migration branch in flight" paragraph (that branch never existed on this repo; the migration merged as `f99793d`); record this plan's execution as in-flight while it runs. **Also add an inbound link to this plan doc** (fixes its docgraph orphan advisory).
- [ ] decisions.md (append): device vocabulary normalized in pdomain-ops at route/dispatcher boundaries, not inside `resolve_effective_device`; all mutating routes (app + suite) now require the API token; frontend token via `apiFetch` + localStorage; upload limits served by `/api/config` so UI copy cannot drift; suite routes mounted with real `app_id` + shared prefs adapter (was `"unknown"` + orphan adapter).
- [ ] intent-map: add "job cancellation — deferred (issue E2)", "config-fetch dedup — deferred (issue E3)", "token Settings field — deferred (issue E5)".
- [ ] statechart comment at `cancel = running.to(cancelled)`: `# Modeled but unreachable: no cancel endpoint ships yet (ocr-container-meta#E2, deferred). Frontend no-ops cancellation (useOcrJob.ts).`
- [ ] Reindex docgraph. Commit — `docs(context): reflect merged migration + review-fix decisions`.

### Task 22 (OPTIONAL, non-gating): Agent Index backfill

Red-team verified: `docgraph check --strict` does not require Agent Index sections (`docgraph.toml` has no such `required_sections` rule), so this is consistency polish, not gate work. If executed: add a 4-line Agent Index to the 16 docs lacking one (architecture/ ×3, process/ ×4, specs/behavior/ ×6 minus generated coverage.md, specs/2026-05-29-download-model.md, decisions/2026-06-04, README.md); one mechanical subagent; commit `docs: add Agent Index sections repo-wide`. Skip freely if time-boxed.

### Task 23: Postflight gate

- [ ] `docgraph reindex` → `docgraph check --strict`: **no blocking issues**, and no advisories on files this plan touched (the plan doc itself must be non-orphan by now via Task 21's inbound link; its `## Goal`/`## Architecture`/`## Tech Stack` headings satisfy the structural parser — rev 2 already uses real headings).
- [ ] `make ci AI=1` here; pdomain-ops gate ran in Phases B/C.
- [ ] Emit the postflight manifest per DOCGRAPH.md (status-reconciler only if check surfaces field conflicts).

---

## Execution model

- One implementation subagent per task (`writing-python:python-implementer` for Python, general implementer for TS), `isolation: "worktree"`, `model: sonnet`; reviewer between tasks per superpowers:subagent-driven-development. **Phase A is strictly sequential** (same-file overlap: Tasks 2/10/11 → `uploads.py`; 4/6 → `jobs.py`; 12/13/14 → `App.tsx`; 1/11/14 → `jobCreationMachine.ts`).
- Phase B may run concurrently with Phase A (different repos, worktree from `origin/master`).
- Phase C blocks Phase D entirely (no local-dev workaround in worktrees). Phases E and F run after A and B merge locally.
- Nothing is pushed until the human gate; integration of this repo's branch via `finishing-a-development-branch`.

## Self-review notes

- Finding→task map: frontend token wrapper (1), uploads auth (2), words traversal (3), per-id GET (4), suite middleware (5), rerun semaphore (6), timeout (7), statechart bypass (8), stale comments (9), zip bomb + event loop (10), copy/cap (11), dead header buttons (12), update policy (13), dead code + config error + jobsPillPopover doc (14), dead prefs fields (15), device vocabulary + display + resolver canonicalization (16), batch resolver (17), suite mount app_id (18), settings→execution (19), stale specs (20), current-state/decisions/cancel comment (21), Agent Index (22, optional), postflight (23). Issues cover: panel test realism (E1), cancellation (E2), config dedup (E3), predictor-cache lock (E4), token Settings UI (E5).
- Deliberate non-fixes: default CI still skips real OCR (documented tradeoff); FakeStageDispatcher still lacks `run_stage` (accepted); executor threads survive Task 7 timeouts (documented; E4 tracks the shared-cache lock); non-constant-time token comparison (noted by red team, not elevated); zip-entry symlink concerns (no practical injection path found).

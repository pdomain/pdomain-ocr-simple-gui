---
Status: draft
Owner: CT
Created: 2026-07-21
Last verified: 2026-07-21
Kind: plan
---

# Deferred Follow-ups Plan (2026-07-21)

> **For agentic workers:** REQUIRED SUB-SKILL — use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans` to
> implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for
> tracking. Every behavior change is TDD: failing test first.

## Agent Index

- **Kind:** plan
- **Status:** draft
- **Read when:** implementing the three deferred `simple-gui` follow-ups from the
  2026-07-14 review — API-token Settings field, `/api/config` fetch dedup, and
  the job-cancellation ship-or-strip decision.
- **Search terms:** deferred follow-ups, API token settings, apiFetch token,
  config fetch dedup, fetchRuntimeConfig, job cancellation, cancel endpoint,
  strip cancelled state, ocr-container-meta 395 396 398.

## Goal

Close the three actionable deferred items on the
[roadmap](../roadmap.md) "Next" list, each an `effort:S` follow-up filed during
the 2026-07-14 review-fixes Phase E:

- **#398** — add a Settings field for the API token (today it is devtools-only).
- **#396** — collapse the two `/api/config` fetchers into one fetch+parse site.
- **#395** — decide job cancellation ship-or-strip, then execute the decision.

Each phase is self-contained and independently shippable. There are no ordering
dependencies between them, so they may be worked in any order or in parallel
worktrees.

## Decision recorded for #395: STRIP (recommended)

The issue's acceptance bar for "ship" — a cancel that *actually interrupts the
running dispatcher call* — is not achievable with the current
`LocalStageDispatcher`. The OCR batch runs in a `ThreadPoolExecutor` work item
(`pdomain-ops` `local_stage.py:179-192`), and `concurrent.futures` work items
cannot be cancelled once running. This exact limitation is already documented
twice in this repo (`pipeline.py:446-456`, `routes/pages.py:311-322`) and tracked
upstream as `ocr-container-meta#397`. On top of that, there is **no UI cancel
button anywhere** — `App.tsx` hardcodes `cancelable: false` and `ResultsPage.tsx`
never even destructures `cancel`. So "ship" would mean new backend plumbing, a
new frontend affordance, and race-safe status writes, all for a cancel that still
can't stop the in-flight batch.

**Strip is risk-free**: the `cancel` transition has never fired (no route ever
called it), so removing it changes zero runtime behavior. Phase 3 below plans
both paths; execute **Plan B (strip)** unless a human overrides. This is the one
item in this plan that is a genuine product call — flag it before executing if
there is any appetite to redefine "cancel" as cooperative-at-chunk-boundary.

## Architecture

Phases 1 and 2 are frontend-only. Phase 3 (strip) touches the backend
lifecycle statechart plus a small frontend cleanup. No phase adds a backend
route or changes the OCR pipeline. The three phases share no state and have no
ordering dependency, so each is an independent worktree.

## Tech Stack

FastAPI + Pydantic + pytest (backend), React + Vite + TS + vitest (frontend),
`uv`, `xstate` (frontend statecharts), `python-statemachine` (backend
lifecycle).

## Global constraints

- Run `make ci AI=1` in this repo before every commit batch. Never
  `python -m pytest` — always `uv run pytest` or `make test AI=1`.
- TDD: a failing test first for every behavior change (copy-only and comment-only
  changes exempt).
- Work in isolated worktrees (`superpowers:using-git-worktrees`); pass
  `isolation: "worktree"` to implementation subagents.
- Commit locally; **never push** and **never release** without explicit human
  approval.
- After editing any doc under `docs/`, reindex docgraph the same turn; final gate
  is `docgraph check --strict` with no blocking issues.
- On completion, retire each item: move its roadmap "Next" bullet to "Done" and
  close the matching `ConcaveTrillion/ocr-container-meta` issue.

---

## Phase 1 — #398: Settings field for the API token

**Goal:** add a `Settings > API Token` panel so a user can view (masked), set,
update, and clear the `pdomain.apiToken` localStorage key that `apiFetch.ts`
already consumes — no devtools console required. No backend endpoint.

**Files:**

- Create: `frontend/src/components/ApiTokenSettings.tsx`
- Create: `frontend/src/components/__tests__/ApiTokenSettings.test.tsx`
- Modify: `frontend/src/api/apiFetch.ts` — export the existing private
  `TOKEN_STORAGE_KEY` const (`apiFetch.ts:19`) so the component reuses the literal
  instead of duplicating `"pdomain.apiToken"`.
- Modify: `frontend/src/lib/testids.ts` — add a `settingsApiToken*` block after
  the `settingsJobsLocation*` block (`testids.ts:96-103`).
- Modify: `frontend/src/App.tsx` — import `ApiTokenSettings`, append
  `{ id: "api-token", label: "API Token", content: <ApiTokenSettings /> }` to
  `settingsPanels` (`App.tsx:250-269`), as the last entry.
- Modify: `docs/runbooks/install.md` — the API-token section (`install.md:47-61`):
  lead with the Settings field, keep the `localStorage.setItem` snippet as a
  documented headless fallback.

**Interfaces:**

- `export function ApiTokenSettings(): JSX.Element` — no props, mirroring the
  zero-prop `ModelCacheSettings` / `JobsLocationSettings`.
- Reads/writes `localStorage["pdomain.apiToken"]` exclusively — the exact key
  `apiFetch.ts:20` reads. No `apiFetch` behavior change.
- pdomain-ui derives `settings-modal-tab-api-token` /
  `settings-modal-panel-api-token` from the panel `id`.

**Design decisions:**

- **No network, no `useEffect`.** The token lives only in localStorage, so seed
  the input synchronously: `useState(() => localStorage.getItem(KEY) ?? "")`.
  This avoids the async-load-clobbers-edit class of bug `JobsLocationSettings`
  had to guard against — there is nothing async to race.
- **Masking:** `Input type={revealed ? "text" : "password"}` with a
  `Button variant="ghost"` Show/Hide toggle in the same row as Save/Clear —
  mirrors `JobsLocationSettings.tsx:141-171` rather than introducing the unused
  `Input` `suffix` prop.
- **Save/Clear:** edit-then-Save (no per-keystroke write). Save writes the
  trimmed value and shows a transient "Saved" indicator (the existing `savedOk`
  pattern). Clear calls `removeItem` and resets. **Saving an empty value clears
  the key** rather than storing `""` (an empty string would still satisfy
  `apiFetch`'s truthy check at `apiFetch.ts:22`).
- **Status line:** a read-only line above the input showing `set` / `not set` —
  never renders the raw token.

**Steps (TDD):**

- [ ] **1.** Write the failing test `ApiTokenSettings.test.tsx` (use
  `renderWithProviders`, `userEvent`, `APP_TEST_IDS`): not-set status + masked
  empty input with no stored key; seeds from localStorage still masked; type +
  Save writes the key and shows the "Saved" confirmation; reveal toggle flips
  `input.type` to `text`; Clear removes the key and empties the input; saving an
  empty value clears the key.
- [ ] **2.** `make frontend-test AI=1` → FAIL (component missing).
- [ ] **3.** Add `export` to `TOKEN_STORAGE_KEY` in `apiFetch.ts:19` (no other
  change to that file).
- [ ] **4.** Add the `settingsApiToken*` testids block after `testids.ts:103`.
- [ ] **5.** Implement `ApiTokenSettings.tsx` matching sibling styling
  (`className="label"` heading, `<code>` status value, helper text).
- [ ] **6.** Wire the panel into `App.tsx` `settingsPanels` and extend the panel
  doc comment above it.
- [ ] **7.** `make frontend-test AI=1` → PASS, no regressions in `App.test.tsx`
  or `JobsLocationSettings.test.tsx`.
- [ ] **8.** `make frontend-build AI=1` → clean.
- [ ] **9.** Update `install.md` API-token section.
- [ ] **10.** `make ci AI=1` → green. Commit —
  `feat(frontend): add Settings field for the API token (#398)`.

**Open questions:** exporting `TOKEN_STORAGE_KEY` is a 1-line change outside the
new component; if "no other code changes" is read strictly, fall back to a local
const with a comment. Empty-Save-clears is a design choice (no product spec); the
panel `id`/`label` grouping is a choice — confirm if an "Advanced" grouping is
preferred. Token-validation round-trip is explicitly out of scope per the AC.

---

## Phase 2 — #396: Deduplicate the two `/api/config` fetchers

**Goal:** make `GET /api/config` fetch + parse happen in exactly one place,
consumed by both `ConfigContext.tsx` (React) and `jobCreationMachine.ts` (xstate
actor), with no behavior change for existing consumers or tests.

**Chosen approach — shared helper, not context-in-machine.** Extract
`fetchRuntimeConfig()` into a new `frontend/src/api/config.ts` that both call.
The alternative ("machine reads `ConfigContext`") is not viable: the machine is a
plain `setup(...).createMachine(...)` invoked via `fromPromise` actors
(`jobCreationMachine.ts:101-143`) with no access to React hooks/context, and its
`loadingConfig` state has its own retry logic (`configFailed` / `CONFIG_RETRY`,
lines 176-198) that must run before config is known. Piping context in as actor
`input` would restructure the provider tree just to avoid one `fetch` — far more
blast radius than an `effort:S` item warrants.

**Bonus consolidation:** `RuntimeConfig` / `OcrEngineConfig` are currently defined
**twice, divergently** — `ConfigContext.tsx:18-31` (no `upload_max_*`) and
`jobCreationTypes.ts:3-18` (has `upload_max_bytes` / `upload_max_files`). The new
module owns the canonical **superset** type (extra fields optional, so safe); both
existing files re-export it under their current names so no import path breaks
(`JobConfigInline.tsx:26` imports `RuntimeConfig` from `jobCreationTypes` and must
keep working).

**Files:**

- Create: `frontend/src/api/config.ts` — canonical `RuntimeConfig`,
  `OcrEngineConfig`, and `fetchRuntimeConfig()`.
- Create: `frontend/src/api/__tests__/config.test.ts`.
- Modify: `frontend/src/runtime/ConfigContext.tsx` — `load()` (lines 50-63) calls
  `fetchRuntimeConfig()`; re-export the types from `../api/config`; drop the now
  unused `apiFetch` import.
- Modify: `frontend/src/statecharts/jobCreationMachine.ts` — replace
  `defaultLoadConfig()` (lines 51-55) with `loadConfig: fromPromise(fetchRuntimeConfig)`.
  **Keep** the `apiFetch` import — `defaultUploadFiles` / `defaultCreateJob` still
  use it.
- Modify: `frontend/src/statecharts/jobCreationTypes.ts` — re-export the types
  from `../api/config` (lines 3-18).

**Interface:**

```ts
// frontend/src/api/config.ts
export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  const res = await apiFetch("/api/config");
  if (!res.ok) throw new Error(`GET /api/config failed: ${res.status}`);
  return (await res.json()) as RuntimeConfig;
}
```

Error contract matches today's two sites combined: a non-ok response throws; a
rejected `fetch`/`apiFetch` propagates. `ConfigContext.load()`'s existing
`try/catch` already sets `error(true)` on both paths, so its `if (!res.ok)` branch
simply collapses into the catch — no behavior change.

**Steps (TDD):**

- [ ] **1.** Write failing `config.test.ts` (mock `globalThis.fetch`): fetches +
  parses `/api/config`; throws on a non-ok (500) response; propagates a network
  error.
- [ ] **2.** Implement `config.ts`; the test passes.
- [ ] **3.** Update `ConfigContext.tsx` (re-export types; `load()` delegates; drop
  `apiFetch` import). Its existing test must pass unmodified.
- [ ] **4.** Update `jobCreationTypes.ts` to re-export; `tsc --noEmit` clean
  (verifies `JobConfigInline` and other consumers).
- [ ] **5.** Update `jobCreationMachine.ts` (`loadConfig: fromPromise(fetchRuntimeConfig)`;
  keep `apiFetch` import). Its existing test passes unmodified (tests always
  `.provide()` a stub `loadConfig`).
- [ ] **6.** Verify: `grep -rn '"/api/config"' frontend/src` returns exactly one
  hit (`config.ts`); `make frontend-test AI=1`; `make typecheck`;
  `make frontend-lint`; `make frontend-knip`. Commit —
  `refactor(frontend): consolidate /api/config fetch into fetchRuntimeConfig() (#396)`.

**Open questions:** the canonical type must be the superset or `JobConfigInline`
typecheck breaks (verify with `tsc --noEmit`). `frontend-knip` may flag a
redundant re-export; drop the `ConfigContext` re-export if nothing imports the
type from that path.

---

## Phase 3 — #395: Job cancellation (execute STRIP; ship plan kept for the record)

### Plan B — Strip (recommended — execute this)

**Goal:** remove the unreachable `cancel` transition / `cancelled` state from the
statechart and the dead `cancel()` no-op from the frontend hook, **without**
narrowing the wire-level `ApiJobState` / `ProjectStatus.state` / `PageResult.state`
Literals. Those stay a superset for compatibility with the shared
`@pdomain/pdomain-ui` `JobState` type (`useOcrJob.ts:27`) — `"cancelled"` must
remain a value the frontend can *receive*, even though this app will never emit
it again.

**Files:**

- `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`
- `tests/test_job_lifecycle_statechart.py`
- `frontend/src/api/useOcrJob.ts`
- `frontend/src/api/__tests__/useOcrJob.test.tsx` (keep the "backend can still
  report cancelled" mapping test)
- `frontend/src/App.tsx` (comment cleanup only — already `cancelable: false`)

**Steps (TDD — the failing-test-first step is the statechart contract change):**

- [ ] **1.** In `test_job_lifecycle_statechart.py`: remove the
  `("running", "cancel", "cancelled")` valid-transition case (line 43) and the
  `("cancelled", "rerun_requested", "queued")` case (line 46); add
  `("running", "cancel")` to the invalid-event parametrization — this fails
  today because `cancel` still succeeds, which is the red step.
- [ ] **2.** Add an explicit `test_cancel_is_not_a_valid_lifecycle_event` so the
  removal is asserted, not just implied.
- [ ] **3.** Remove `cancel = running.to(cancelled)` and the
  `cancelled = State("cancelled")` declaration (`job_lifecycle.py:39,48`) and the
  stale comment (lines 45-47).
- [ ] **4.** Drop `| cancelled.to(queued)` from `rerun_requested` (line 49) and
  `("cancelled", "queued"): "rerun_requested"` from `_AGG_EVENT` (line 92).
- [ ] **5.** Narrow the **local** `JobLifecycleEvent` Literal (drop `"cancel"`),
  `JOB_STATES`, and local `JobState` (drop `"cancelled"`) — **module-local only**.
  Do not touch `models.py` / `storage.py` / `pipeline.py` / `routes/jobs.py` wire
  Literals.
- [ ] **6.** Run the statechart test file; fix any `basedpyright` `cast`/type
  errors from the narrower local `JobState`. Grep-verify no other backend module
  imports these symbols expecting `"cancel"`/`"cancelled"`.
- [ ] **7.** Frontend: remove `cancel: () => void` from `UseOcrJobResult`
  (`useOcrJob.ts:99`), stop returning/destructuring it (lines 225, 234). **Keep**
  `toHookStatus`'s `case "cancelled"` (lines 127-128) and its mapping test — the
  wire type can still deliver `"cancelled"`.
- [ ] **8.** Tighten stale `App.tsx` comments (lines 38, 448-449, 697-698) —
  no functional change.
- [ ] **9.** Verify:
  `uv run pytest tests/test_job_lifecycle_statechart.py tests/test_routes_jobs.py tests/test_behavior_coverage.py -q`;
  `uv run basedpyright src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`;
  `cd frontend && npm test -- useOcrJob && npm run lint && npx tsc --noEmit`;
  then `make ci AI=1`. Commit —
  `refactor: strip unreachable job-cancellation state (#395)`.

### Plan A — Ship (NOT recommended; kept so the decision is auditable)

Only a cooperative, chunk-boundary cancel is possible: `POST /api/jobs/{id}/cancel`
fires the `cancel` transition and stops `run_project`'s `while chunk_start < total`
loop (`pipeline.py:422`) from starting the *next* chunk — the in-flight batch (up
to `batch_pages`, default 8) still runs to completion. This needs: a
cancellation-signal store, a check inside `run_project` plus a three-way terminal
branch (replacing `terminal_event = "succeed" if all_done else "fail"` at
`pipeline.py:589`), race-safe writes against `storage.py`'s unlocked
read/write, semaphore-release-once coverage, and a brand-new frontend button
(none exists — `cancelable: false` is hardcoded). It still would not satisfy the
issue's "interrupts the running dispatcher call" bar. If chosen, TDD the route
(`tests/test_routes_jobs.py` `client_with_source` fixture: 202 + `cancelled`
state; 400 for non-running; 404 for missing), the pipeline early-stop, the
semaphore release, and the `useOcrJob` `cancel()` fetch.

**Risks either way:** the leaked-executor-thread problem (`#397`) means a
cancelled-then-rerun job could race the abandoned thread still mutating
`_predictor_cache`; a cancel endpoint makes that easier for a user to trigger.
`#397` stays open regardless of ship/strip.

---

## Done criteria

- [ ] Phase 1 (#398) shipped: masked token Settings panel, `make ci AI=1` green.
- [ ] Phase 2 (#396) shipped: single `/api/config` fetch site, `make ci AI=1`
  green.
- [ ] Phase 3 (#395) decision executed (strip): statechart + frontend cleaned,
  wire compatibility preserved, `make ci AI=1` green.
- [ ] Roadmap "Next" bullets moved to "Done"; `ocr-container-meta` #398 / #396 /
  #395 closed; docgraph reindexed and `check --strict` clean.

## Out of scope

- `#397` (predictor-cache lock) — lives in `pdomain-ops`, not this repo.
- `#26` (suite-launcher opener isolation) — blocked on a `@pdomain/pdomain-ui`
  release; see
  [the governed issue](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md).
- Download-truth separation, multilingual OCR profiles, richer project catalogue,
  hosted/packaged deployment — larger deferred items on the
  [intent map](../context/intent-map.md), not `effort:S` build tasks.
- Residual `# ---` divider banners under `tests/e2e/` (former #13) — trivial style
  cleanup tracked on the [roadmap](../roadmap.md) "Later" list.

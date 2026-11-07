---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-11-07
Kind: context
---

# Durable decisions and retirement tombstones

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** checking why documentation or product direction changed.
- **Search terms:** decisions, deviations, retirement, tombstones, security, tests,
  GitHub issue migration.

### 2026-07-19 — GitHub issue migration repair (ledger over false backlog)

- **Context:** On 2026-07-17 all 37 repository GitHub issues were deleted after
  dumping bodies into a temporary archive (`ec3979f`, removed in `7f3be6b`) and
  listing them as open work on `docs/roadmap.md`. That roadmap claim conflicted
  with code: most issues were already fixed.
- **Decision:** Keep a recomputable
  [migration ledger](github-issue-migration-ledger.md) with one row per former
  issue (archive section digests + evidence). Represent residual open work in
  `docs/issues/`, the intent map, and a short honest roadmap. Do **not** disable
  the GitHub Issues feature in this repair (owner choice). Do not re-create the
  deleted GitHub issues.
- **Rationale:** Permanent deletion without a truthful ledger loses provenance;
  reopening fixed items as backlog wastes agent and human attention.
- **Evidence:** Archive at `ec3979f`; API issue totalCount 0; code paths cited in
  the ledger; governed issue for #26.
- **Remaining work:** None required for migration hygiene. GitHub Issues stays
  enabled. Deletion journal reconstructed 2026-07-19 (most GraphQL node IDs
  unavailable after prior deletion; only #26 node id retained from an earlier
  worktree note).

### 2026-07-14 — Preserve implemented behavior in architecture

- **Context:** Historical plans, specs, and audits mixed shipped truth with execution scaffolding and outdated universal claims.
- **Decision:** Keep current statecharts, behavior coverage, test tiers, and security boundaries in architecture; remove the completed source documents.
- **Rationale:** Current code and tests are more precise than projected checklists and time-bound inventories.
- **Evidence:** Commits `d61dd42`, `c6af2ee`, `195c67d` through `b5c9fef`, security commits `9afd500`, `ac3577a`, `e9aac52`, `5c6f052`, `218b152`, `398ed04`, and `docs/architecture/00-overview.md`.
- **Remaining work:** None for the retired execution material.

### 2026-07-14 — Testing consolidation remains intentionally non-absolute

- **Context:** The retired audit design required zero inline `AsyncClient` setup and universal good/bad test pairs.
- **Decision:** Shared fixtures and behavior coverage remain the default, while specialized tests may keep local clients when setup timing or isolation requires them.
- **Rationale:** Current tests such as `tests/test_routes_pages.py`, `tests/test_security_auth_token.py`, and `tests/test_prefs_lock_timeout.py` need specialized setup and remain covered by CI.
- **Evidence:** Commits `d61dd42` and `c6af2ee`; current test files and `make ci AI=1` on 2026-07-14.
- **Remaining work:** None.

### 2026-07-14 — Retired documentation

- Old paths: `docs/archive/plans/2026-05-28-test-suite-audit-reorg.md`, `docs/archive/plans/2026-05-29-behavior-e2e-pilot.md`, `docs/archive/plans/2026-06-01-runtime-statecharts.md`, `docs/archive/specs/2026-05-28-test-suite-audit-reorg-design.md`, `docs/archive/specs/2026-06-01-runtime-statecharts-design.md`, `docs/research/2026-05-22-deep-code-review-security-scan.md`, `docs/research/2026-05-28-test-audit-matrix.md`, `docs/research/2026-06-02-multilingual-ocr-routing.md`, and `docs/specs/2026-05-29-projects-page.md`.
- Outcome: implemented or superseded, then deleted after migration-time adversarial review.
- Superseded by: `docs/architecture/00-overview.md`, `docs/architecture/module-map.md`, `docs/architecture/runtime-flows.md`, and `docs/context/intent-map.md`.
- Removal commit: this migration commit.
- Rationale kept: this decision log and the replacement architecture.
- Remaining work: deferred download and multilingual ideas remain in the intent map.

### 2026-07-19 — Retired: 2026-07-14 review-fixes plan

- **Old path:** `docs/plans/2026-07-14-review-fixes.md`
- **Outcome:** implemented (Phases A–F present in code, tests, and architecture)
- **Superseded by:** `docs/architecture/00-overview.md`,
  `docs/architecture/runtime-flows.md`, `docs/architecture/module-map.md`, and
  this decisions log
- **Removal commit:** (this cleanup commit)
- **Rationale kept:** durable design decisions in the 2026-07-14 review-fix
  entry below; residual deferred product work in `intent-map.md` (meta #395–#398)
- **Remaining work:** none for the plan itself

### 2026-07-14 — Review-fix decisions (multi-lens review + red team)

- **Context:** A multi-lens review plus a three-lens adversarial red team of the
  shipped app produced the now-retired 2026-07-14 review-fixes plan.
- **Decisions:**
  - Device vocabulary is normalized in `pdomain-ops` at the route and dispatcher
    boundaries (`canonical_execution_device` / `display_device_id`), not inside
    `resolve_effective_device`, so a stored `cuda:0` preference round-trips
    unchanged for display and normalizes to `local` for execution.
  - All mutating routes require the API token: the app-level upload and per-id
    job GET use `Depends(require_token)`, and `suite_token_middleware` guards
    every mutating `/api/suite/*` path by method+prefix rather than a hardcoded
    path allowlist.
  - The frontend sends the token via a shared `apiFetch` wrapper reading
    `localStorage`.
  - Upload limits are served by `GET /api/config` so the drop-zone copy cannot
    drift from the backend cap; zip extraction is capped by decompressed size
    and runs off the event loop.
  - Suite routes mount with the real `app_id` (`pdomain-ocr-simple-gui`) and a
    shared prefs adapter; the dispatcher uses `device_resolver` so Settings
    device changes apply on the next OCR stage.
- **Rationale:** The red team confirmed each gap against code; several were
  pre-existing (frontend token, suite mount, unauthenticated suite mutations)
  and would have silently broken or exposed a token-enabled deployment.
- **Evidence:** Architecture overview / runtime-flows / module-map (2026-07-19
  refresh); ocr-container-meta #395–#398 for residual deferred work;
  `pdomain-ops>=0.11.1` pin.
- **Remaining work:** deferred product items only (see intent-map), not plan
  execution.

### 2026-07-21 — Job cancellation: strip, not ship (ocr-container-meta#395)

- **Context:** The backend statechart modeled a `cancel` event and a
  `cancelled` state, but no route fired `cancel`, and the frontend `cancel()`
  was a no-op with no button.
- **Decision:** Remove the event and state from `job_lifecycle.py` and remove
  `cancel` from `useOcrJob`. Keep `"cancelled"` in the wire-level Literals
  (`ApiJobState`, `ProjectStatus.state`, `PageResult.state`) so the app can
  still receive the value from the shared `@pdomain/pdomain-ui` `JobState`.
- **Rationale:** The issue's bar was a cancel that interrupts the running
  dispatcher call. `LocalStageDispatcher` runs each OCR batch in a
  `ThreadPoolExecutor` work item, which `concurrent.futures` cannot cancel once
  it runs (ocr-container-meta#397). A chunk-boundary cancel would still finish
  the in-flight batch, and it would need new backend plumbing, race-safe status
  writes, and a new UI button. Removing a transition that never fired changes
  no runtime behavior.
- **Evidence:** `src/pdomain_ocr_simple_gui/statecharts/job_lifecycle.py`;
  `tests/test_job_lifecycle_statechart.py`
  (`test_cancel_is_not_a_valid_lifecycle_event`,
  `test_narrow_job_state_rejects_cancelled`); `frontend/src/api/useOcrJob.ts`;
  `docs/architecture/runtime-flows.md` "State machine reference".
- **Remaining work:** none. Re-adding cancel needs a new decision and, first,
  the upstream executor fix in ocr-container-meta#397.

### 2026-11-07 Retired: Deferred follow-ups plan (2026-07-21)

- Old path: docs/plans/2026-07-21-deferred-followups.md
- Outcome: implemented, and deleted as duplicate of the architecture
- Superseded by: docs/architecture/00-overview.md (API token, Settings >
  API Token), docs/architecture/module-map.md (`ApiTokenSettings.tsx`,
  `api/config.ts`), docs/architecture/runtime-flows.md (no `cancel` event)
- Removal commit: 95f1690bbf4f8d7500a7800589b13ad7946e7825
- Rationale kept: the strip decision above; the three shipped items in the
  architecture docs. Code: `frontend/src/components/ApiTokenSettings.tsx`,
  `frontend/src/api/config.ts` (the only `"/api/config"` fetch),
  `job_lifecycle.py` with no `cancel`. Tests:
  `frontend/src/components/__tests__/ApiTokenSettings.test.tsx`,
  `frontend/src/api/__tests__/config.test.ts`,
  `tests/test_job_lifecycle_statechart.py`. ocr-container-meta #395, #396,
  and #398 are closed (checked 2026-11-07).
- Remaining work: none

### 2026-11-07 Retired: Isolate suite launcher tabs from the opener (former GitHub #26)

- Old path: docs/issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md
- Outcome: implemented upstream. The locked `@pdomain/pdomain-ui` 0.12.1
  bundle calls `window.open(url, "_blank", "noopener,noreferrer")`; upstream
  commit `562938d` and `LauncherTile.test.tsx` pin it.
- Superseded by: docs/architecture/00-overview.md "Suite launcher tab
  isolation"
- Removal commit: 95f1690bbf4f8d7500a7800589b13ad7946e7825
- Rationale kept: docs/architecture/00-overview.md; former issue body
  recoverable with `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`
- Remaining work: none. The stale issue-#26 comment in
  `frontend/src/App.tsx` is removed; see the closeout tombstone below.

### 2026-11-07 Retired: Suite launcher opener isolation closeout plan and spec (2026-07-21)

- Old path: docs/plans/2026-07-21-suite-launcher-opener-closeout.md,
  docs/specs/2026-07-21-suite-launcher-opener-closeout-design.md
- Outcome: implemented, and deleted as duplicate of the architecture. Task 1
  (verify the locked package) and Task 3 (retire the issue) were done in
  95f1690; Task 2 deleted the stale issue-#26 comment from
  `frontend/src/App.tsx`.
- Superseded by: docs/architecture/00-overview.md "Suite launcher tab
  isolation"
- Removal commit: (fill after commit)
- Rationale kept: docs/architecture/00-overview.md; the issue #26 tombstone
  above. The locked `@pdomain/pdomain-ui` 0.12.1 bundle calls
  `window.open(url, "_blank", "noopener,noreferrer")`.
- Remaining work: none

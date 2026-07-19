---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-07-19
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

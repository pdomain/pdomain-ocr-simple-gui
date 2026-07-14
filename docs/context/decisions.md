---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-07-14
Kind: context
---

# Durable decisions and retirement tombstones

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** checking why documentation or product direction changed.
- **Search terms:** decisions, deviations, retirement, tombstones, security, tests.

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

---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-11-07
Kind: context
---

# Current state

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** starting repository work or checking current operational risks.
- **Search terms:** current state, shipped architecture, CI, risks, docgraph,
  issue migration.

## What matters now

All application milestones are shipped. The current product is the FastAPI and
React OCR application described in
[the architecture overview](../architecture/00-overview.md).
The supported install path is browser-based; the removed desktop extra and Qt
launch mode are not current product behavior.

v0.5.0 (2026-11-06) adds a PP-DocLayout-Plus-L layout pass before
`Page.reorganize_page`; see
[runtime flows](../architecture/runtime-flows.md). The 2026-07-21 deferred
follow-ups and former GitHub #26 are shipped and retired; tombstones are in
[decisions](decisions.md).

## In-flight work

One small closeout remains: removing the stale issue-#26 comment from
`frontend/src/App.tsx`
([closeout plan](../plans/2026-07-21-suite-launcher-opener-closeout.md)).

## Open product residue

The full list of remaining work is on the [roadmap](../roadmap.md). Deferred
and blocked bets are in the [intent map](intent-map.md).

## Verification and risks

`make ci AI=1` passed on 2026-07-14 after the review-fix merges; re-run after
substantive code changes. The download output mirror can remain stale after
per-page edits or reruns; the deferred redesign is tracked in
[the intent map](intent-map.md).

The dispatcher timeout bounds a hung OCR await but does not stop the underlying
executor thread, which can still race the shared predictor cache in pdomain-ops
([ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).
The repository has no GitHub workflows since `0bb3a4a` (2026-09-13, owner
request); `make ci AI=1` run locally is the gate, and releases run from
`scripts/release-common.sh`.

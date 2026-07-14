---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-07-14
Kind: context
---

# Current state

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** starting repository work or checking current operational risks.
- **Search terms:** current state, shipped architecture, CI, risks, docgraph.

## What matters now

All application milestones are shipped. The current product is the FastAPI and
React OCR application described in [the architecture overview](../architecture/00-overview.md).
The supported install path is browser-based; the removed desktop extra and Qt
launch mode are not current product behavior.

## In-flight work

The docgraph migration is complete and merged (commit `f99793d`). The
[2026-07-14 review-fixes plan](../plans/2026-07-14-review-fixes.md) is executing:
Phases A, B, E, and F have landed on `master`; the pdomain-ops device-vocabulary
release (Phase C) and the settings-to-execution wiring that depends on it
(Phase D) remain pending a human release gate.

## Verification and risks

`make ci AI=1` passed on 2026-07-14 after the review-fix merges. The download
output mirror can remain stale after per-page edits or reruns; the deferred
redesign is tracked in [the intent map](intent-map.md).

The dispatcher timeout added in Phase A bounds a hung OCR call but does not stop
the underlying executor thread, which can still race the shared predictor cache
in pdomain-ops (tracked in [ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).
No flaky test is currently recorded.

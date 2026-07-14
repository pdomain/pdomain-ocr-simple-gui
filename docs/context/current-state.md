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

The `docs/docgraph-migration` branch is reconciling documentation lifecycle,
retrieval, and suppression governance. No application feature is in flight.

## Verification and risks

The pre-migration `make ci AI=1` gate passed on 2026-07-14. The download output
mirror can remain stale after per-page edits or reruns; the deferred redesign is
tracked in [the intent map](intent-map.md). No flaky test is currently recorded.

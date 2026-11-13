---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-11-12
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

None. The five 2026-11-07 bugs and the browser-test races are on master
in the merge of `fix/e2e-flakes`. What remains is on the
[roadmap](../roadmap.md).

## Open product residue

The only remaining-work list is the [roadmap](../roadmap.md). It also names
work that belongs in another repo. Deferred and blocked bets, with the
reason they stay deferred, are in the [intent map](intent-map.md).

## Verification and risks

`make ci AI=1` passed on 2026-11-11 on `fix/e2e-flakes` before this merge,
with the GPU hidden. The word-overlay test waits until the count is at
least one. The upload flow polls until the job is terminal. The e2e
server starts uvicorn with `--port 0` and reads the bound port from its
log. That suite passed 20 of 20 runs under `-n auto`.
The smoke server starts with `--port 0` and reads the bound port from uvicorn's log.
The download output mirror can remain stale after
per-page edits or reruns; the deferred redesign is tracked in
[the intent map](intent-map.md).

The dispatcher timeout bounds a hung OCR await but does not stop the underlying
executor thread, which can still race the shared predictor cache in pdomain-ops
([ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).
The repository has no GitHub workflows since `0bb3a4a` (2026-09-13, owner
request); `make ci AI=1` run locally is the gate, and releases run from
`scripts/release-common.sh`.

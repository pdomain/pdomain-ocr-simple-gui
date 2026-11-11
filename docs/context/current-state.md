---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-11-10
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

The five bugs from the 2026-11-07 doc recheck are fixed on the local branch
`fix/doc-recheck-bugs`, which is not merged or pushed. Their issue files are
retired; the tombstone is in [decisions](decisions.md). Until the branch
merges, `master` still has all five bugs.

## Open product residue

The full list of remaining work is on the [roadmap](../roadmap.md). Deferred
and blocked bets are in the [intent map](intent-map.md).

## Verification and risks

`make ci AI=1` passed on 2026-11-10 on `fix/doc-recheck-bugs`, with the GPU
hidden and no `PLAYWRIGHT_BROWSERS_PATH` set; re-run after substantive code
changes. `test_word_overlays_render_from_sidecar` failed once under `-n auto`
on unchanged code and passed when run alone, because it reads the word count
once as soon as the canvas appears. The download output mirror can remain stale after
per-page edits or reruns; the deferred redesign is tracked in
[the intent map](intent-map.md).

The dispatcher timeout bounds a hung OCR await but does not stop the underlying
executor thread, which can still race the shared predictor cache in pdomain-ops
([ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).
The repository has no GitHub workflows since `0bb3a4a` (2026-09-13, owner
request); `make ci AI=1` run locally is the gate, and releases run from
`scripts/release-common.sh`.

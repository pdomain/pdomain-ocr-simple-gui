---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-07-19
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

The 2026-07-14 review-fixes execution plan is **implemented and retired** —
auth, suite mount, device resolution, concurrent-job caps, zip limits,
`apiFetch`, and related hardening live in architecture and code. The GitHub
issue migration repair (ledger + deletion journal) is on `master`.

## In-flight work

None for execution plans. Open product residue is deferred/blocked only.

## Open product residue

- Upstream launcher `noopener` —
  [governed issue #26](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md)
- Deferred items and meta links — [intent map](intent-map.md) and
  [roadmap](../roadmap.md)

## Verification and risks

`make ci AI=1` passed on 2026-07-14 after the review-fix merges; re-run after
substantive code changes. The download output mirror can remain stale after
per-page edits or reruns; the deferred redesign is tracked in
[the intent map](intent-map.md).

The dispatcher timeout bounds a hung OCR await but does not stop the underlying
executor thread, which can still race the shared predictor cache in pdomain-ops
([ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).
GitHub Actions CI may still fail e2e tests that expect Tesseract when only DocTR
is available in the runner image — treat as a known CI environment gap, not as
missing product work.

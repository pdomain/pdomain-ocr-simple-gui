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

## In-flight work

- **GitHub → docgraph issue migration (repair).** Issues were deleted on
  2026-07-17; the 2026-07-19 repair adds
  [the migration ledger](github-issue-migration-ledger.md),
  [the deletion journal](github-issue-deletion-journal.md), installs
  `docs/issues/` templates, reclassifies the roadmap, and keeps Issues
  **enabled** on GitHub by owner choice.
- **Review-fixes plan.** [2026-07-14 review-fixes](../plans/2026-07-14-review-fixes.md):
  Phases A, B, E, and F landed on `master`; the pdomain-ops device-vocabulary
  release (Phase C) and settings-to-execution wiring (Phase D) remain pending a
  human release gate where still applicable after later ops bumps.

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
No flaky test is currently recorded.

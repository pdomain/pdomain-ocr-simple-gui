---
Status: active
Owner: CT
Created: 2026-07-14
Last verified: 2026-11-13
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

## Released version

0.5.3 is the current release. Tag `v0.5.3` is commit `76067d7`. It is
published as a GitHub Release and on the live pdomain pip index. The 0.5.1,
0.5.2, and 0.5.3 tags were all cut on 2026-11-13.

## In-flight work

Branch `fix/release-review-exports` holds two unreleased fixes from the 0.5.3
release review. Neither is merged to `master` or released.

- **Downloads now carry saved edits and reruns.** Save and single-page rerun
  refresh the output mirror that the ZIP streams, along with both combined
  texts. See [runtime flows](../architecture/runtime-flows.md) and the
  [decision](decisions.md).
- **The release preflight now runs a real-OCR browser test.** `just ci-slow`
  runs `just ci` and then the real-OCR acceptance test. That test covers
  upload, OCR, edit, rerun, and ZIP export on the CPU. See
  [quality gates](../architecture/quality-gates.md).

Product work remains on the [roadmap](../roadmap.md).

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
Up to and including 0.5.3, the ZIP download can carry stale text after a
per-page edit or rerun. The branch above fixes that. Separate original and
edited downloads stay deferred in [the intent map](intent-map.md).

The release preflight needs Playwright chromium, the DocTR and layout model
weights, and the `tesseract` binary on the release machine. If any is missing,
the preflight fails. Plain `just ci` still skips the real-OCR test and prints
a note saying so. The smoke test still records a failed job as `xfail`.

The dispatcher timeout bounds a hung OCR await but does not stop the underlying
executor thread, which can still race the shared predictor cache in pdomain-ops
([ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).
The repository has no GitHub workflows since `0bb3a4a` (2026-09-13, owner
request); `AI=1 just ci` run locally is the gate, and releases run from
`scripts/release-common.sh`.

## Current gate and architecture verification

Commits `6889d3f` and `996bc7e` installed the Just task runner and removed its
Make shim. The current gate, locked frontend install, test isolation, and SPA
artifact boundaries are described in
[quality gates and distribution](../architecture/quality-gates.md). Both final
normal and AI CI runs passed on the removal bytes before `996bc7e`: 647 Python
tests, one smoke test, four packaging tests, 234 frontend tests, and 124 fast
browser tests. This is prior verification, not a claim that a release ran.

The current architecture reflects the 0.13.0 UI lock and the extracted settings,
preferences, and configuration-hook modules. The closed November handoffs have
been replaced by those durable references and their retirement receipts. The
[issue ledger](github-issue-migration-ledger.md) retains dated evidence; its
new reconciliation distinguishes remaining indented test banners from the
otherwise closed issue set.

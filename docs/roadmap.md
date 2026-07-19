---
Status: active
Owner: CT
Created: 2026-07-17
Last verified: 2026-07-19
Kind: plan
---

<!-- markdownlint-configure-file { "MD024": { "siblings_only": true } } -->

# pdomain-ocr-simple-gui Roadmap

## Agent Index

- **Kind:** plan
- **Status:** active
- **Read when:** deciding what to work on next in `pdomain-ocr-simple-gui`.
- **Search terms:** roadmap, backlog, now next later, open priorities, migration repair

## Provenance

This roadmap is the standing list of **still-open** work in
`pdomain-ocr-simple-gui`. On 2026-07-17 it incorrectly absorbed all 37 former
GitHub issues as unimplemented backlog. A 2026-07-19 reclassification against
code and git history showed **35 implemented**, **1 active/blocked** (#26), and
**1 residual style debt** (#13). Full rows live in
[the migration ledger](context/github-issue-migration-ledger.md).

Verbatim former issue bodies (Git history tombstone):

```bash
git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md
```

Cross-repo deferred items remain on
[ocr-container-meta](https://github.com/ConcaveTrillion/ocr-container-meta)
(#395–#398) and in [the intent map](context/intent-map.md).

## Goal

Keep a short, honest list of open priorities for the OCR GUI. Prefer
architecture, intent-map, and governed issues over a long false backlog.

## Architecture

`pdomain-ocr-simple-gui` is a local web server: FastAPI serves a React/Vite SPA
and drives OCR through `pdomain-ops` `LocalStageDispatcher` wrapping
`pdomain-book-tools`. It is the Phase 3 reference consumer for the dispatcher.

## Tech Stack

Python FastAPI + Pydantic; React + TypeScript on Vite; Vitest; `uv`, pytest,
Ruff, basedpyright.

## Global Constraints

Keep reusable OCR and dispatch logic upstream. Backend and frontend contracts
must stay aligned. Treat caller-controlled paths and IDs as untrusted. Run
`make ci AI=1` before committing.

## Now

- **[blocked]** Isolate suite launcher tabs (`noopener,noreferrer`) — former
  GitHub #26.
  Governed issue:
  [suite launcher opener isolation](issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md).
  Blocked on `@pdomain/pdomain-ui` release; then bump and verify the AppShell
  bundle. See [intent map](context/intent-map.md).

## Next

Product deferred work (not part of the deleted 37-issue set as open bugs):

- Job cancellation ship-or-strip —
  [ocr-container-meta#395](https://github.com/ConcaveTrillion/ocr-container-meta/issues/395)
- Config-fetch deduplication —
  [ocr-container-meta#396](https://github.com/ConcaveTrillion/ocr-container-meta/issues/396)
- API-token Settings field —
  [ocr-container-meta#398](https://github.com/ConcaveTrillion/ocr-container-meta/issues/398)
- Download truth separation (edited pages in export) — intent map
- Upstream predictor-cache lock (affects timeout cancellation safety) —
  [ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)

## Later

- **[style/low]** Remove residual `# ---` divider banners under `tests/e2e/`
  (former #13; earlier cleanup did not stick or was incomplete).
- Multilingual OCR profiles — intent map
- Richer project catalogue if the jobs dock proves insufficient — intent map
- Hosted deployment / Windows / macOS packaging — intent map (explicitly deferred)

## Done (former GitHub issues — do not re-open)

Implemented against current code (see ledger for digests and commits):

| Cluster | Issues |
| --- | --- |
| Rerun / image path / async | #1, #2, #10 |
| FE/BE contracts + `response_model` + 202 | #3, #4, #5, #11, #12 |
| Language default, StaticFiles factory | #6, #9 |
| CI frontend-test + pre-commit | #7, #8 |
| Style banners (partial; residual in Later) | #13 attempt `fd83a28` |
| Lint deviations catalog | #14 |
| pdomain-ui package alignment | #15 |
| Security: traversal, allowlist, auth, caps | #16, #17, #18, #19, #23 |
| Vite/esbuild + lock integrity | #20, #21, #22 |
| Fonts self-host; no file:// open | #24, #25 |
| Ops pin; Actions/uv pins | #27, #28 |
| Suite/prefs/listing logging | #29–#34 |
| Fake dispatcher warning; e2e prefs guard; fake isinstance | #36, #37, #38 |

## Ideas

_No untriaged requests._

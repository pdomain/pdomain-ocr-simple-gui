---
Status: active
Owner: CT
Created: 2026-07-17
Last verified: 2026-11-07
Kind: plan
---

# pdomain-ocr-simple-gui Roadmap

## Agent Index

- **Kind:** plan
- **Status:** active
- **Read when:** deciding what to work on next in `pdomain-ocr-simple-gui`.
- **Search terms:** roadmap, remaining work, backlog, open priorities, needs
  owner decision

## Goal

List the work that is still open, one line per item, with the file that
tracks it. Shipped behavior lives in the architecture docs, not here.

## Architecture

`pdomain-ocr-simple-gui` is a local web server: FastAPI serves a React/Vite SPA
and drives OCR through `pdomain-ops` `LocalStageDispatcher` wrapping
`pdomain-book-tools`, followed by a PP-DocLayout-Plus-L layout pass. Current
truth: [overview](architecture/00-overview.md),
[module map](architecture/module-map.md), and
[runtime flows](architecture/runtime-flows.md).

## Tech Stack

Python FastAPI + Pydantic; React + TypeScript on Vite; Vitest; `uv`, pytest,
Ruff, basedpyright.

## Global Constraints

Keep reusable OCR and dispatch logic upstream. Backend and frontend contracts
must stay aligned. Treat caller-controlled paths and IDs as untrusted. Run
`make ci AI=1` before committing.

## Remaining work

- Separate original and modified downloads so edited pages reach the export.
  [docs/specs/2026-05-29-download-model.md](specs/2026-05-29-download-model.md)
- Lock the shared predictor cache upstream so a timed-out batch cannot race
  the next one. [ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)
- Remove the residual `# ---` divider banners under `tests/e2e/` (former #13).
  [docs/context/github-issue-migration-ledger.md](context/github-issue-migration-ledger.md)
- Close or keep the `dep-refresh` auto-land issue now that the workflow is
  deleted. Needs an owner decision.
  [docs/issues/2026-08-08-dep-refresh-cannot-auto-land.md](issues/2026-08-08-dep-refresh-cannot-auto-land.md)
- Deferred, not scheduled: multilingual OCR profiles, a richer project
  catalogue, hosted deployment, and Windows or macOS packaging.
  [docs/context/intent-map.md](context/intent-map.md)

## Shipped

- Former GitHub issues #1–#34 and #36–#38, except #13, are implemented; the
  [migration ledger](context/github-issue-migration-ledger.md) has one row per
  issue with evidence. Do not reopen them.
- Retired plans and issues, with their evidence, are tombstoned in
  [decisions](context/decisions.md).

---
Status: active
Owner: CT
Created: 2026-05-19
Last verified: 2026-07-19
Kind: process
---

# docs/

How documentation is organized in this repo.

| Folder | Purpose | Use when |
| --- | --- | --- |
| `architecture/` | Durable reference — how the system works today. | Capturing current shape (modules, data flow, contracts, current-state diagrams). |
| `archive/` | Cold storage. Mirrors the nine active folders. | A doc is no longer in force (shipped, superseded, abandoned). |
| `context/` | Operational digest, intent, decisions, migration ledgers. | Starting work or tracing former GitHub issues. |
| `decisions/` | ADRs — dated, append-only "we chose X because Y." | Recording a specific design choice with context, alternatives, consequences. |
| `issues/` | Governed evidence-bearing issue reports. | Durable bugs/investigations (not chat summaries). |
| `plans/` | Active execution — what order to make a spec real. | Sequencing work for an approved spec. |
| `process/` | Cross-cutting workflow conventions (verification rules, merge strategy, release process). | Capturing how the team works, not what the system does. |
| `research/` | Investigation in progress. Messy by design. | Exploring before committing to a design. |
| `runbooks/` | Operational reference — something is broken or being operated. | An on-call or ops task needs a recipe. |
| `specs/` | Aspirational, pre-implementation design. | Describing what to build, before code. |
| `templates/` | Issue, spec, plan, ADR boilerplate. | Adding a starter template for a new doc type. |
| `usage/` | Downstream reference — how to consume this app/tool/library. | A user or integrator needs to know how to use it. |

Empty folders are intentional and tracked via `.gitkeep`.

## Current document index

- Architecture: [overview](architecture/00-overview.md), [module map](architecture/module-map.md), and [runtime flows](architecture/runtime-flows.md).
- Context: [current state](context/current-state.md), [intent map](context/intent-map.md), [decisions](context/decisions.md), and [GitHub issue migration ledger](context/github-issue-migration-ledger.md).
- Issues: [index](issues/README.md) and open [suite launcher opener isolation](issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md).
- Roadmap: [open priorities](roadmap.md) (reclassified 2026-07-19).
- Decisions: [jobs location](decisions/2026-06-04-jobs-location-setting.md) and [preserved runtime boundaries](decisions/2026-07-13-preserved-runtime-boundaries.md).
- Process: [lint deviations](process/lint-deviations.md), [local development](process/local-dev.md), and [writing style](process/writing-style.md).
- Runbooks: [installation](runbooks/install.md), [CUDA setup](runbooks/cuda-setup.md), and [release](runbooks/release.md).
- Active and deferred contracts: [download model](specs/2026-05-29-download-model.md) and the [behavior-spec index](specs/behavior/README.md), including [coverage](specs/behavior/coverage.md), [flows](specs/behavior/flows.md), [app shell](specs/behavior/screen-app-shell.md), [home](specs/behavior/screen-home.md), [page view](specs/behavior/screen-page-view.md), and [results](specs/behavior/screen-results.md).

Former repository GitHub issues (#1–#34, #36–#38) were deleted; status and
evidence live in the [migration ledger](context/github-issue-migration-ledger.md)
and [governed issues](issues/README.md), not the GitHub tracker. Verbatim
archive text: `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`.
This layout is workspace-standard; see
`/workspaces/ocr-container/docs/README.md` for the master when that tree exists.

---
Status: active
Owner: CT
Created: 2026-05-19
Last verified: 2026-11-13
Kind: process
---

# docs/

How documentation is organized in this repo.

| Folder | Purpose | Use when |
| --- | --- | --- |
| `architecture/` | Durable reference — how the system works today. | Capturing current shape (modules, data flow, contracts, current-state diagrams). |
| `context/` | Operational digest, intent, decisions, migration ledgers. | Starting work or tracing former GitHub issues. |
| `decisions/` | ADRs — dated, append-only "we chose X because Y." | Recording a specific design choice with context, alternatives, consequences. |
| `issues/` | Governed evidence-bearing issue reports. | Durable bugs/investigations (not chat summaries). |
| `plans/` | Active execution — what order to make a spec real. | Sequencing work for an approved spec. |
| `process/` | Cross-cutting workflow conventions (verification rules, merge strategy, release process). | Capturing how the team works, not what the system does. |
| `research/` | Investigation in progress. Messy by design. | Exploring before committing to a design. |
| `runbooks/` | Operational reference — something is broken or being operated. | An on-call or ops task needs a recipe. |
| `specs/` | A design that is not built yet, plus the living behavior records the coverage gate reads. | The download-model stub, or a screen contract in `specs/behavior/`. |
| `templates/` | Issue, spec, plan, ADR boilerplate. Empty today; the issue template is `issues/TEMPLATE.md`. | Adding a starter template for a new doc type. |
| `usage/` | Downstream reference — how to consume this app/tool/library. | A user or integrator needs to know how to use it. |

`plans/`, `research/`, `templates/`, and `usage/` are empty on purpose and
kept with `.gitkeep`. There is no `docs/archive/` folder. A retired doc is
tombstoned in [decisions](context/decisions.md), and the old file stays in
git history. `roadmap.md` sits at the top of `docs/` and is the only list
of remaining work.

## Current document index

- Architecture: [overview](architecture/00-overview.md), [module map](architecture/module-map.md), and [runtime flows](architecture/runtime-flows.md), and [quality gates and distribution](architecture/quality-gates.md).
- Context: [current state](context/current-state.md), [intent map](context/intent-map.md), [decisions](context/decisions.md), [GitHub issue migration ledger](context/github-issue-migration-ledger.md), and [deletion journal](context/github-issue-deletion-journal.md).
- Issues: [index](issues/README.md) and open [dep-refresh auto-land](issues/2026-08-08-dep-refresh-cannot-auto-land.md).
- Roadmap: [remaining work, including work for other repos](roadmap.md).
- Plans: none active.
- Decisions: [jobs location](decisions/2026-06-04-jobs-location-setting.md) and [preserved runtime boundaries](decisions/2026-07-13-preserved-runtime-boundaries.md).
- Process: [lint deviations](process/lint-deviations.md), [local development](process/local-dev.md), and [writing style](process/writing-style.md).
- Runbooks: [installation](runbooks/install.md), [CUDA setup](runbooks/cuda-setup.md), and [release](runbooks/release.md).
- Unbuilt design: [download model](specs/2026-05-29-download-model.md).
- Living screen contracts, read by `scripts/behavior_coverage.py`: [behavior-spec index](specs/behavior/README.md), [coverage](specs/behavior/coverage.md), [flows](specs/behavior/flows.md), [app shell](specs/behavior/screen-app-shell.md), [home](specs/behavior/screen-home.md), [page view](specs/behavior/screen-page-view.md), and [results](specs/behavior/screen-results.md).

Former repository GitHub issues (#1–#34, #36–#38) were deleted; status and
evidence live in the [migration ledger](context/github-issue-migration-ledger.md)
and [governed issues](issues/README.md), not the GitHub tracker. Verbatim
archive text: `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`.
This file is the layout for this repo. `ConcaveTrillion/ocr-container-meta`
used to hold a shared template. That repo is no longer used. Its last push
was 2026-06-06.

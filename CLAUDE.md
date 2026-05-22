# CLAUDE — pd-ocr-simple-gui

Minimal drag-and-drop OCR web app. User drops a folder of scanned images,
picks an engine, runs OCR, gets `.txt` files. Phase 3 reference consumer
that validates `pd-ocr-ops`' `LocalStageDispatcher` and the
`register_default_stages()` helper before `pd-prep-for-pgdp` migrates.

**Architecture:** see workspace-level docs for historical plans/specs.
Spec: workspace `docs/specs/2026-05-17-pd-ocr-simple-gui-design.md`.
Plans: workspace `docs/archive/plans/2026-05-17-pd-ocr-simple-gui.md` (complete).

## Quick orientation

Architecture doc: `docs/architecture/00-overview.md`.

- **Backend:** FastAPI + uvicorn, Python 3.11+. `src/pd_ocr_simple_gui/`.
- **Frontend:** React + Vite + TS + `@concavetrillion/pd-ui`. `frontend/` (shipped M3+).
- **OCR pipeline:** `pd-ocr-ops` `LocalStageDispatcher` +
  `register_default_stages()`. `pd-book-tools` supplies the runners.
- **Suite integration:** `pd-ocr-ops.suite.register_self()` wires the
  app into the installed.toml launcher registry.
- **Port:** 8004 (default).

## Commands

| Target | Does |
|--------|------|
| `make setup AI=1` | `uv sync` + pre-commit hooks |
| `make test AI=1` | pytest — unit + integration, excludes `slow`/`e2e` |
| `make smoke AI=1` | httpx end-to-end smoke (xfails without model weights) |
| `make e2e-browser AI=1` | Playwright browser e2e (requires chromium) |
| `make frontend-test AI=1` | vitest frontend component tests |
| `make frontend-build AI=1` | Vite build → `src/pd_ocr_simple_gui/static/` |
| `make lint AI=1` / `make format AI=1` | ruff check / format |
| `make typecheck AI=1` | basedpyright |
| `make pre-commit-check AI=1` | all pre-commit hooks on every tracked file |
| `make ci AI=1` | full gate: setup + lint + typecheck + build + test + smoke + frontend-test |
| `make ci-full AI=1` | `make ci` + `e2e-browser` (Playwright) |
| `make run` | launch on :8004 |

`AI=1` captures verbose output to `.ci-ai.log`; stdout shows ✅ on pass
or filtered failure sections on error.

## Rules

- Always run `make ci AI=1` before committing.
- Make targets first; fall back to `uv run …` only when no target exists.
- Never `python -m pytest`. Always `uv run pytest` or `make test`.
- **TDD-first** for all feature work: test first, then implementation.
- Stub-shaped work (route stubs, protocol definitions) is exempt.

## Memory path

Agent memory: `/workspaces/ocr-container/.claude/agent-memory/pd-ocr-simple-gui/`

Always write to the **absolute path** above. Never use a relative
`.claude/agent-memory/...` path — cwd at write time may not be the
workspace root.

## Current status

All milestones shipped (M0–M8 + verification milestone). Open work:

- **#14** — `docs/conventions/lint-deviations.md` chore (`kind:chore`, unblocked).

## GH issues

Cross-cut tasks tracked in `ConcaveTrillion/ocr-container-meta`.
Milestone: `spec: 2026-05-17-pd-ocr-simple-gui (#211)` — all tasks closed.

Before starting: `gh issue view <N> --repo ConcaveTrillion/ocr-container-meta`
After completing: `gh issue close <N> --repo ConcaveTrillion/ocr-container-meta`

## Sibling repos

In `/workspaces/ocr-container/` (when present):

- `pd-book-tools/` — OCR, layout, image primitives. Hard dependency.
- `pd-ocr-ops/` — suite plumbing, GPU dispatch, prefs. Hard dependency.
- `pd-prep-for-pgdp/` — sister FastAPI app; mirrors this repo's patterns.

## Out of scope

- Editing files outside `/workspaces/ocr-container/pd-ocr-simple-gui/`.
- Touching shared OCR/layout logic (do that in `pd-book-tools`).
- Releases, force-push, or wheel publish without explicit approval.

## docs/ folder

This repo follows the workspace docs/ template — see [`docs/README.md`](docs/README.md). Active
folders: `architecture/`, `decisions/`, `plans/`, `process/`, `research/`,
`runbooks/`, `specs/`, `templates/`, `usage/`, plus parallel `archive/`
subfolders.

**Superpowers redirect.** When a superpowers skill (e.g. `brainstorming`,
`writing-plans`) instructs you to save to `docs/superpowers/specs/<file>.md`
or `docs/superpowers/plans/<file>.md`, save to `docs/specs/<file>.md` or
`docs/plans/<file>.md` instead. There is no `docs/superpowers/` subdirectory
in this repo.

<!-- workspace-process:start -->

## Before coding

These steps are workspace defaults for any coding task. **User-level settings
override them** — a user's own `~/.claude/CLAUDE.md`, `settings.json`, or a
direct instruction in the conversation takes precedence and may waive or
change any step below.

### Working principles

- **Use skills.** Invoke the relevant superpowers skill before starting —
  process skills first (`brainstorming`, `systematic-debugging`,
  `writing-plans`, `test-driven-development`), then implementation skills.
  If a skill applies, using it is not optional.
- **Delegate by default.** Dispatch subagents for non-trivial work: per-repo
  agents for repo changes, `Explore` for code searches. This keeps large tool
  output out of the parent context.
- **Parallelize.** Run independent tasks as concurrent subagents — multiple
  agent calls in a single message. Set `model: sonnet` on implementers and
  reviewers.

### Steps

1. **Check the working tree.** `git status --short`. Surface or resolve stray
   uncommitted work before starting — don't build on it.
2. **Read repo guidance.** This repo's `CLAUDE.md` and `CONVENTIONS.md` for
   repo-specific rules.
3. **Consult `docs/` for authoritative context** (whichever folders exist):
   `plans/` (the work plan), `specs/` (design specs — follow any `Spec:`
   pointer from the issue), `research/` (prior investigations), `decisions/`
   (ADRs / constraints), `architecture/` (shipped design).
4. **Check live issue status.** `gh issue view <N> --repo <owner/repo>` —
   confirm it isn't already closed; note its milestone.
5. **Check for in-flight work.** Open PRs and existing branches touching the
   same area, to avoid colliding with work-in-progress.
6. **Consult agent memory.** `.claude/agent-memory/<repo>/feedback_*.md` for
   corrections not yet promoted to `CONVENTIONS.md`.
7. **Locate code with `Explore` first.** Use an `Explore` subagent to find
   relevant files before broad `Read`/grep.
8. **Isolate in a worktree.** Never work directly in the interactive checkout
   at `/workspaces/ocr-container/<repo>/`. Use the `using-git-worktrees` skill
   to set up an isolated worktree. When delegating to a full-power
   implementation agent, pass `isolation: "worktree"` on the `Agent` call
   (skip for `-docs` agents and the `driver` agent). When an agent returns a
   worktree path + branch, use the `finishing-a-development-branch` skill to
   decide how to integrate.
9. **TDD.** Write the failing test first where the plan calls for it.
10. **Verify before committing.** Focused verification plus `make ci`.
11. **Commit locally; do not push** without explicit say-so.

<!-- workspace-process:end -->

---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-11-07
Kind: process
---

# CLAUDE — pdomain-ocr-simple-gui

Minimal drag-and-drop OCR web app. User drops a folder of scanned images,
picks an engine, runs OCR, gets `.txt` files. Phase 3 reference consumer
that validates `pdomain-ops`' `LocalStageDispatcher` and the
`register_default_stages()` helper before `pdomain-prep-for-pgdp` migrates.

**Architecture:** `docs/architecture/00-overview.md` (primary).

## Quick orientation

Architecture doc: `docs/architecture/00-overview.md`.

- **Backend:** FastAPI + uvicorn, Python 3.11+. `src/pdomain_ocr_simple_gui/`.
- **Frontend:** React + Vite + TS + `@pdomain/pdomain-ui`. Source lives in
  `frontend/`; the packaged build lives in `src/pdomain_ocr_simple_gui/frontend/`.
- **OCR pipeline:** `pdomain-ops` `LocalStageDispatcher` +
  `register_default_stages()`. `pdomain-book-tools` supplies the runners.
- **Suite integration:** `pdomain_ops.suite.bootstrap_spa()`, called from
  `__main__.py`, runs `register_self()` to wire the app into the
  installed.toml launcher registry.
- **Port:** 8004 (default; the next free port if 8004 is taken).

## Commands

| Target | Does |
|--------|------|
| `make setup AI=1` | `uv sync` + pre-commit hooks + Playwright chromium |
| `make test AI=1` | pytest — unit + integration, excludes `slow`/`e2e` |
| `make smoke AI=1` | httpx end-to-end smoke (xfails without model weights) |
| `make e2e-browser AI=1` | Playwright browser e2e (requires chromium) |
| `make frontend-test AI=1` | vitest frontend component tests |
| `make frontend-build AI=1` | Vite build → `src/pdomain_ocr_simple_gui/frontend/` |
| `make lint AI=1` / `make format AI=1` | ruff check / format |
| `make typecheck AI=1` | basedpyright |
| `make pre-commit-check AI=1` | all pre-commit hooks on every tracked file |
| `make update-hooks` | bump pre-commit hooks to their latest releases, frozen to commit SHAs (`pre-commit autoupdate --freeze`) |
| `make ci AI=1` | full gate: setup + pre-commit + lint + typecheck + frontend-build + test + behavior-coverage + smoke + packaging-test + frontend format/lint/test/knip + e2e-fast |
| `make ci-full AI=1` | `make ci` + `e2e-browser` (Playwright) |
| `make run` | launch on :8004 |
| `make local-setup` | clone any missing sibling pd-* repos |
| `make local-dev` | switch to local-dev mode (Python + npm siblings editable + marker) |
| `make local-check` | print local-dev mode + per-sibling resolution |
| `make local-upgrade-deps` | upgrade deps then restore editables (local-mode only) |
| `make local-setup-py` | re-apply editable Python siblings (idempotent; defensive against `uv sync`) |
| `make local-frontend-install` | `pnpm install` + restore `pnpm link` overlays for npm siblings |
| `make local-frontend-build` | Vite build using locally-linked npm siblings |
| `make local-frontend-test` | vitest using locally-linked npm siblings |
| `make local-frontend-dev` | Vite dev server using locally-linked npm siblings |
| `make local-run` | run the SPA against local-dev workspace (local-mode only; uses `local-frontend-build` — local-link sticky) |
| `make update-pdomain-deps` | bump pd-* sibling deps to registry latest; leaves diff for review |

`frontend-*` and `run` are registry-resolved (canonical CI path).
`local-frontend-*` and `local-run` are local-link-resolved (developer
workflow); see [`docs/process/local-dev.md`](docs/process/local-dev.md)
for why the two families are kept separate.

`AI=1` captures verbose output to `.ci-ai.log`; stdout shows ✅ on pass
or filtered failure sections on error.

## Rules

- Always run `make ci AI=1` before committing.
- Make targets first; fall back to `uv run …` only when no target exists.
- Never `python -m pytest`. Always `uv run pytest` or `make test`.
- **TDD-first** for all feature work: test first, then implementation.
- Stub-shaped work (route stubs, protocol definitions) is exempt.

## Current status

All milestones shipped (M0–M8 + verification milestone). Remaining
repo-scoped work is listed in [`docs/roadmap.md`](docs/roadmap.md). Lint deviations are catalogued in
`docs/process/lint-deviations.md` with inline rationale at each
suppression point.

## Issues

Work is tracked as Markdown files in `docs/issues/`. The open list is
[`docs/issues/README.md`](docs/issues/README.md). Items that cut across
several `pdomain-*` repos are filed in
`/mnt/work/projects/pdomain/pdomain-book-tools/docs/issues/`. GitHub Issues is
still enabled on `pdomain/pdomain-ocr-simple-gui`, but work is not tracked
there. `ConcaveTrillion/ocr-container-meta` was the tracker for the old
`/workspaces/ocr-container` workspace. Its last push was 2026-06-06, and it is
no longer used.

## Sibling repos

In `/mnt/work/projects/pdomain/`:

- `pdomain-book-tools/` — OCR, layout, image primitives. Hard dependency.
- `pdomain-ops/` — suite plumbing, GPU dispatch, prefs. Hard dependency.
- `pdomain-prep-for-pgdp/` — sister FastAPI app; mirrors this repo's patterns.

## Out of scope

- Editing files outside `/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/`.
- Touching shared OCR/layout logic (do that in `pdomain-book-tools`).
- Releases, force-push, or wheel publish without explicit approval.

## docs/ folder

This repo follows the workspace docs/ template — see [`docs/README.md`](docs/README.md). Active
folders: `architecture/`, `context/`, `decisions/`, `issues/`, `plans/`,
`process/`, `research/`, `runbooks/`, `specs/`, `templates/`, `usage/`, plus
`archive/` subfolders for the nine folders other than `context/` and `issues/`.

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
- **Write clearly.** Follow `docs/process/writing-style.md` for direct user
  updates, handoffs, final summaries, docs, reports, issue text, PR text, and
  user-facing copy. Keep agent communication short, clear, and easy to scan.
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
4. **Check the issue file.** Read the matching file in `docs/issues/` and
   confirm its Resolution is still Open.
5. **Check for in-flight work.** Open PRs and existing branches touching the
   same area, to avoid colliding with work-in-progress.
6. **Locate code with `Explore` first.** Use an `Explore` subagent to find
   relevant files before broad `Read`/grep.
7. **Isolate in a worktree.** Never work directly in the interactive checkout
   at `/mnt/work/projects/pdomain/<repo>/`. Use the `using-git-worktrees` skill
   to set up an isolated worktree. When delegating to a full-power
   implementation agent, pass `isolation: "worktree"` on the `Agent` call
   (skip for `-docs` agents and the `driver` agent). When an agent returns a
   worktree path + branch, use the `finishing-a-development-branch` skill to
   decide how to integrate.
8. **TDD.** Write the failing test first where the plan calls for it.
9. **Verify before committing.** Focused verification plus `make ci`.
10. **Commit locally; do not push** without explicit say-so.

<!-- workspace-process:end -->

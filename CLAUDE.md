# CLAUDE — pd-ocr-simple-gui

Minimal drag-and-drop OCR web app. User drops a folder of scanned images,
picks an engine, runs OCR, gets `.txt` files. Phase 3 reference consumer
that validates `pd-ocr-ops`' `LocalStageDispatcher` and the
`register_default_stages()` helper before `pd-prep-for-pgdp` migrates.

**Architecture:** `docs/` (plan/spec under workspace `docs/superpowers/`).
Spec: `docs/superpowers/specs/2026-05-17-pd-ocr-simple-gui-design.md`.

## Quick orientation

- **Backend:** FastAPI + uvicorn, Python 3.11+. `src/pd_ocr_simple_gui/`.
- **Frontend:** React + Vite + TS + `@concavetrillion/pd-ui`. `frontend/`
  (M3, not yet scaffolded).
- **OCR pipeline:** `pd-ocr-ops` `LocalStageDispatcher` +
  `register_default_stages()`. `pd-book-tools` supplies the runners.
- **Suite integration:** `pd-ocr-ops.suite.register_self()` wires the
  app into the installed.toml launcher registry.
- **Port:** 8004 (default).

## Commands

```sh
make ci AI=1        # full CI — always run before committing
make test           # uv run pytest tests/ -v
make run            # launch on :8004
```

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

## GH issues

Cross-cut tasks tracked in `ConcaveTrillion/ocr-container-meta`.
Milestone: `spec: 2026-05-17-pd-ocr-simple-gui (#211)`.

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

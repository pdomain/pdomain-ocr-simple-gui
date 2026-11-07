---
Status: active
Owner: CT
Created: 2026-05-27
Last verified: 2026-11-07
Kind: process
---

# Local-dev workflow — pdomain-ocr-simple-gui

This repo follows the workspace local-dev pattern (spec #362), described in
`docs/process/local-dev.md` in the private `ConcaveTrillion/ocr-container-meta`
repo, for iterating against sibling pd-* repos as editable installs. This page documents the **repo-specific** detail of how the
local-dev path is kept separate from the registry path.

## Two parallel Make-target families

| Family | Targets | Resolves siblings from |
|--------|---------|------------------------|
| Registry (canonical, `make ci` and releases) | `frontend-install`, `frontend-build`, `frontend-test`, `frontend-dev`, `run`, `ci` | the published pdomain-index-pip / pdomain-index-npm registries |
| Local-link (developer only) | `local-frontend-install`, `local-frontend-build`, `local-frontend-test`, `local-frontend-dev`, `local-setup-py`, `local-run` | the sibling checkouts beside the canonical repo, here `/mnt/work/projects/pdomain/<sibling>/` |

The scripts find siblings in the parent directory of the canonical checkout, the
one that owns `.git`, so a worktree elsewhere still resolves
`/mnt/work/projects/pdomain/<sibling>/`. Siblings are `pdomain-book-tools` and
`pdomain-ops` for Python and `pdomain-ui` for npm.

The two families exist because `pnpm install` and `uv sync` each
discard any local overlay (the `pnpm link` for npm siblings, the
`uv pip install -e` for Python siblings) and restore registry
resolution. If a single target family tried to be "marker-aware" it
would either:

- silently re-link inside `make ci` / a release build (wrong — both must
  reproduce a registry-resolved build), or
- silently fall back to registry inside developer flows (wrong — the
  whole point of local-dev is to iterate against local sibling changes
  that haven't been released yet).

So they're kept separate. **Use `local-*` while iterating; `make ci`
and releases use the registry path unchanged.**

## Entry points

- `make local-dev` — initial switch to local mode (Python + npm
  siblings editable, marker written).
- `make local-run` — the canonical "run the app against my local
  siblings" entry point. Internally:
  1. `local-setup-py` — re-applies editable Python siblings (defensive
     against any prior `uv sync`).
  2. `local-frontend-build` → `local-frontend-install` — pnpm install
     then `pnpm link` each npm sibling.
  3. Launches `pdomain-ocr-simple-gui` directly with
     `uv run --no-sync --project <canonical repo>` (not via `make run`,
     which would re-enter the registry path). `--no-sync` is required: a
     plain `uv run` re-syncs and drops the editable siblings.

  It exits with an error unless `make local-dev` has written the marker
  `.pdomain-local-mode` in the canonical repo's virtual environment.
- `make local-check` — verify resolution (each sibling should report
  "editable from …" or "linked → …", not "registry version …").

## Why `local-run` does not call `make run`

`make run` depends on `frontend-build` → `frontend-install`, both of
which are the registry path. If `local-run` delegated there, it would
overwrite the `pnpm link` overlay every time. `local-run.sh`
reproduces the launch step inline
(`uv run --no-sync --project "$CANONICAL_REPO_ROOT" pdomain-ocr-simple-gui`)
to keep the local overlay intact.

## Never commit local-link overlay state

`pnpm link <sibling>` mutates **both** `frontend/pnpm-workspace.yaml`
(adds an `overrides: { '@pdomain/<sibling>': link:... }` entry,
collapses `$react` aliases to literal versions) **and**
`frontend/pnpm-lock.yaml` (changes the resolution from a registry
specifier to `link:`). These mutations are intentional at runtime and
make the local checkout resolve correctly — but they must NEVER be
committed.

Before committing any work in local-dev mode:

```bash
git checkout -- frontend/pnpm-workspace.yaml frontend/pnpm-lock.yaml
```

`make local-frontend-install` is safe to re-run afterward (it
re-applies the link from the script's `NPM_SIBLINGS` array — the git
overlay state isn't its source of truth).

## Adding a new sibling

Update every script that lists siblings:

- `scripts/local-dev.sh` — `PY_SIBLINGS` / `NPM_SIBLINGS` arrays.
- `scripts/local-setup-py.sh` — `PY_SIBLINGS` array.
- `scripts/local-frontend-install.sh` — `NPM_SIBLINGS` array.
- `scripts/local-check.sh` — `PY_SIBLINGS` / `NPM_SIBLINGS` arrays.
- `scripts/local-setup.sh` — `SIBLINGS` array, the repos it clones.
- `scripts/update-pdomain-deps.sh` — `PY_SIBLINGS` / `NPM_SIBLINGS` arrays.
- `scripts/ci-against-master.sh` — `PY_SIBLINGS` array, which must also
  match `[tool.uv.sources]`.

Keep the arrays in sync across these scripts; they intentionally
don't share a source-of-truth because each script must stand alone
under `set -euo pipefail`.

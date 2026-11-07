---
Status: active
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-07
Kind: issue
Level: I2
---

# Two setup defaults still point at the old devcontainer and the old GitHub owner

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I2
- **Last verified:** 2026-11-07
- **Resolution:** Open
- **Severity:** Low — `make ci` fails its browser tests and `make local-setup`
  clones from the wrong owner unless the developer knows the workaround.
- **Affected version:** `master` at `c029c52`
- **Read when:** running `make ci` or `make local-setup` on a new machine, or
  cleaning up leftovers from the devcontainer setup.
- **Search terms:** PLAYWRIGHT_BROWSERS_PATH, /cache/shared-ai/ms-playwright,
  local-setup.sh, gh repo clone, ConcaveTrillion, pdomain org, devcontainer.
- **Relates to:** [local development](../process/local-dev.md),
  [intent map](../context/intent-map.md)

## Summary

Two defaults still assume the old setup. The `Makefile` looks for Playwright
browsers in a devcontainer path that does not exist on the owner's desktop.
`scripts/local-setup.sh` clones sibling repos from the `ConcaveTrillion` GitHub
account, but the repos now live under the `pdomain` organization.

## Impact

- `make ci` runs the browser e2e tests, and every one of them errors unless
  `PLAYWRIGHT_BROWSERS_PATH` is set by hand.
- `make local-setup` fails for any missing sibling, because
  `ConcaveTrillion/<sibling>` does not exist. For example,
  `gh repo view ConcaveTrillion/pdomain-ops` returns "Could not resolve to a
  Repository".

## Environment / versions

```text
master c029c52, omarchy-main (Arch Linux), repo at
/mnt/work/projects/pdomain/pdomain-ocr-simple-gui
Playwright browsers installed at ~/.cache/ms-playwright
```

## Evidence

### 1. The Makefile defaults to a devcontainer path

Four recipes in the `Makefile` use
`PLAYWRIGHT_BROWSERS_PATH=$${PLAYWRIGHT_BROWSERS_PATH:-/cache/shared-ai/ms-playwright}`.
That path does not exist here. On 2026-11-07, `make ci AI=1` passed only with
`PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright` set. The run also set
`UV_OFFLINE=1` so `uv` would not reach the package index; that is unrelated to
this bug.

### 2. The setup script clones from the old owner

`scripts/local-setup.sh` runs
`gh repo clone "ConcaveTrillion/$sibling" "$WORKSPACE_ROOT/$sibling"`.
`gh repo view pdomain/pdomain-ops` resolves, and
`gh repo view ConcaveTrillion/pdomain-ops` does not.

## Root-cause hypotheses

1. **(Confirmed) Both defaults were written for the devcontainer and the old
   GitHub owner, and were not updated when the repos moved.**

## Defects to fix

1. **Playwright path:** drop the devcontainer default, so Playwright uses its
   own default cache (`~/.cache/ms-playwright` on Linux). (Primary)
2. **Clone owner:** clone siblings from `pdomain/<sibling>`.

## Next steps

1. Change the four `Makefile` recipes to pass `PLAYWRIGHT_BROWSERS_PATH` only
   when it is set.
2. Change the owner in `scripts/local-setup.sh`. It is the only script that
   names an owner; the other scripts list sibling names only.
3. Run `make e2e-fast AI=1` without `PLAYWRIGHT_BROWSERS_PATH` set to confirm.

## What is NOT broken (to scope the fix)

- The e2e tests themselves, which pass once the browsers are found.
- `make local-dev` and the editable-sibling setup, which work on repos that
  are already cloned.

## Resolution

_Open._

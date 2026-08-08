---
Status: active
Owner: CT
Created: 2026-08-08
Last verified: 2026-08-08
Kind: issue
Level: I1
---

# `dep-refresh` cannot auto-land; branches/PRs pile up until someone sweeps by hand

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I1
- **Last verified:** 2026-08-08
- **Resolution:** Open
- **Severity:** Medium — no data loss; dependency currency silently stalls until
  a human notices and sweeps the accumulated pull requests by hand.
- **Affected version:** `.github/workflows/dep-refresh.yml` at `5db3d78` (current `master`)
- **Read when:** touching `dep-refresh.yml`, triaging why weekly dependency PRs
  are piling up, or applying the `pdomain-ui` auto-land design to this repo.
- **Search terms:** dep-refresh, weekly dependency refresh, stray branch,
  delete_branch_on_merge, gh pr merge --auto, ERR_PNPM_LOCKFILE_CONFIG_MISMATCH,
  branch protection required contexts.
- **Relates to:** [intent map](../context/intent-map.md),
  `pdomain-ui` design spec `docs/specs/2026-07-16-dep-refresh-auto-land-design.md`
  (different repo, read-only reference).

## Summary

`dep-refresh.yml` names a fresh dated branch every run
(`dep-refresh/$(date +%Y-%m-%d)-$GITHUB_RUN_ID`) and the repo has
`delete_branch_on_merge: false`, so nothing ever reclaims a branch whose PR
did not merge. The repo currently shows 0 stray `dep-refresh` branches and 0
open PRs, but that is **not** because the structure is safe — it is because a
human (or an agent working in this repo) has swept the accumulated,
never-merged PRs by hand three separate times in under two months
(2026-06-14, 2026-07-12, and again minutes before this report was written,
2026-08-08T11:18 UTC). The branch-per-run / no-delete-on-merge structure that
produced each pile-up is still present in the workflow today.

## Impact

- Weekly dependency currency depends on a human periodically noticing and
  batch-closing dead PRs; nothing in the workflow expires or reuses a red run.
- Each red week adds one more branch and one more open PR, silently, since
  nothing alerts on the growing pile — this is the same shape already
  documented for peer repos where the pile reached seven.
- The very fix landed today (commit `5db3d78`) removes the *current* cause of
  red runs (a pnpm lockfile mismatch) but does not change the workflow's
  branch/PR-reuse structure, so any future red run — for any other reason —
  will resume accumulating exactly as before.

## Environment / versions

```text
pdomain-ocr-simple-gui @ master (HEAD c2a0125, dep-refresh workflow at 5db3d78)
Required branch-protection context on master: ["ci"] (single context)
delete_branch_on_merge: false (repo setting, confirmed via gh api)
```

## Evidence

### 1. The workflow still mints a fresh branch per run and never deletes on merge

`.github/workflows/dep-refresh.yml` (current `master`):

```yaml
BRANCH="dep-refresh/$(date +%Y-%m-%d)-$GITHUB_RUN_ID"
...
gh pr merge --auto --rebase
```

```console
$ gh api repos/pdomain/pdomain-ocr-simple-gui --jq '.delete_branch_on_merge'
false
```

Every run gets its own branch name and no merge ever deletes a branch — the
structural precondition for accumulation the `pdomain-ui` spec identifies.

### 2. The workflow has run repeatedly and produced 8 PRs, none auto-merged

```console
$ gh run list --repo pdomain/pdomain-ocr-simple-gui --workflow dep-refresh.yml --limit 10
completed  success  ...  30734249442  2026-08-02
completed  success  ...  30189620855  2026-07-26
completed  success  ...  29674818884  2026-07-19
completed  success  ...  29181299661  2026-07-12
completed  success  ...  28731559560  2026-07-05
completed  success  ...  28313680362  2026-06-28
completed  success  ...  27896523588  2026-06-21
completed  success  ...  27507144728  2026-06-14 (workflow_dispatch)
completed  failure  ...  27506854436  2026-06-14 (workflow_dispatch)
completed  failure  ...  27491012806  2026-06-14 (schedule)
```

```console
$ gh pr list --repo pdomain/pdomain-ocr-simple-gui --state all --label dep-refresh \
    --json number,state,mergedAt,closedAt,createdAt
#50 CLOSED mergedAt:null closedAt:2026-08-08T11:18:31Z createdAt:2026-08-02T05:38:17Z
#49 CLOSED mergedAt:null closedAt:2026-08-08T11:18:29Z createdAt:2026-07-26T05:36:05Z
#45 CLOSED mergedAt:null closedAt:2026-08-08T11:18:28Z createdAt:2026-07-19T05:26:06Z
#44 CLOSED mergedAt:null closedAt:2026-07-12T10:09:58Z createdAt:2026-07-12T05:32:59Z
#43 CLOSED mergedAt:null closedAt:2026-07-12T10:09:57Z createdAt:2026-07-05T06:09:50Z
#42 CLOSED mergedAt:null closedAt:2026-07-12T10:09:57Z createdAt:2026-06-28T06:23:20Z
#41 CLOSED mergedAt:null closedAt:2026-07-12T10:09:56Z createdAt:2026-06-21T06:55:50Z
#39 CLOSED mergedAt:null closedAt:2026-06-14T18:09:29Z createdAt:2026-06-14T17:52:50Z
```

All 8 weekly PRs are `CLOSED` with `mergedAt: null` — auto-merge never landed
one. They were closed in three distinct batches, seconds apart within each
batch, which is the signature of a manual sweep rather than organic
per-PR review: `#39` alone on 2026-06-14, `#41`–`#44` together on
2026-07-12, and `#45`/`#49`/`#50` together on 2026-08-08T11:18 — minutes
before this report. `gh api .../branches --jq '.[].name'` now returns only
`master`, so the branches behind those PRs were also removed by hand (not by
`delete_branch_on_merge`, which is `false`).

### 3. Why the PRs were red: a real bug, fixed today, but not the structural one

```console
$ gh pr checks 50 --repo pdomain/pdomain-ocr-simple-gui
ci  fail  1m6s
```

The fix landed in the merge commit at `HEAD` (`c2a0125`, merging `5db3d78`):

> `chore: weekly dep refresh (actions pins + all deps)`
> "Replaces the three stale bot PRs (#45, #49, #50), all of which failed CI
> with `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`. ... Fixed here by running a plain
> `pnpm install` after the update, and the dep-refresh workflow now does the
> same so this stops recurring weekly."

`dep-refresh.yml` itself now carries the same note inline, dated today:
"Every dep-refresh PR opened before 2026-08-08 failed CI this way." This
confirms the reason all 8 PRs were red (a lockfile-override resolution gap)
is fixed as of `5db3d78`. It does **not** touch the branch-naming or
`delete_branch_on_merge` settings that let the red PRs pile up in the first
place — those are unchanged in the current workflow file.

### 4. The merge gate itself is sound (unlike the peer repos with a renamed job)

```console
$ gh api repos/pdomain/pdomain-ocr-simple-gui/branches/master/protection \
    --jq '.required_status_checks.contexts'
["ci"]
```

`.github/workflows/ci.yml` defines exactly one job, `name: ci` / job id `ci`
(`jobs.ci`), on `pull_request`, and `gh pr checks 50` above shows it reporting
as context `ci` — the required context is produced by a real job. This repo
does **not** have the peer-repo problem (`pdomain-ops`,
`pdomain-ocr-training`) where a required context outlives a job rename and
blocks every PR forever. No branch-protection change is needed here.

## Root-cause hypotheses

1. **(Confirmed, primary)** The workflow's per-run dated branch name plus
   `delete_branch_on_merge: false` has no mechanism to expire or reuse a red
   run's branch/PR. Every red week adds one more of each. Direct evidence:
   8 PRs, `mergedAt: null` on all, three separate manual batch-close events.
2. **(Confirmed, contributing, already resolved for now)** A pnpm
   lockfile-override resolution gap
   (`ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`) made every one of those 8 runs fail
   the `ci` gate, so none could ever reach auto-merge even before the
   structural gap mattered. Fixed in `5db3d78` (today) — the *symptom* that
   made this pile visible is gone, but the *mechanism* that would let it
   recur for any other red-run reason is still in place.
3. **(Ruled out)** Merge-gate context mismatch (the bug affecting
   `pdomain-ops` / `pdomain-ocr-training`). Checked directly against this
   repo's branch protection and `ci.yml`; the single required context `ci`
   maps to a real, currently-passing/failing job. Not a factor here.

## Defects to fix

1. **No branch/PR reuse across runs (primary)** — `dep-refresh.yml` should use
   one reusable `dep-refresh` branch, force-pushed from a fresh `master` each
   run, and open a PR only when no open one already exists for that branch.
2. **`delete_branch_on_merge: false`** — a green auto-merge currently would
   not clean up its own branch even if it did land; needs to be `true` on
   this repo.
3. **No re-arm of auto-merge on the reused branch** — once (1) is in place,
   each run needs to re-run `gh pr merge --auto --rebase` against the
   existing (or newly opened) PR so a red-then-green sequence still lands
   unattended.

## Next steps

1. Apply the `pdomain-ui` design (see
   `docs/specs/2026-07-16-dep-refresh-auto-land-design.md` in the
   `pdomain-ui` repo, sections 3.B and 3.C) to this repo's
   `.github/workflows/dep-refresh.yml`: reusable `dep-refresh` branch,
   open-PR-only-if-none-open check, re-armed `gh pr merge --auto --rebase`.
2. Set `delete_branch_on_merge: true` on `pdomain/pdomain-ocr-simple-gui`
   (repo setting, not a workflow change).
3. Confirm this repo does not need the `pdomain-ui` spec's section 3.A
   (`unit-test` gate rename) — already verified moot here (see Evidence §4)
   — so only 3.B and 3.C apply.
4. After landing, watch one full weekly cycle (next scheduled run,
   2026-08-15 02:00 UTC) to confirm a red or green result reuses the single
   branch/PR instead of minting a new one.

## What is NOT broken (to scope the fix)

- The branch-protection required-status-check mapping (`ci` → job `ci`) is
  correct; this repo does not have the peer repos' stale-context problem.
- The dependency-refresh logic itself (Python via `uv lock --upgrade`,
  GitHub Actions SHA pins, and now the corrected `pnpm install` follow-up)
  is working — the CI failures that produced 8 red PRs are already fixed as
  of `5db3d78`.

## Resolution

*Open.* The immediate symptom (CI-failing lockfile mismatch) was independently
fixed in commit `5db3d78` on 2026-08-08, and the resulting stale PRs
(`#45`, `#49`, `#50`) were closed by hand in the same window. The structural
defect that let 8 PRs accumulate over three manual sweeps — dated branch
naming plus `delete_branch_on_merge: false`, with no auto-merge re-arm — is
unchanged and will resume accumulating on the next red run for any reason.
Apply the `pdomain-ui` auto-land design (sections 3.B/3.C) to close this out.

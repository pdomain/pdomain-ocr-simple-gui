---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-07-14
Kind: runbook
---

# Release runbook

## Agent Index

- **Kind:** runbook
- **Status:** active
- **Read when:** cutting a local release from `master`.
- **Search terms:** release, tag, master, GitHub artifacts, index dispatch.

## Trigger

Use this runbook only when an owner has authorized a release.

## Preconditions

Start from a clean, up-to-date `master` checkout with release credentials.
The local release helper runs its configured preflight, including the slow CI
gate, before creating a tag.

## Steps

Run exactly one local target:

```bash
make release-patch
make release-minor
make release-major
```

The helper creates an annotated semantic-version tag, pushes `master` and the
tag, and dispatches the release workflow. The workflow builds one wheel and one
source distribution, publishes both as GitHub Release artifacts, and dispatches
`pdomain-index-pip` when `PDOMAIN_INDEX_DISPATCH` is available. Scheduled index
regeneration is the fallback.

## Verification

Confirm the tag, GitHub Release artifacts, workflow result, and index dispatch
or scheduled fallback. The implementation sources are `scripts/do-release.sh`
and `.github/workflows/release.yml`.

## Rollback

Do not rewrite a published tag. Stop before pushing if preflight fails. If an
artifact or index dispatch fails after publication, correct the defect and cut
a new patch release.

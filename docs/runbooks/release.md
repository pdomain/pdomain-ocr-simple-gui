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
tag, then builds one wheel and one source distribution and publishes both as
GitHub Release artifacts. It does all of this locally: the workflows were
removed on 2026-09-13.

Publishing to the index is a separate, manual step, with no dispatch and no
scheduled fallback:

```bash
(cd ../pdomain-index-pip && ./scripts/publish-index.sh)
```

## Verification

Confirm the tag, the GitHub Release artifacts, and that the package appears on
the index after running the publish script. The implementation sources are
`scripts/do-release.sh` and `scripts/release-common.sh`.

## Rollback

Do not rewrite a published tag. Stop before pushing if preflight fails. If an
artifact or index dispatch fails after publication, correct the defect and cut
a new patch release.

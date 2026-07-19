---
Status: active
Owner: CT
Created: 2026-07-19
Last verified: 2026-07-19
Kind: issue
Level: I1
---

# Isolate suite launcher tabs from the opener

The shared suite launcher still opens tabs without `noopener,noreferrer`.
This repository cannot complete the fix until `pdomain-ui` owns and releases
the corrected launcher behavior.

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I1
- **Last verified:** 2026-07-19
- **Resolution:** Open
- **Severity:** Medium — launched pages retain opener access
- **Affected version:** `@pdomain/pdomain-ui` 0.11.0
- **Read when:** changing the shared launcher or upgrading `pdomain-ui`.
- **Search terms:** GitHub issue 26, window.open, noopener, noreferrer, launcher, tabnabbing.
- **Relates to:** [intent map](../context/intent-map.md), [migration ledger](../context/github-issue-migration-ledger.md)

## Summary

Former GitHub issue #26 identified a reverse-tabnabbing boundary in the shared
suite launcher. Local app links are fine; the `window.open` call lives inside
the compiled `@pdomain/pdomain-ui` AppShell. Commit `5c6f052` documented the
ownership boundary rather than claiming a local fix. Work remains blocked on
an upstream release.

## Impact

- A page opened by the suite launcher may retain access to `window.opener`.
- The affected call is shared UI code and cannot be corrected in this app alone.

## Environment / versions

```text
pdomain-ocr-simple-gui (master)
@pdomain/pdomain-ui ^0.11.0 (frontend/package.json)
```

## Evidence

### 1. Local ownership note

`frontend/src/App.tsx` states that the suite launcher opens sibling apps via
`window.open(url, "_blank")` inside the compiled AppShell bundle, and that this
repo's own anchors do not use `target="_blank"`.

### 2. Provenance (deleted GitHub issue)

- Former URL: <https://github.com/pdomain/pdomain-ocr-simple-gui/issues/26>
- Original author: `ConcaveTrillion`
- Original state and reason: closed, `completed` (closed without a full fix)
- Labels at archive time: kind/bug style backlog item
- Archive section digest (SHA-256 of the `#26` section at `ec3979f`): see the
  full 64-hex digest for row 26 in
  [the migration ledger](../context/github-issue-migration-ledger.md).
- Verbatim body recoverable via:
  `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`

### 3. Related commit

`5c6f052` — documented local boundary / suite launcher link hygiene; did not
change the shared AppShell `window.open` implementation.

## Root-cause hypotheses

1. **(Most likely) Shared launcher omits isolation features** — the call site is
   inside `@pdomain/pdomain-ui`, so only that package can ship the fix.
2. **Local wrapper insufficient** — wrapping after launch cannot guarantee the
   shared component's behavior across upgrades.

## Defects to fix

1. **Add `noopener,noreferrer` in the `pdomain-ui` launcher** — primary.
2. **Release and bump** — upgrade `@pdomain/pdomain-ui` here and verify the
   compiled bundle.

## Next steps

1. Land and release the upstream change in `pdomain-ui`.
2. Bump the dependency in this app.
3. Verify the compiled launcher call and browser opener behavior.

## What is NOT broken (to scope the fix)

- App-local `<a>` elements that do not use `target="_blank"`.
- Other security work from the former GitHub backlog (#16–#19, #23) that already
  ships in this repository.

## Resolution

*Open and blocked upstream.* Migrated from deleted GitHub #26. See
[the intent map](../context/intent-map.md) and
[the migration ledger](../context/github-issue-migration-ledger.md).

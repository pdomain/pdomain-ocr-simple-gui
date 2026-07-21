---
Status: active
Owner: CT
Created: 2026-07-21
Last verified: 2026-07-21
Kind: plan
---

# Suite Launcher Opener Isolation Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close former issue #26 using evidence from the already-installed fixed shared UI package.

**Architecture:** Verify the locked 0.11.0 package and upstream regression test, remove stale local guidance, then route issue retirement and context reconciliation through docgraph. No runtime or dependency behavior changes.

**Tech Stack:** React/Vite consumer, pnpm lockfile, Git, Make, docgraph.

---

## Agent Index

- **Kind:** plan
- **Status:** active
- **Read when:** executing the documentation closeout for former GitHub issue #26.
- **Search terms:** issue 26 closeout, noopener, noreferrer, LauncherTile, doc-retirer.
- **Relates to:** [closeout design](../specs/2026-07-21-suite-launcher-opener-closeout-design.md),
  [governed issue](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md).

## Goal

Close former issue #26 using evidence from the already-installed fixed shared UI package.

## Architecture

Verify the locked package and upstream regression test. Then remove stale guidance and use docgraph governance to reconcile context and retire the issue.

## Tech Stack

React/Vite consumer, pnpm lockfile, Git, Make, and docgraph.

## Global Constraints

- Do not bump `@pdomain/pdomain-ui` or add a local launcher wrapper.
- Preserve unrelated staged documentation changes.
- Run frontend build, full CI, reindex, and strict docgraph checks before closeout.

### Task 1: Verify the shipped dependency evidence

**Files:**
- Inspect: `frontend/package.json`
- Inspect: `frontend/pnpm-lock.yaml`
- Inspect: `frontend/node_modules/@pdomain/pdomain-ui` after installation

- [ ] **Step 1: Confirm the declared and locked versions**

Run:

```bash
rg -n '"@pdomain/pdomain-ui": "\^0\.11\.0"' frontend/package.json
rg -n "'@pdomain/pdomain-ui@0\.11\.0'" frontend/pnpm-lock.yaml
```

Expected: each command prints at least one matching line and exits 0.

- [ ] **Step 2: Install the locked frontend dependencies**

Run: `make frontend-install`

Expected: pnpm completes with the frozen lockfile and exits 0.

- [ ] **Step 3: Verify the installed launcher call**

Run:

```bash
rg -n "window\.open\([^)]*noopener,noreferrer" frontend/node_modules/@pdomain/pdomain-ui
```

Expected: at least one built launcher match contains `noopener,noreferrer`. Stop the closeout if no match exists; the installed artifact would contradict the design evidence.

- [ ] **Step 4: Record the upstream source evidence in the work log**

Run:

```bash
git -C ../pdomain-ui show --stat --oneline 562938d
git -C ../pdomain-ui show 562938d -- src/shell/LauncherTile.tsx src/shell/LauncherTile.test.tsx
```

Expected: the source uses `window.open(result.url, '_blank', 'noopener,noreferrer')`, and the test asserts those arguments.

### Task 2: Remove stale local blocker guidance

**Files:**
- Modify: `frontend/src/App.tsx:4`

- [ ] **Step 1: Delete only the obsolete issue-26 comment**

Remove these lines:

```ts
// noopener note (issue #26):
// The suite launcher opens sibling apps via window.open(url, "_blank") inside the
// compiled @pdomain/pdomain-ui AppShell bundle. Our own <a> elements don't use
// target="_blank". The upstream fix (add "noopener,noreferrer" to window.open call)
// must land in pdomain-ui; once that is released, bump @pdomain/pdomain-ui here.
```

- [ ] **Step 2: Run the frontend build**

Run: `make frontend-build`

Expected: exit 0 with a completed Vite build.

- [ ] **Step 3: Commit the stale-comment removal**

```bash
git add frontend/src/App.tsx
git commit -m "docs(frontend): remove resolved launcher blocker note"
```

### Task 3: Promote evidence and retire the issue

**Files:**
- Modify: `docs/architecture/00-overview.md`
- Modify: `docs/context/current-state.md`
- Modify: `docs/context/intent-map.md`
- Retire: `docs/issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md`
- Modify: doc-retirer tombstone and link-repair files selected by the governed workflow

- [ ] **Step 1: Add the shipped launcher boundary to architecture**

Replace the stale statement that the launcher "must add" isolation with present-tense text:

```markdown
`@pdomain/pdomain-ui` 0.11.0 isolates sibling tabs with
`window.open(url, "_blank", "noopener,noreferrer")`. Upstream commit `562938d`
and `LauncherTile.test.tsx` pin this boundary.
```

- [ ] **Step 2: Remove active and deferred issue references from authored context**

Delete the #26 entry from `docs/context/current-state.md`. Delete both the active-item link and the deferred "Launcher opener isolation" paragraph from `docs/context/intent-map.md`. Keep unrelated entries byte-for-byte unchanged.

- [ ] **Step 3: Run the spec retirement workflow**

Invoke `docgraph:doc-retirer` with evidence that 0.11.0 is locked, upstream commit `562938d` contains the fix and test, and Task 1 verified the installed artifact. Retire the issue record, repair its inbound links, and write the required tombstone. Do not archive the stale issue as current truth.

- [ ] **Step 4: Reindex and run the strict documentation gate**

Run:

```bash
docgraph reindex
docgraph check --strict
```

Expected: reindex succeeds and strict check reports no blocking issue introduced by this closeout.

- [ ] **Step 5: Run full repository verification**

Run: `make ci AI=1`

Expected: exit 0 with the repository's success summary.

- [ ] **Step 6: Commit the governed closeout**

Stage only the files changed by Task 3, excluding unrelated pre-existing work:

```bash
git add docs/architecture/00-overview.md docs/context/current-state.md docs/context/intent-map.md
git add -u docs/issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md
git add <doc-retirer-tombstone-path> <doc-retirer-link-repair-paths>
git commit -m "docs: close resolved suite launcher isolation issue"
```

Replace the doc-retirer paths with the exact files reported by the workflow before staging. Confirm `git diff --cached --name-only` excludes `docs/plans/2026-07-21-deferred-followups.md` and `docs/roadmap.md`.

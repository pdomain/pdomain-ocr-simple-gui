---
Status: active
Owner: CT
Created: 2026-07-21
Last verified: 2026-07-21
Kind: spec
---

# Suite launcher opener isolation needs documentation closeout only

Former issue #26 is already fixed by the installed `@pdomain/pdomain-ui` 0.11.0 package, so this repository needs no dependency or runtime change.

## Agent Index

- **Kind:** spec
- **Status:** active
- **Read when:** closing former GitHub issue #26 or auditing suite launcher tab isolation.
- **Search terms:** issue 26, LauncherTile, noopener, noreferrer, pdomain-ui 0.11.0.
- **Relates to:** [governed issue](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md),
  [closeout plan](../plans/2026-07-21-suite-launcher-opener-closeout.md).

## Adversarial Review

The author checked the closeout against the issue, package manifest, lockfile, upstream commit `562938d`, and its regression test. An independent writing-docs review could not run because the shared agent pool had no free slot. No unresolved author finding remains.

## Installed code already meets the requirement

`frontend/package.json` requests `@pdomain/pdomain-ui` `^0.11.0`, and `frontend/pnpm-lock.yaml` resolves 0.11.0. Upstream commit `562938d6a8df6f9dd20f8772afc18f99eede46fb` changed `LauncherTile` to call:

```ts
window.open(result.url, '_blank', 'noopener,noreferrer');
```

The upstream `LauncherTile.test.tsx` asserts the same three arguments. The fix predates the local issue's claim that 0.11.0 remained vulnerable.

## Closeout removes stale guidance

The work will remove the obsolete blocker comment from `frontend/src/App.tsx`. It will update authored context so current-state and intent no longer describe the issue as blocked.

The governed issue will be retired through the repository's doc-retirer workflow. Durable architecture will record the installed package version, upstream commit, and regression-test evidence before retirement removes the active issue record.

## Verification proves consumption rather than reimplementation

The frontend build proves the locked package still integrates. Full CI proves the comment and documentation closeout do not disturb the application. A source inspection of the locked package or its release artifact must find the three-argument `window.open` call.

No package bump, local launcher wrapper, or new app test is required. This app does not own `LauncherTile`, and duplicating its upstream unit test would couple the consumer to package internals.

## Acceptance criteria

- The installed 0.11.0 launcher is verified to use `noopener,noreferrer`.
- The stale blocker comment is removed from `frontend/src/App.tsx`.
- Architecture and authored context describe the issue as resolved.
- The active issue record is retired through docgraph governance.
- Frontend build, full CI, reindex, and strict docgraph checks pass.

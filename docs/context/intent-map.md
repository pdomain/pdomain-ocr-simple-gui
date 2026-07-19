---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-07-19
Kind: context
---

# Intent map

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** deciding whether to expand deployment or packaging scope, or
  checking deferred and blocked product bets.
- **Search terms:** intent, hosted deployment, Windows, macOS, packaging,
  deferred, blocked, open issues, cancellation, config fetch, API token.

## Active bets

None.

## Open issues (governed)

- [Isolate suite launcher tabs from the opener](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md)
  — former GitHub #26; blocked on `@pdomain/pdomain-ui`.

## Deferred work

- **Download truth separation — deferred.** Per-page edits and reruns update
  canonical page artifacts but do not rebuild the job output mirror. Preserve
  separate original and modified downloads, explicit provenance, and a test that
  proves an edited page appears in the selected export. The current two fixed
  job-level download buttons replaced the earlier checkbox proposal.
- **Multilingual OCR profiles — deferred.** The shipped narrow rule maps `en`
  to Tesseract `eng`. A future `OcrProfile` should separate language, script,
  engine, model, and capability data. Runtime ownership belongs in a capability
  statechart with unresolved, checking, available, unavailable, and error
  states. Regression coverage must include missing traineddata, mixed scripts,
  engine/profile mismatch, managed-mode restrictions, and fallback behavior.
  Evaluate PAGE-XML import before building a new annotation format. Prioritize
  historical-document ground truth, then modern layout data, scene text, and
  handwriting only when those product surfaces exist. Dataset work must record
  license, redistribution, script coverage, layout labels, and train/test split
  constraints. Open decisions include profile ownership, mixed-script policy,
  model download authority, managed-mode capability reporting, and whether a
  broader engine such as PaddleOCR is justified.
- **Richer project browsing — deferred.** The shared AppShell jobs dock now
  lists, opens, and deletes jobs, and recent projects are recorded at creation.
  A dedicated catalogue with page count, engine, and last-opened metadata is
  still unbuilt and should start only if the dock proves insufficient.
- **Job cancellation — deferred ([ocr-container-meta#395](https://github.com/ConcaveTrillion/ocr-container-meta/issues/395)).**
  The `cancelled` state is modeled end-to-end in the job statechart, models, and
  API types, but no route fires the `cancel` event and the frontend no-ops
  cancellation. Decide ship-or-strip.
- **Config-fetch deduplication — deferred ([ocr-container-meta#396](https://github.com/ConcaveTrillion/ocr-container-meta/issues/396)).**
  `ConfigContext` and `jobCreationMachine` each fetch `/api/config`
  independently. Config-load failures are now surfaced to the user, but the
  duplicate fetch remains.
- **API-token Settings field — deferred ([ocr-container-meta#398](https://github.com/ConcaveTrillion/ocr-container-meta/issues/398)).**
  The frontend now sends a bearer token from `localStorage` via `apiFetch`, set
  through a browser-console command. A proper masked Settings input is unbuilt.
- **Hosted deployment — deferred.** The app ships local and managed mode
  selection, capability-token protection through `PDOMAIN_API_TOKEN`, and
  managed-mode source/output restrictions. It does not ship a hosted service,
  hosted persistence, account model, or production deployment contract. Owner:
  a future hosted-product maintainer. Start only after a consumer and threat
  model are approved.
- **Windows and macOS packaging — deferred.** The supported installer path is
  Linux/browser-first. Shortcut helpers report unsupported platforms rather
  than pretending Windows or macOS installers exist. Owner: platform packaging
  maintainers. Require platform-native install, uninstall, launch, and upgrade
  tests before support is claimed.

## Blocked (waiting on)

- **Launcher opener isolation — blocked upstream (former GitHub #26).** This app
  does not own the shared `window.open` call. `@pdomain/pdomain-ui` must add
  `noopener,noreferrer`; after its release, bump the dependency and verify the
  compiled AppShell bundle. Evidence: `frontend/src/App.tsx`. Governed record:
  [suite launcher opener isolation](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md).
- **Predictor-cache lock — blocked upstream ([ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397)).**
  Bounded dispatcher timeouts cancel the awaiter but not the executor thread,
  which can still race `_predictor_cache` in `pdomain-ops`.

## Rejected directions

- Do not describe authentication or mode selection as wholly unbuilt. Token
  auth and local/managed branching already ship in `auth.py`, `runtime/mode.py`,
  route guards, and their tests.
- Do not treat the 2026-07-17 roadmap dump of all 37 GitHub issues as open work.
  Most were already implemented; see
  [the migration ledger](github-issue-migration-ledger.md).

## Needs owner decision

None for lifecycle of retained docs. Product ship-or-strip for job cancellation
remains under deferred work (meta#395).

## Legacy-unverified sweep

The 2026-07-14 migration verified retained architecture, process, runbook, and
behavior documents against current code, tests, and history. The 2026-07-19
GitHub-issue repair reclassified the deleted tracker against code; no
owner-only lifecycle decision remains for those 37 issues.

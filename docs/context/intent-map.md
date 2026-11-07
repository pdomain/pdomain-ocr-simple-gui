---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-07
Kind: context
---

# Intent map

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** deciding whether to expand deployment or packaging scope, or
  checking deferred and blocked product bets.
- **Search terms:** intent, hosted deployment, Windows, macOS, packaging,
  deferred, blocked, open issues, needs owner decision, dep-refresh.

## Active bets

None.

## Open issues (governed)

- [The font-size setting never saves](../issues/2026-11-07-font-scale-never-persists.md)
  — the frontend sends `fontScale`, the backend reads `font_scale`.
- [Re-run shortcuts check the wrong engine](../issues/2026-11-07-rerun-shortcuts-check-wrong-engine.md)
  — Ctrl+R needs Tesseract, Ctrl+Shift+R does not.
- [Viewer PNG caches become extra OCR pages](../issues/2026-11-07-viewer-png-cache-becomes-ocr-page.md)
  — `.viewer.png` files in the source folder count as pages.
- [CUDA setup link is not served](../issues/2026-11-07-cuda-setup-link-not-served.md)
  — the Compute panel help link lands on the app home screen.
- [Setup defaults point at the old devcontainer and owner](../issues/2026-11-07-devcontainer-and-old-org-defaults.md)
  — Playwright path in the `Makefile`, clone owner in `local-setup.sh`.
- [`dep-refresh` cannot auto-land](../issues/2026-08-08-dep-refresh-cannot-auto-land.md)
  — needs an owner decision; see below.

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

- **`dep-refresh` auto-land issue: close or keep.** The issue asks for a
  reusable branch and auto-merge re-arm in `.github/workflows/dep-refresh.yml`.
  Commit `0bb3a4a` (2026-09-13, owner request) deleted every GitHub workflow,
  including `dep-refresh.yml`, so the pile-up cannot recur today. Close the
  issue as moot, or keep it for the day the workflows return. Record:
  [dep-refresh cannot auto-land](../issues/2026-08-08-dep-refresh-cannot-auto-land.md).

Job cancellation (meta#395) was decided as strip; the rationale is in
[decisions](decisions.md).

## Legacy-unverified sweep

The 2026-07-14 migration verified retained architecture, process, runbook, and
behavior documents against current code, tests, and history. The 2026-07-19
GitHub-issue repair reclassified the deleted tracker against code; no
owner-only lifecycle decision remains for those 37 issues.

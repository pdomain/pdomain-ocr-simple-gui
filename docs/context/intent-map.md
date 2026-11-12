---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-11-12
Kind: context
---

# Intent map

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** deciding whether to expand deployment or packaging scope, or
  checking deferred and blocked product bets.
- **Search terms:** intent, hosted deployment, Windows, macOS, packaging,
  deferred, blocked, needs owner decision, dep-refresh, other repos.

## Active bets

None.

## Open bugs

The ordered list is the [roadmap](../roadmap.md). The issue files are linked
from the [issues index](../issues/README.md). This map does not copy them.

## Deferred work

- **Download truth separation. Deferred. Stays in this repo.** Per-page edits and reruns update canonical page artifacts, but they do not rebuild the job output mirror. Preserve separate original and modified downloads, explicit provenance, and a test that proves an edited page appears in the selected export. The current two fixed job-level download buttons replaced the earlier checkbox proposal.
- **Multilingual OCR profiles. Deferred. Belongs in `pdomain-book-tools` and `pdomain-ops`, not here.** The shipped narrow rule maps `en` to Tesseract `eng`.

  A future `OcrProfile` should separate language, script, engine, model, and capability data. Runtime ownership belongs in a capability statechart with unresolved, checking, available, unavailable, and error states.

  Regression coverage must include missing traineddata, mixed scripts, engine/profile mismatch, managed-mode restrictions, and fallback behavior.

  Open decisions include profile ownership, mixed-script policy, model download authority, managed-mode capability reporting, and whether a broader engine such as PaddleOCR is justified.

  The PP-DocLayout-Plus-L pass already ships in this app, in `layout_pass.py`. It calls `pdomain_book_tools.layout.get_detector`. The detector stays in `pdomain-book-tools`.
- **Ground truth, labeling, and training data. Deferred. Not this app.** The repos that already do this work are `pdomain-ocr-labeler-spa`, `pdomain-ocr-trainer-spa`, `pdomain-ocr-training`, `pdomain-ocr-synth`, and `pdomain-source-data`.

  Evaluate PAGE-XML import before a new annotation format. Start with historical-document ground truth, then modern layout. Add scene text and handwriting only when those products exist.

  Dataset work must record license, redistribution, script coverage, layout labels, and train/test split constraints.
- **Richer project browsing. Deferred. Belongs in `@pdomain/pdomain-ui` if the shared dock is not enough.** The shared AppShell jobs dock now lists, opens, and deletes jobs. Recent projects are recorded at creation.

  A dedicated catalogue with page count, engine, and last-opened metadata is still unbuilt. It should start only if the dock proves insufficient.
- **Hosted deployment. Deferred. A new service repo, and only after a consumer and a threat model are approved.** The app ships local and managed mode selection, capability-token protection through `PDOMAIN_API_TOKEN`, and managed-mode source/output restrictions. It does not ship a hosted service, hosted persistence, account model, or production deployment contract.

  Owner: a future hosted-product maintainer. Start only after a consumer and threat model are approved.
- **Windows and macOS packaging. Deferred. No new installer repo until a second app needs the same native installer.** The supported installer path is Linux/browser-first. Shortcut helpers report unsupported platforms rather than pretending Windows or macOS installers exist.

  Owner: platform packaging maintainers. Require platform-native install, uninstall, launch, and upgrade tests before support is claimed.

## Blocked, waiting on another repo

- **Predictor-cache lock. Blocked in `pdomain-ops`. [ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397).** Bounded dispatcher timeouts cancel the awaiter but not the executor thread. That thread can still race `_predictor_cache` in `pdomain-ops`. Do not patch the cache in this app.

## Rejected directions

- Do not describe authentication or mode selection as wholly unbuilt. Token auth and local/managed branching already ship in `auth.py`, `runtime/mode.py`, route guards, and their tests.
- Do not treat the 2026-07-17 roadmap dump of all 37 GitHub issues as open work. Most were already implemented. See [the migration ledger](github-issue-migration-ledger.md).

## Needs owner decision

- **Old viewer caches in source folders.** New caches are written in the
  project directory. Collection skips old `.viewer.png` copies. The old
  `.viewer.png` and `.viewer.webp` files stay in folders the user owns.
  Deleting them is still an owner decision. The roadmap lists it.
- **`dep-refresh` auto-land issue: close or keep.** The issue asks for a reusable branch and auto-merge re-arm in `.github/workflows/dep-refresh.yml`.

  Commit `0bb3a4a`, on 2026-09-13 at the owner's request, deleted every GitHub workflow, including `dep-refresh.yml`. The pile-up cannot recur today.

  The owner still chooses: close the issue as obsolete, or keep it.

  Checked on 2026-11-07, PRs #51 through #55 were still open. Their five `dep-refresh/` branches still existed.

  The earlier steps that apply the `pdomain-ui` auto-land design described the deleted workflow. They no longer apply.

  That `pdomain-ui` spec is a historical proposal. Its owner still has to decide whether to abandon or replace it.

  The record is [dep-refresh cannot auto-land](../issues/2026-08-08-dep-refresh-cannot-auto-land.md).

Job cancellation, meta#395, was decided as strip. The rationale is in [decisions](decisions.md).

## Legacy-unverified sweep

No owner-only lifecycle decision remains for those 37 issues.

The 2026-07-14 migration verified retained architecture, process, runbook, and behavior documents against current code, tests, and history.

The 2026-07-19 GitHub-issue repair reclassified the deleted tracker against code.

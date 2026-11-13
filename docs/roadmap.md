---
Status: active
Owner: CT
Created: 2026-07-17
Last verified: 2026-11-12
Kind: plan
---

# pdomain-ocr-simple-gui Roadmap

## Agent Index

- **Kind:** plan
- **Status:** active
- **Read when:** deciding what to work on next in `pdomain-ocr-simple-gui`,
  including work that belongs in another repo.
- **Search terms:** roadmap, remaining work, backlog, open priorities, needs
  owner decision, other repos, sibling repos

## Goal

This is the only list of work still open for this app.

- Shipped behavior is in the [architecture overview](architecture/00-overview.md).
- The reason a deferred bet stays deferred is in the [intent map](context/intent-map.md).
- Each open bug file is linked from the [issues index](issues/README.md).

## Architecture

The [overview](architecture/00-overview.md), the
[module map](architecture/module-map.md), and
[runtime flows](architecture/runtime-flows.md) describe the running app.
This roadmap does not restate that design.

## Tech Stack

- Python, FastAPI, and Pydantic run on the server.
- React and TypeScript run on Vite in the browser.
- Tests use Vitest and pytest.
- The tool gate is `uv`, Ruff, and basedpyright.
- The layer table is in the [overview](architecture/00-overview.md).

## Global Constraints

- Keep reusable OCR and dispatch logic upstream.
- Backend and frontend contracts must stay aligned.
- Treat caller-controlled paths and IDs as untrusted.
- Run `AI=1 just ci` before committing.
- Work that belongs in another repo is listed below, and it is not a task for this app.

## Resolved on master

These landed in the merge of `fix/e2e-flakes`.

- Font size saves as `font_scale` (`cc2a8ca`). Ctrl+Shift+R is the
  Tesseract re-run shortcut (`fad237a`). New viewer caches go in the
  project directory, and collection skips old `.viewer.png` copies
  (`37f3ab9`). The Compute panel links to the published CUDA guide
  (`e8bcd17`). Setup no longer uses the devcontainer Playwright path
  or the old clone owner (`4c37fea`). The issue files are retired.
  The tombstone is in [decisions](context/decisions.md).
- The browser tests wait for word overlays (`60020aa`), let uvicorn
  pick the port (`630e2e0`), wait for a finished upload job
  (`0451c26`), and check the 404 words response before reading the
  count (`73cacdd`). `fix/word-overlay-flake`, `60020aa` through
  `af4afdd`, is the word-overlay part of that same merge.
- The smoke server starts with `--port 0` and reads the bound port
  from uvicorn's log. `start_smoke_server` in `tests/smoke/test_e2e.py`
  is that path. A held port is not the URL the test uses.
- The `# ---` divider banners are gone from `tests/e2e/`. This was
  former GitHub issue #13. The
  [migration ledger](context/github-issue-migration-ledger.md) has the row.

## Owner decision still open

Close or keep the `dep-refresh` issue, and clean up the pull requests it left behind.

Commit `0bb3a4a` on 2026-09-13, at the owner's request, deleted every GitHub workflow, including `.github/workflows/dep-refresh.yml`. No new refresh run can open.

Checked on 2026-11-07, PRs #51 through #55 were still open. Auto-merge was still armed. Their five `dep-refresh/` branches still existed. `delete_branch_on_merge` was still false.

What is left is to close or delete those five pull requests and branches, and to decide whether to close the issue as obsolete.

The issue's earlier fix steps described the deleted workflow and no longer apply. That includes copying the `pdomain-ui` auto-land design.

That design is a historical proposal in `pdomain-ui`. Its owner still has to decide whether to abandon or replace it before anyone implements it.

Do not treat it as the design for this repo.
[Issue](issues/2026-08-08-dep-refresh-cannot-auto-land.md).

Old `.viewer.png` and `.viewer.webp` files can remain in source folders.
`37f3ab9` stores new caches in the project directory and skips old
`.viewer.png` copies during collection. Deleting the leftover files is
still an owner decision.

## Work that belongs in another repo

This app stays a small local OCR consumer. Shared OCR, suite plumbing, and
shared UI stay upstream. That boundary is
[preserved runtime boundaries](decisions/2026-07-13-preserved-runtime-boundaries.md).

These already have a home:

- The predictor-cache lock belongs in `pdomain-ops`. A batch timeout cancels
  the waiting task and does not stop the executor thread. A timed-out batch
  can still race `_predictor_cache`.
  [ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397).
  Do not patch that cache in this app.

  Job cancel was stripped on 2026-07-21. That decision's remaining work is
  none. Bringing cancel back would need a new decision, and that decision
  would need this executor fix first. Cancel is not open work on this
  roadmap. The strip decision is in [decisions](context/decisions.md).
- A richer job catalogue belongs in `@pdomain/pdomain-ui` if the shared jobs
  dock is not enough. The dock already lists, opens, and deletes jobs. This
  app records recent projects when a job is created. Page count, engine, and
  last-opened metadata are not built.
- Language profiles and engine capability belong in `pdomain-book-tools`
  and `pdomain-ops`. This app only maps `en` to Tesseract `eng`.

  A future profile should separate language, script, engine, model, and
  capability data. Design the capability states upstream: unresolved,
  checking, available, unavailable, and error.

  Still open: who owns the profile, mixed-script policy, who may download a
  model, what managed mode reports, and whether a broader engine such as
  PaddleOCR is justified.

  Tests have to cover missing traineddata, mixed scripts, an engine that
  does not match the profile, managed-mode limits, and fallback.

  The PP-DocLayout-Plus-L pass already ships in this app, in `layout_pass.py`.
  It calls `pdomain_book_tools.layout.get_detector` for
  `pp-doclayout-plus-l`, then `Page.reorganize_page`. The detector stays in
  `pdomain-book-tools`. Do not rebuild it here.
- Ground truth, labeling, training, and synthetic pages belong in the repos
  that already do that work: `pdomain-ocr-labeler-spa`,
  `pdomain-ocr-trainer-spa`, `pdomain-ocr-training`, `pdomain-ocr-synth`,
  and `pdomain-source-data`. Do not add a labeler or a trainer to this app.

  Start with historical-document ground truth, then modern layout. Add
  scene text and handwriting only when those products exist. Evaluate a
  PAGE-XML import before a new annotation format.

  Dataset work has to record license, redistribution, script coverage,
  layout labels, and the train/test split.

Do not start a new repo for any of these until its own condition is true:

- **A hosted service.** This app ships local mode, managed mode, a capability
  token through `PDOMAIN_API_TOKEN`, and managed-mode limits on source and
  output paths. It does not ship hosted persistence, accounts, or a
  production deployment contract. A new service repo waits for an approved
  consumer and an approved threat model.
- **Windows and macOS installers.** The supported install is Linux, then the
  browser. Shortcut helpers report that the other platforms are unsupported.
  The Linux wheel, `install.sh`, and `uninstall.sh` stay here, with their
  own tests. A shared installer repo waits until a second app needs the
  same native installer.
- **A shared behavior-coverage package.** This repo and
  `pdomain-ocr-labeler-spa` each carry `scripts/behavior_coverage.py`.
  Leave the two copies until a third app needs the same gate. If the
  checker is extracted, put it in an existing shared library. Do not make
  a new product repo for it.

## Deferred, and not active work

These stay deferred. None of them are active work.

The constraints are in the [intent map](context/intent-map.md).

- Separate original engine output from the user's edited text. This stays
  in this repo, and it is not a current task. The design stub says it is
  not scheduled. Saving text or rerunning one page updates the project
  tree and does not refresh the output mirror. The ZIP is built from that
  mirror. [Design stub](specs/2026-05-29-download-model.md). The steps
  that ship today are in [runtime flows](architecture/runtime-flows.md).
- Multilingual OCR profiles, the richer catalogue, hosted deployment, and
  Windows or macOS packaging. Where each one belongs, if it is ever built,
  is in the section above.

## Where shipped work is recorded

Former GitHub issues #1 through #34 and #36 through #38 are implemented, including #13, the divider banners. The [migration ledger](context/github-issue-migration-ledger.md) has one row per issue. Do not reopen them.

Retired plans and issues are tombstoned in [decisions](context/decisions.md). There is no `docs/archive/` folder. Retired files stay in git history.

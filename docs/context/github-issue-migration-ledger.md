---
Status: active
Owner: CT
Created: 2026-07-19
Last verified: 2026-07-19
Kind: context
---

# GitHub issue migration ledger

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** tracing a former GitHub issue, its archive digest,
  implementation evidence, or migration classification.
- **Search terms:** GitHub issues, migration ledger, issue deletion,
  archive digest, cutover, #NNN, ec3979f.

## Purpose

All **37** former GitHub issues for `pdomain/pdomain-ocr-simple-gui`
(#1–#34, #36–#38; no #35) were permanently deleted from GitHub on
2026-07-17 after a non-conforming cutover. This ledger is the durable
one-row-per-issue reconciliation required by the shared-devtools
migration runbook. It replaces the incorrect claim in the 2026-07-17
roadmap that the issues were closed without implementation.

## Provenance sources

1. **Verbatim archive (primary text):** committed then removed —
   `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`
   (removal commit `7f3be6b`). Full-file SHA-256:
   `53dbaa82fac75e311a03710360f2aa403b51099cd6e6c58e9f67aa8aa4a8b4ca`.
2. **Archive section digests:** SHA-256 of each `## #N` section in that
   file (recomputable; not the original live GitHub API export digest).
3. **Code and git evidence** on current `master` (re-verified 2026-07-19).
4. **Cross-repo open work** remains on
   `ConcaveTrillion/ocr-container-meta` (#395–#398) and is **not**
   re-created as GitHub issues in this repository.

## Classification rules

- Do **not** treat GitHub `closed` / `COMPLETED` as implementation proof.
- **Implemented** requires present-tense code or tests (and usually a fix commit).
- **Active** means residual product or style work still open.
- Comments in the archive that only restate the body are disposable chatter.

## Reconciliation

| # | Former URL | Archive section digest | Outcome | Governed destination | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | [1](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/1) | `ec078cdbc5c683653c37ec59cb8a1dd7610b5b7fd56ebaa48fba6fe7a4e823f1` | Implemented | runtime-flows; pages route | `d847e01`; `routes/pages.py` reruns inline with correct page_idx |
| 2 | [2](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/2) | `e05d9c5bb7a91ce6c54a6e63dbea8bbc54c9b7d9d34968465579378ed5fc1569` | Implemented | runtime-flows; pages route | `d847e01`; single-file `source_path` branch in `get_page_image` |
| 3 | [3](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/3) | `0cbee5fb46e44a896ca8d5fb19b5a63758d836ab604f2296954bf11fa7bf17a3` | Implemented | results behavior spec; frontend | `6761dd4`; ResultsPage uses ProjectStatus-shaped fields |
| 4 | [4](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/4) | `e8fecc32797d410eeafcfffdc13e38625d52f6d298493f5e4eea5ef6a2de7996` | Implemented | results behavior spec; frontend | `6761dd4`; `page_name` on page rows |
| 5 | [5](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/5) | `40d1b3afa76bfccf5f96ba5600abfbfb3c7edd63969b779fab51517981b47a7e` | Implemented | page-view behavior spec; frontend | `6761dd4`; PageData matches PageResponse |
| 6 | [6](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/6) | `4fff9d71793b587953c3efc790d6bec6d53855484ea18b505e9d213e0ed7544f` | Implemented | home behavior; JobConfigInline | `04e42a9`; default language `en` |
| 7 | [7](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/7) | `336e95ef33286d1fc601e4c8b88c18cdeaba15fa1b032f53967b23e2f38d5c91` | Implemented | Makefile ci target | `73f724b`; `make ci` includes `frontend-test` |
| 8 | [8](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/8) | `096ebe181f8cfe3d109da9ef3f38a526c65a0a60b877f219e196788298d18046` | Implemented | Makefile ci target | `73f724b`; `make ci` includes `pre-commit-check` |
| 9 | [9](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/9) | `148226b20fa1e28810a4d5581124f619d2532d5c0199b1184a82e81a63b9899e` | Implemented | module-map; app factory | `04e42a9`; StaticFiles mounted inside app factory |
| 10 | [10](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/10) | `b86877ed21b3dd0219ff4a8250485f9e305dcfe713a5b980dacb1694e917893b` | Implemented | runtime-flows; pages route | `d847e01` + timeout bound; residual thread leak → meta#397 |
| 11 | [11](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/11) | `0398698bf3008b670a54649057fb2b175ad1a1f2dbe41d7403c37b7e21f2f4c7` | Implemented | runtime-flows; jobs route | `bbd40d6`; `POST /api/jobs` returns 202 |
| 12 | [12](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/12) | `2f6165669b2ab61c032a2074d5e39f5ab912cdc075fc53cf6b9451bfef1277f3` | Implemented | runtime-flows; route handlers | `bbd40d6`; `response_model=` on handlers |
| 13 | [13](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/13) | `dc65ba5589a102bb297a771108f45800191cda07145b992babf3112c3a16dfb8` | Active (residual) | roadmap (style debt) | Commit `fd83a28` claimed removal; `# ---` dividers remain in `tests/e2e/` |
| 14 | [14](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/14) | `278c4713335dd40bd25247d9931bfbc9e04ca66c81c3a76bbe7330154f50eead` | Implemented | process/lint-deviations.md | `663f252`; catalog present |
| 15 | [15](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/15) | `fcade8f5b8616dda7aca92f5e0748f8382bfc45f78cd9854e4c302a161eee575` | Implemented | frontend package; architecture | `9cd1378` lineage; `@pdomain/pdomain-ui` ^0.11.0 |
| 16 | [16](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/16) | `f75720cbdffcc055b1cb84b7c1e733db5a4bcf8d1ea5f0578604b89417653b94` | Implemented | runtime-flows; storage validate_project_id | `9afd500` |
| 17 | [17](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/17) | `66574b4211c64924c54fff0795da292bc35da39366fe17e1feb624f086103241` | Implemented | runtime-flows; source allowlist | `ac3577a` |
| 18 | [18](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/18) | `09386cecb2e9fc0ce407221961406c40965e3611a8dc6b92d022e268321b1a4f` | Implemented | architecture; auth + concurrent jobs | `e9aac52` |
| 19 | [19](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/19) | `d63c446ff75fc0bac921a726e81c989cfe4ebfb6a645328aeb9b7bbf791b4f5e` | Implemented | architecture; suite token middleware | `e9aac52` + suite middleware hardening |
| 20 | [20](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/20) | `b9cef82bd768fa680634df9be54f16683a5a876ff81fe2ace954635195ef84b7` | Implemented | frontend Vite pin | `4d1f68f`; vite ^7.3.6 |
| 21 | [21](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/21) | `c3ca6991afce6a143fdb4320641c76b391e9d6b4e9983613430dfa47c06bf94d` | Implemented | frontend Vite toolchain | `4d1f68f` |
| 22 | [22](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/22) | `f7738b5c6a1b7800fe673c33750527924624d16dca680e1e2c21ea044003a17d` | Implemented | uv.lock hashes; pdomain-index | `c9c9fc4` / lockfile hashes |
| 23 | [23](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/23) | `b83be35216c491fa86b1b032681d49638771465868a03d5897235dd493d53961` | Implemented | architecture; require_token on prefs/metadata | `e9aac52` |
| 24 | [24](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/24) | `7d7386f89c4cfe92303fb4f41b8c593e54bb7a00a360093858113195e32a45a9` | Implemented | self-hosted @fontsource fonts | `5d3cbc7`; main.tsx imports |
| 25 | [25](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/25) | `6d68e2c3514965b43f21b98917d76297b00594d671bddf35aaf67eb03bc33454` | Implemented | results download UI | `8091b72`; API download + clipboard path, no file:// open |
| 26 | [26](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/26) | `778ce07050501a2bbfe6ae98b6ec8bab9a192db59559950ca79fa9996cbce5ef` | Active / blocked upstream | docs/issues/2026-07-19-gh-026-…; intent-map | `5c6f052` boundary note; shared window.open still upstream |
| 27 | [27](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/27) | `9a8c1144436864f8285988a7ad6e76b1ef8f825687fd03e0754c002037f29659` | Implemented | pyproject pdomain-ops pin | `218b152` lineage; `pdomain-ops>=0.11.1` |
| 28 | [28](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/28) | `7779ff41553faa7b0bbcbbc9e3948577bf8cfbc71bc5170a30d511729ed67a1b` | Implemented | GitHub Actions SHA pins | `398ed04`; ci.yml uses commit SHAs + uv version |
| 29 | [29](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/29) | `99db382ffd74edc7cd00038d38e7856a3e6924328c54ca079b106ae5ac644ea3` | Implemented | `app/__main__.py` logging | `4bf9440`; logger.exception on unregister |
| 30 | [30](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/30) | `aae731449eb786d9429c2076095d5a9536bbd49999fd05d3b89ddcca366ad944` | Implemented | app startup logging | `4bf9440`; registration failures logged |
| 31 | [31](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/31) | `7848b4c80fb1f0742c0ab31dda0b7d19713a78ed7dcdd27c29921c14e424b42f` | Implemented | app suite mount logging | `4bf9440` |
| 32 | [32](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/32) | `749a70d4c4f82264c34671904e494160dc9a292e8802e6b25645dab54cd26bd6` | Implemented | jobs failure persistence logging | `4bf9440` |
| 33 | [33](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/33) | `a550171b00d03e05925fbf9aee5d5aef4add61a7640c0e535164fc1c598e51c4` | Implemented | prefs/recent-projects logging | `4bf9440` |
| 34 | [34](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/34) | `709d7fba7d60d60e3a82534b2eb8a7292bc1feffc39380e5576d0f07b2b23ba1` | Implemented | storage listing logging | `4bf9440`; unreadable dirs logged |
| 36 | [36](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/36) | `2bfbdb92f2717c9d6b8b3f324903d0f78420ebfca364ce5a8b6cf56b454e15b1` | Implemented | app FAKE_DISPATCHER warning | `73cf193` |
| 37 | [37](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/37) | `53aff7f548e9c63274ccdb0cb4545ea03ab9b22a89548ccd8f8ef722c69c5023` | Implemented | e2e conftest guard tests | `db544d8`; `test_e2e_conftest_guard.py` |
| 38 | [38](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/38) | `c897b192e5ac062353802c0fbba24c7fefe9ae65c80f9a0f4451976d25db524f` | Implemented | fake_dispatcher isinstance path | `e15ea6d`; getattr retained only for untyped test stubs |

**Row count:** 37 (must match open+closed inventory at deletion time).

## Coverage notes

- **#26** remains the only former issue with an active governed issue
  document: [suite launcher opener isolation](../issues/2026-07-19-gh-026-suite-launcher-opener-isolation.md).
- **#13** is residual style debt (divider banners reappeared or were never
  fully cleared in `tests/e2e/`). Tracked on the [roadmap](../roadmap.md);
  not worth a full issue report.
- **#10** fixed event-loop blocking for the await path; the detached
  executor-thread / `_predictor_cache` race is tracked as
  [ocr-container-meta#397](https://github.com/ConcaveTrillion/ocr-container-meta/issues/397).
- **#38** uses `isinstance(OcrBatchRequest)` for production-shaped requests;
  `getattr` remains only for untyped test stubs.
- Deferred product work that was **never** in this 37-issue set (download
  truth, multilingual profiles, cancellation UI, config dedupe, Settings
  token field) lives in [intent-map](intent-map.md) and/or meta issues.

## Cutover status

| Gate | Status |
| --- | --- |
| Verbatim archive in Git history | Done (`ec3979f`) |
| GitHub issues deleted | Done (API totalCount 0; GraphQL cannot resolve #1–#38) |
| Completed-issue ledger (this file) | Done (2026-07-19 repair) |
| Active governed issue for residual #26 | Done |
| Roadmap reclassified vs code | Done (2026-07-19) |
| `docs/issues` template bundle | Done |
| GitHub Issues feature disabled | **Not done** (owner chose to leave enabled) |
| Append-only deletion journal with node IDs | Not reconstructed (no live node IDs after deletion) |

## Related documents

- [Current state](current-state.md)
- [Intent map](intent-map.md)
- [Roadmap](../roadmap.md)
- [Issues index](../issues/README.md)
- Architecture: [overview](../architecture/00-overview.md),
  [runtime flows](../architecture/runtime-flows.md)

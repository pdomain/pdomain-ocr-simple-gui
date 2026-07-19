---
Status: active
Owner: CT
Created: 2026-07-19
Last verified: 2026-07-19
Kind: context
---

# GitHub issue deletion journal

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** auditing permanent deletion of migrated GitHub issues or
  verifying tracker absence after cutover.
- **Search terms:** deletion journal, deleteIssue, GitHub issues deleted,
  node ID, cutover verification, migration journal.

## Purpose

Append-only record of permanent deletion (or verified prior deletion) of
migrated GitHub issues for `pdomain/pdomain-ocr-simple-gui`. Companion to
[the migration ledger](github-issue-migration-ledger.md).

## Method notes

- **Original deletion window:** 2026-07-17 (commits `ec3979f` archive +
  `7f3be6b` archive removal; issues removed from the tracker the same day).
- **This journal:** reconstructed 2026-07-19 because the 2026-07-17 cutover
  did not write a runbook-compliant journal before `deleteIssue`.
- **Node IDs:** only #26 was retained in an earlier unmerged worktree note
  (`I_kwDOShaXL88AAAABDI7UbA`). Other GraphQL node IDs are **not recoverable**
  after permanent deletion; rows mark `node_id` as unavailable.
- **Digests:**
  - `archive_section_digest` — SHA-256 of the `## #N` section in
    `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`
    (recomputable).
  - `prior_export_digest` — SHA-256 of the pre-deletion GitHub API export
    bundle from the 2026-07-15 migration worktree ledger (not re-exportable).
- **Actor (original deletion):** repository admin `ConcaveTrillion` (inferred
  from archive authorship and admin access; exact `deleteIssue` audit actor
  not re-fetched).
- **GitHub Issues feature:** left **enabled** by owner choice (not disabled).

## Batch 1 — verification of prior deletion (2026-07-19)

- **Journal write timestamp (UTC):** 2026-07-19T11:00:30Z
- **Repair branch commit (pre-merge):** `076e16f` (migration repair docs).
- **Merged default-branch commit:** `0aed22680ae99064a14e1fe057eaa477db4b6c92` (PR #46).
- **API check before journal close:** GraphQL
  `repository.issues.totalCount == 0`; `gh issue list --state all` empty
  (PRs excluded). Sample GraphQL lookups for #1, #16, #26, #38:
  `Could not resolve to an issue or pull request`.
- **Action taken this session:** **none** — issues already absent; no
  additional `deleteIssue` calls required.

| # | Former URL | node_id | archive_section_digest | prior_export_digest | Destination | Deletion status | Verified absent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [1](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/1) | `unavailable (deleted before journal)` | `ec078cdbc5c683653c37ec59cb8a1dd7610b5b7fd56ebaa48fba6fe7a4e823f1` | `8fbf1f7bef588b43b3d91089be7de41326e4312b942c1417afb4c51ecd3f0852` | runtime-flows; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 2 | [2](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/2) | `unavailable (deleted before journal)` | `e05d9c5bb7a91ce6c54a6e63dbea8bbc54c9b7d9d34968465579378ed5fc1569` | `24f930aa581d4eef7bb6076d2672e23358f89357539d5e4e591064b4a6e3c541` | runtime-flows; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 3 | [3](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/3) | `unavailable (deleted before journal)` | `0cbee5fb46e44a896ca8d5fb19b5a63758d836ab604f2296954bf11fa7bf17a3` | `0d4f9f7626949ae0583b401e35289a8e0619e3a399ff64d0de1acc48fbfa26c1` | results FE; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 4 | [4](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/4) | `unavailable (deleted before journal)` | `e8fecc32797d410eeafcfffdc13e38625d52f6d298493f5e4eea5ef6a2de7996` | `6fb0d2300fd31976ca43a840d52c7c136148dfb9cf8c8bb5fa640f4e8371656d` | results FE; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 5 | [5](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/5) | `unavailable (deleted before journal)` | `40d1b3afa76bfccf5f96ba5600abfbfb3c7edd63969b779fab51517981b47a7e` | `d84e23efce7aa9a7bcb951f8326ddd7e16fb8e034b6fcfc0df7250fbf53ee7d9` | page-view FE; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 6 | [6](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/6) | `unavailable (deleted before journal)` | `4fff9d71793b587953c3efc790d6bec6d53855484ea18b505e9d213e0ed7544f` | `058da03692a01d32baa91c93bae6b4140eb4b4302cfe9f706028d4bbe8971f85` | JobConfigInline; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 7 | [7](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/7) | `unavailable (deleted before journal)` | `336e95ef33286d1fc601e4c8b88c18cdeaba15fa1b032f53967b23e2f38d5c91` | `429bd44af0430ecb9c2a40bfb5818761fdec02d2ed64e4ff90be5045bdf8471a` | Makefile ci; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 8 | [8](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/8) | `unavailable (deleted before journal)` | `096ebe181f8cfe3d109da9ef3f38a526c65a0a60b877f219e196788298d18046` | `0b07bcc3283b338585f74068137e124f154c441cee3a755664dc8b5e091541e5` | Makefile ci; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 9 | [9](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/9) | `unavailable (deleted before journal)` | `148226b20fa1e28810a4d5581124f619d2532d5c0199b1184a82e81a63b9899e` | `c48a8a88f6b42f23e3fabb486191a39f4ab63c3e38436f5ed0d39d6c76ad18d0` | app factory; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 10 | [10](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/10) | `unavailable (deleted before journal)` | `b86877ed21b3dd0219ff4a8250485f9e305dcfe713a5b980dacb1694e917893b` | `0ef6efd341d8fc642f2895c8caee8c506282b7b89e4c15cd27aec6377aeeaaa1` | pages route; implemented (meta#397 residual) | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 11 | [11](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/11) | `unavailable (deleted before journal)` | `0398698bf3008b670a54649057fb2b175ad1a1f2dbe41d7403c37b7e21f2f4c7` | `8229c050e15a96839bdad819de2852a4befdd6c91de6b88f6c36980b1600126b` | jobs 202; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 12 | [12](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/12) | `unavailable (deleted before journal)` | `2f6165669b2ab61c032a2074d5e39f5ab912cdc075fc53cf6b9451bfef1277f3` | `724c5aa811d95f502c0afde29b4a1d9b96258d757dca8908a1d4411b8e6a89c3` | response_model; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 13 | [13](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/13) | `unavailable (deleted before journal)` | `dc65ba5589a102bb297a771108f45800191cda07145b992babf3112c3a16dfb8` | `9087034d8453e6c9eda73674feabae1620e8cf6e1ce9729e08bee526d59dbcf3` | roadmap residual style | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 14 | [14](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/14) | `unavailable (deleted before journal)` | `278c4713335dd40bd25247d9931bfbc9e04ca66c81c3a76bbe7330154f50eead` | `ca640ac99c9f09d26aa16933a191817fcdf217366a06a43e0b2082e2b1ca474b` | lint-deviations; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 15 | [15](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/15) | `unavailable (deleted before journal)` | `fcade8f5b8616dda7aca92f5e0748f8382bfc45f78cd9854e4c302a161eee575` | `4d67712ce23a0286e015f8b8589f9500825420bfb0a2410658e0fd81cf1d1330` | pdomain-ui; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 16 | [16](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/16) | `unavailable (deleted before journal)` | `f75720cbdffcc055b1cb84b7c1e733db5a4bcf8d1ea5f0578604b89417653b94` | `574d7fe451058c0bc60deb28d3c85dd5735e1b8c51943f98360d3d7be2f1bd39` | validate_project_id; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 17 | [17](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/17) | `unavailable (deleted before journal)` | `66574b4211c64924c54fff0795da292bc35da39366fe17e1feb624f086103241` | `a22d9b245e696d725648db1705d564c1f432d31d4cd2a66fbd4f2e4d06d26d41` | source allowlist; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 18 | [18](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/18) | `unavailable (deleted before journal)` | `09386cecb2e9fc0ce407221961406c40965e3611a8dc6b92d022e268321b1a4f` | `7b4535cf060935ec3c58f2e5559067e8b6dfdcabff8ee8a4a1d9861ca0f7d048` | auth + caps; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 19 | [19](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/19) | `unavailable (deleted before journal)` | `d63c446ff75fc0bac921a726e81c989cfe4ebfb6a645328aeb9b7bbf791b4f5e` | `b6841a22dfea951bcd395475d4991b737fb30964d1034d6cafbe00dfa0d8f100` | suite auth; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 20 | [20](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/20) | `unavailable (deleted before journal)` | `b9cef82bd768fa680634df9be54f16683a5a876ff81fe2ace954635195ef84b7` | `d58c94283e654cd859ee66c321ef525a11e74eb27a394b9e74694e15048ba4da` | Vite pin; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 21 | [21](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/21) | `unavailable (deleted before journal)` | `c3ca6991afce6a143fdb4320641c76b391e9d6b4e9983613430dfa47c06bf94d` | `a8a4a84a5692e7e5f10f7b944639ea6d8af0668fda0af6796ea6ed5ea0f2912a` | esbuild via Vite; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 22 | [22](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/22) | `unavailable (deleted before journal)` | `f7738b5c6a1b7800fe673c33750527924624d16dca680e1e2c21ea044003a17d` | `eeb76c67e8bfa4d361abf77463188c8df4554ec2d59a22917bdf18875bc08d9d` | uv.lock hashes; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 23 | [23](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/23) | `unavailable (deleted before journal)` | `b83be35216c491fa86b1b032681d49638771465868a03d5897235dd493d53961` | `023d8439f85a8cd6ea5ebcc6ad5b3ebe2cfb005f97ec38eddced290a97ae8ddf` | prefs auth; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 24 | [24](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/24) | `unavailable (deleted before journal)` | `7d7386f89c4cfe92303fb4f41b8c593e54bb7a00a360093858113195e32a45a9` | `e7ac8e56e87a8dfc69a279e89c250f09dc6f2db3e1703c6bcaeab3f93de635fe` | self-hosted fonts; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 25 | [25](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/25) | `unavailable (deleted before journal)` | `6d68e2c3514965b43f21b98917d76297b00594d671bddf35aaf67eb03bc33454` | `143cb40e6671ae79beedbae5cd12f75aeda88f4d9507e40d1c50cdcd48f35584` | download UI; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 26 | [26](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/26) | `I_kwDOShaXL88AAAABDI7UbA` | `778ce07050501a2bbfe6ae98b6ec8bab9a192db59559950ca79fa9996cbce5ef` | `d30b594428e206e67e57c76700e7d7ce5388ab6a557cb271da39d86b171b352e` | docs/issues/2026-07-19-gh-026-…; active | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 27 | [27](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/27) | `unavailable (deleted before journal)` | `9a8c1144436864f8285988a7ad6e76b1ef8f825687fd03e0754c002037f29659` | `652ccbf127cfcfade024f35f8bbbb9652c5ee76d707ac1d6f2d0d12f4db5c0ae` | pdomain-ops pin; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 28 | [28](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/28) | `unavailable (deleted before journal)` | `7779ff41553faa7b0bbcbbc9e3948577bf8cfbc71bc5170a30d511729ed67a1b` | `07d9af9ebe4284d2e2d855569e436263932545481df694734afb5e5e5641d4a9` | Actions SHA pins; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 29 | [29](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/29) | `unavailable (deleted before journal)` | `99db382ffd74edc7cd00038d38e7856a3e6924328c54ca079b106ae5ac644ea3` | `386b016818d23b1bcd685a887a304d05e33320123aeffc5cad505cbf4ecbe6f6` | logging; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 30 | [30](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/30) | `unavailable (deleted before journal)` | `aae731449eb786d9429c2076095d5a9536bbd49999fd05d3b89ddcca366ad944` | `07bf827fd2520cdc9d284d06cb23953121510eb1ed1f3fab646679b7a5d4f3b0` | logging; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 31 | [31](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/31) | `unavailable (deleted before journal)` | `7848b4c80fb1f0742c0ab31dda0b7d19713a78ed7dcdd27c29921c14e424b42f` | `a14d9bdb91e8ffd0b4cd285b6bd1548cb25a77800d19d3aadd87163c37d3705a` | logging; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 32 | [32](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/32) | `unavailable (deleted before journal)` | `749a70d4c4f82264c34671904e494160dc9a292e8802e6b25645dab54cd26bd6` | `ea9bafa0bc432cf1cac5d25093ce98275c5b771cb7496d26d58b3609a62a5fa6` | logging; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 33 | [33](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/33) | `unavailable (deleted before journal)` | `a550171b00d03e05925fbf9aee5d5aef4add61a7640c0e535164fc1c598e51c4` | `dca23adc2baf70e25ddc2c37c4a6bd72650eb5b39135a1790f637351ef9e41ab` | logging; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 34 | [34](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/34) | `unavailable (deleted before journal)` | `709d7fba7d60d60e3a82534b2eb8a7292bc1feffc39380e5576d0f07b2b23ba1` | `0e4ebffc143e49b039e0ec189b7cd022084e7fa0d662149894d5a147aaefbcb7` | logging; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 36 | [36](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/36) | `unavailable (deleted before journal)` | `2bfbdb92f2717c9d6b8b3f324903d0f78420ebfca364ce5a8b6cf56b454e15b1` | `4ed442b9e8f430c2fa9da54fe84cc94925db49e5f47fc6be43c4c8f5a48fd18f` | FAKE_DISPATCHER warn; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 37 | [37](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/37) | `unavailable (deleted before journal)` | `53aff7f548e9c63274ccdb0cb4545ea03ab9b22a89548ccd8f8ef722c69c5023` | `55ca4564cbcb048b3114f9f6d45026280a0a1b444860ec4f969279b8826fa881` | e2e prefs guard; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |
| 38 | [38](https://github.com/pdomain/pdomain-ocr-simple-gui/issues/38) | `unavailable (deleted before journal)` | `c897b192e5ac062353802c0fbba24c7fefe9ae65c80f9a0f4451976d25db524f` | `3a2d1b06c0dfaa02bd618a7516f7fb2da462dc32153cfa53140e509b3c018528` | fake_dispatcher isinstance; implemented | deleted 2026-07-17 (prior cutover) | yes (API 2026-07-19) |

**Row count:** 37 (must equal migration inventory).

## Append-only log

- `2026-07-19T11:00:30Z` — Batch 1 verified: 0 issues remain on GitHub; 37 journal rows
  recorded; Issues feature left enabled; no disable step.
- `2026-07-19T11:05:58Z` — PR #46 merged to `master` as `0aed22680ae99064a14e1fe057eaa477db4b6c92`. Re-checked API:
  `issues.totalCount == 0`; no residual issues to delete. Issues feature remains enabled.

## Related

- [Migration ledger](github-issue-migration-ledger.md)
- [Issues index](../issues/README.md)
- Archive tombstone: `git show ec3979f:docs/decisions/2026-07-17-closed-issues-archive.md`

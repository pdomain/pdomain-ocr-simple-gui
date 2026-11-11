---
kind: archive
status: retired
created_at: "2026-11-11T08:53:05Z"
owner: "CT"
branch: "fix/word-overlay-flake"
scope: "word-overlay-flake"
worktree: "/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/word-overlay-flake"
base_commit: "60020aa"
supersedes: "2026-11-11-032238-doc-recheck-bug-fixes-ready-for-review.md"
handoff_reason: "stopping"
host: "claude-code"
created: "2026-11-11"
last_verified: "2026-11-11"
---

# Word overlay flake fixed

> **Retired — superseded by `docs/handoff/2026-11-11-092702-two-e2e-flakes-fixed.md`.**

## Goal

Fix the flaky e2e test `test_word_overlays_render_from_sidecar` on a branch made from the unmerged `fix/doc-recheck-bugs`.

## Done

- The test now waits until the canvas reports at least one word, with `expect(...).to_have_attribute("data-word-count", <regex for 1 or more>)`, instead of reading the attribute once. Commit `60020aa` on `fix/word-overlay-flake`.
- Cause confirmed: the canvas wrapper renders with `data-word-count="0"` once the page loads, and the `/words` fetch fills it in later (`frontend/src/pages/PageViewPage.tsx`, the `wordBboxes` state). A temporary repro that delayed `/words` by 1.5 s made the old one-shot read fail every time and the new wait pass. The repro file was deleted.
- Repeated runs: the test passed 30 of 30 times alone, and passed in all 20 runs of the full e2e suite under `-n auto` (124 tests each).
- `make ci AI=1` exited 0 on the committed tree, read from `$?` with no pipe, with the GPU hidden and `TMPDIR` on the work drive.
- `docs/context/current-state.md` now records the fix and the two remaining flakes below.

## Not done

- Two of the 20 suite runs failed on other tests, which were left alone because they were out of scope:
  - `tests/e2e/test_flows.py::test_upload_ocr_download_flow` asserted `succeeded` but got `running`. It reads the job state once, as soon as page rows appear. This is the same one-shot-read pattern and likely needs a poll on the job state.
  - `test_zoom_out_decreases_zoom` failed and `test_zoom_out_clamps_at_floor` errored in the `reset_prefs` fixture with `Connection refused`, so that xdist worker's live server was gone. The cause was not investigated.
- `test_word_overlays_empty_when_words_404` reads `"0"` right after the canvas appears. It cannot flake, but it would also pass before the 404 arrives, so it proves little. A wait on the routed `/words` response would make it meaningful.
- Neither `fix/doc-recheck-bugs` nor this branch is merged. This branch carries all of `fix/doc-recheck-bugs` plus one commit.

## Failed approaches

- None for this fix.

## Decisions

- Kept the change to the one named test; the other flakes are recorded rather than fixed.
- Open for the owner, carried from the superseded handoff: whether the app should delete old `.viewer.png` and `.viewer.webp` files already in users' source folders.

## State

Worktree clean at `60020aa` plus this handoff commit. Nothing was pushed, merged, tagged, released or deployed. All work ran on CPU with `CUDA_VISIBLE_DEVICES` empty. Run logs for the repeated runs are in `/mnt/work/pdt/gui2/` (`single-*.log`, `suite-*.log`, `make-ci.out`).

## Pointers

- `tests/e2e/test_click_paths_page_viewer.py`
- `tests/e2e/test_flows.py`
- `tests/e2e/conftest.py`
- `docs/context/current-state.md`
- `docs/_archive/handoff/2026-11-11-032238-doc-recheck-bug-fixes-ready-for-review.md`

## Resume steps

1. Review `git log master..fix/word-overlay-flake`.
2. Decide whether to merge `fix/doc-recheck-bugs` and then this branch, or this branch alone, since it contains both.
3. Optionally fix `test_upload_ocr_download_flow` the same way, and investigate the lost live server in the zoom tests.

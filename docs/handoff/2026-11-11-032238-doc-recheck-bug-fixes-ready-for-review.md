---
kind: handoff
status: "active"
created: "2026-11-11"
created_at: "2026-11-11T03:22:38Z"
owner: "CT"
branch: "fix/doc-recheck-bugs"
scope: "doc-recheck-bugs"
worktree: "/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/fix-doc-recheck-bugs"
base_commit: "16289ed245902db14764a918c23289a59d117502"
supersedes: ""
handoff_reason: "user_requested"
host: "claude-code"
---

# Doc recheck bug fixes ready for review

## Goal

Fix the five bugs from the 2026-11-07 doc recheck.

## Done

- All five are fixed and committed: font size saving, the Tesseract re-run shortcut guard, viewer caches kept out of the source folder, the CUDA setup link, and the old devcontainer and owner defaults.
- `make ci AI=1` passed on the final tree: 643 unit, 234 frontend and 124 browser tests, plus the smoke test. It ran with the GPU hidden and no Playwright path set.
- The five issue records are retired and `docs/context/current-state.md` is updated. One independent review ran; its one finding was rejected because `.webp` is not an accepted page suffix.

## Not done

- The branch is not merged, so master still has all five bugs.
- The dep-refresh issue and other roadmap items are untouched.

## Failed approaches

- `test_word_overlays_render_from_sidecar` failed once on unchanged code and passed in every later run. It reads the word count too early and may fail `make ci` again. It was left alone and noted in current-state.

## Decisions

- Open for the owner: whether the app should delete old `.viewer.png` and `.viewer.webp` files already in users' source folders. The session left them because they no longer cause harm and those folders belong to users.
- The cache filter skips only the `<image name>.viewer.png` names the app wrote, so a real scan such as `notes.viewer.png` stays a page.
- Without Tesseract, Ctrl+Shift+R now triggers the browser's hard reload because a skipped shortcut does not block the key. The app sends no re-run, and the spec records this.

## State

Worktree clean at the last work commit `16289ed`. The owner paused this work on 2026-11-10 and the session's herdr tab is closed. Nothing was pushed, merged, tagged, released or deployed. All work ran on CPU with the GPU hidden. The session's last terminal output is saved in `/mnt/work/projects/pdomain/.artifacts/handoff-20261110/session-output/`. `/tmp` is a shared tmpfs that ran out of quota several times on 2026-11-10 while ten sessions ran gates. If a gate fails with a quota error, point `TMPDIR` at the work drive and rerun before suspecting the code.

## Pointers

- `docs/roadmap.md`
- `docs/context/current-state.md`

## Resume steps

1. Review `git log master..HEAD` on this branch.
2. Decide the old viewer cache question.
3. Merge when the owner asks.

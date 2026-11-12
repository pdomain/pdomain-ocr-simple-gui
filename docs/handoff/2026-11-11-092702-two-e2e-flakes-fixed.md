---
kind: handoff
status: "closed"
created: "2026-11-11"
created_at: "2026-11-11T09:27:02Z"
owner: "CT"
branch: "fix/e2e-flakes"
scope: "e2e-flakes"
worktree: "/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/.worktrees/e2e-flakes"
base_commit: "d1c8a2e"
supersedes: "2026-11-11-085305-word-overlay-flake-fixed.md"
handoff_reason: "stopping"
host: "claude-code"
---

# Two e2e flakes fixed

## Goal

Fix the two e2e flakes recorded in the `word-overlay-flake` handoff. The work is on `fix/e2e-flakes`, branched from the unmerged `fix/word-overlay-flake`. Each test must wait on a real condition, and the fixes must hold up in repeated runs.

## Done

- **Upload flow, commit `0451c26`.** `test_upload_ocr_download_flow` read the job state once, as soon as page rows appeared. The pipeline writes page results while the job is `running` and persists `succeeded` only after the combined outputs are written, in `src/pdomain_ocr_simple_gui/pipeline.py`, `run_project`. The test now polls `GET /api/jobs/{id}` until the job reaches a terminal state, then asserts `succeeded`.
  - Repro: a temporary 1.5 s sleep before `write_combined_txt` made the old test fail 5 of 5 times and the new one pass 5 of 5. The repro was removed, and `pipeline.py` matches the base.
  - The test passed 30 of 30 times alone.
- **Zoom tests, commit `630e2e0`.** The cause was a port collision between xdist workers, not the zoom code.
  - `_free_port()` closed its probe socket before uvicorn bound the port. Two workers could get the same port.
  - The second worker's uvicorn then failed to bind, but `_wait_ready` got a 200 from the first worker's server.
  - The second worker therefore ran against the other worker's data. That produced "Page not found" for its own seeded job, then `Connection refused` once the owning worker stopped its server. Both symptoms match `suite-16.log` from the previous session.
  - Fix: `_boot_server` starts uvicorn with `--port 0` and reads the bound port from uvicorn's "running on" log line with `_wait_for_bound_port`. It raises at once if the process exits first. `_free_port` is gone.
  - Regression test: `tests/test_e2e_boot_server.py` forces the old collision with a decoy HTTP server. It failed on the old code with the decoy's URL and passes now.
- **404 words test, commit `73cacdd`.** `test_word_overlays_empty_when_words_404` now waits for the routed `/words` response, asserts its 404 status, and then expects the count to be `0`. It passed 30 of 30 times alone.
- **Full suite.** The e2e suite passed in 20 of 20 runs under `-n auto`, with 124 tests passing each time.
- **Gate.** `make ci AI=1` exited 0 on the working tree that was then committed unchanged as these four commits. The status came from `$?` on the redirected command, with no pipe. The GPU was hidden with `CUDA_VISIBLE_DEVICES` empty, and `TMPDIR` pointed to `/mnt/work/pdt/gui3`.
- **Docs, commit `d1c8a2e`.** `docs/context/current-state.md` records both fixes.

## Not done

- `tests/smoke/test_e2e.py` still has its own `_free_port()` with the same release-then-bind gap. `make smoke` runs without xdist, so only another process on the machine could take the port. It was left alone. The same `--port 0` approach would close the gap.
- No `python-reviewer` pass ran on these changes.
- The merge of `fix/e2e-flakes` onto master brings in `fix/doc-recheck-bugs` and `fix/word-overlay-flake`. `tests/smoke/test_e2e.py` still reserves a port and binds it afterwards.

## Failed approaches

- `page.wait_for_function` with an `async` predicate that fetched the job API did not wait. It returned at once while the job was still `running`, because Playwright treated the pending Promise as truthy. A Python poll of the API replaced it.

## Decisions

- New basedpyright `reportPrivateUsage` warnings in `tests/test_e2e_boot_server.py` follow the existing pattern in `tests/test_e2e_conftest_guard.py`. `make typecheck` covers only `src/` and `installer/`, and no suppression comments were added.
- Open for the owner, carried forward: should the app delete old `.viewer.png` and `.viewer.webp` files already in users' source folders?
- Open for the owner: merge order for the three stacked branches.

## State

The worktree is clean at `d1c8a2e` plus this handoff commit. Nothing was pushed, merged, tagged, released or deployed. All work ran on CPU. Logs are in `/mnt/work/pdt/gui3/runs/`: `flow-*.log`, `suite-*.log` and `w404-*.log`. The gate output is in `/mnt/work/pdt/gui3/make-ci.out` and `/mnt/work/pdt/gui3/make-ci.exit`.

## Pointers

- `tests/e2e/conftest.py`
- `tests/test_e2e_boot_server.py`
- `tests/e2e/test_flows.py`
- `tests/e2e/test_click_paths_page_viewer.py`
- `tests/smoke/test_e2e.py`
- `src/pdomain_ocr_simple_gui/pipeline.py`
- `docs/context/current-state.md`

## Resume steps

1. Review `git log master..fix/e2e-flakes`.
2. Decide how to merge the three stacked branches. Merging `fix/e2e-flakes` alone brings in all three.
3. Optionally apply the `--port 0` fix to `tests/smoke/test_e2e.py`.

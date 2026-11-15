---
kind: handoff
status: "active"
created: "2026-11-15"
created_at: "2026-11-15T00:54:06Z"
owner: "CT"
branch: "master"
scope: "gui-port-fix-walkthrough-video"
worktree: "/mnt/work/projects/pdomain/pdomain-ocr-simple-gui"
base_commit: "e7220fafcc2929e8be2e2076a218838a78265b3f"
supersedes: ""
handoff_reason: "user_requested"
host: "claude-code"
---

# GUI port fix and walkthrough wait to merge; TTS and video are next

## Goal

Ship two fixes to pdomain-ocr-simple-gui's port selection, a user walkthrough with screenshots, and
then a computer-voiced walkthrough video. The video uses local text-to-speech that
local-generation-services is setting up. Both GUI branches are local only: nothing is merged or
pushed.

## Done

- **Book-tools pin range, released 2026-11-14.** CLI v0.9.6, GUI v0.5.7, labeler-spa v0.7.2 and
  source-data v0.1.4 require `pdomain-book-tools>=0.31.3,<0.32`. The owner then declined going
  back to an exact `==` pin for releases. Keep the range.
- **Manual install tests on GitHub Actions, CLI and GUI.** `just mac-test` and `just win-test` run
  dispatch-only workflows. All four pass, and all four OCR the same 20-word page,
  `known_good_page.png`. The owner said these are not OCR quality tests, so the floor is 0.6 word
  overlap. CLI master `7bd9aef` is pushed. Last runs: CLI macOS 43650589239 and Windows
  43650591413 read all 20 words and matched the Linux output exactly.
- **Port fix, branch `fix/port-selection`.** Commits `264c27e` and `0becf88` are in worktree
  `/mnt/work/projects/pdomain/.worktrees/gui-port-selection`.
  - An explicit `--port` beats `PD_OCR_SIMPLE_GUI_PORT`, which beats 8004.
  - The GUI binds and holds the socket, then hands it to uvicorn, so another process can't take
    the port in between. The new code is in `src/pdomain_ocr_simple_gui/ports.py`.
  - A python-reviewer pass found 2 medium and 5 low issues. All 7 are fixed in `0becf88`. No
    second review has run.
  - `AI=1 just ci` passes. One earlier run failed in `e2e-fast` with read timeouts while the
    machine was heavily loaded. The suite passed alone and on the next full run.
- **Walkthrough draft, branch `docs/usage-walkthrough`.** Commit `b89a2f4` is in worktree
  `/mnt/work/projects/pdomain/.worktrees/gui-walkthrough`.
  - It adds `docs/usage/walkthrough.md` and nine screenshots in `docs/usage/images/`.
  - It adds a README "Use" section and fixes the README's uninstall data path.
  - The example page is *The Wind in the Willows*, Scribner's, 1908, printed page 4: Internet
    Archive item `cu31924028200164`, leaf n15.
  - The screenshots come from the released 0.5.7, run headless with its data kept under
    `/mnt/scratch`.
- **TTS session `lgs-tts`, still wrapping up.** It is a herdr Claude session with permission
  prompts skipped, in the new `local-generation-services` workspace, pane `w98:p1`. It has pulled
  Kokoro-82M and Qwen3-TTS: 1.7B CustomVoice, VoiceDesign and Base, and 0.6B CustomVoice. It is
  recording them in `models/`. Its brief is `/mnt/scratch/claude-pdomain-21e115b6/lgs-tts-brief.md`.
  It was asked to write `research/tts-2026-11-14/REPORT.md` and its own handoff, scope `tts-setup`,
  in local-generation-services.

## Not yet done

1. **Walkthrough review fixes.** These come from a review of `b89a2f4`.
   - **High:** step 3 must tell the reader to choose **Managed (download)**. Without it, step 8
     has no download buttons.
   - **Medium:** say how to find the job ID used in the folder paths.
   - **Medium:** explain OCR, terminal, GiB, JSON and the `pkill` line in plain words.
   - **Medium:** add a screenshot of the Jobs panel.
   - **Low:**
     - Check "Next to source" in the app.
     - Soften the timing wording.
     - Match the page-view button glyph to the screen.
     - Thin out the download table.
   - Check that closing the tab does not stop the app. Ctrl+C stopping it cleanly is confirmed.
   - Then run the `readability-editor` pass, the frozen-region check and full `AI=1 just ci`.
   - Rename the commit. It is titled "draft", because gitlint rule T5 rejects "WIP".
2. **Merge both GUI branches.** Expect a small README conflict: both branches edit the Launch
   paragraph. The port branch owns the port wording, and the walkthrough branch removed the stale
   usage sentences. Merging needs `AI=1 just ci`. Pushing and a GUI v0.5.8 release need the
   owner's say-so.
3. **The same port bugs in sibling repos, not fixed.** The owner hasn't decided yet.
   - pdomain-ops: `bootstrap_spa` lets the env var override, and `find_available_port` probes and
     then closes.
   - pdomain-ocr-trainer-spa has both bugs.
   - pdomain-ocr-labeler-spa has the bind race and may already handle the explicit port.
4. **Video.** Nothing has started. It needs the owner to pick a voice from the `lgs-tts` samples.
   It will use the narration script and the Playwright driver, both under `/mnt/scratch` (see
   Pointers). Record with Playwright's video recording, headless, add TTS per step, and join with
   ffmpeg, which is installed. Where to publish it is not decided; it is too big for git.
5. **App bugs the walkthrough agent found, not filed.**
   - The "images + text" zips contain no images.
   - Recent projects shows a finished job as 0 pages and "queued".
   - Delete has no confirmation and leaves uploaded copies behind.
   - The progress text names `~/.cache/huggingface` instead of `~/.cache/doctr`.
   - In Settings, the colour fields render black, Density is cut off, and the Jobs path is cut off.
   - There is no Quit button. A desktop-shortcut launch has no visible way to stop the app.
   - An explicit `--port 8030` quietly started on 8031 while the old process still held 8030, and
     nothing was logged. The port fix keeps "walk upward" for explicit ports. Decide whether an
     explicit port should fail or at least log the move.

## Failed approaches

- **Shared /tmp ran out of inodes twice.** Agents stopped because every Claude Code shell command
  writes its output under `/tmp/claude-1000`. Moving an agent's files to `/mnt/scratch` did not
  help. The cause was the omarchy-auth-prompts pytest runs: `-n 4`, basetemp `/tmp/x.*`, plus about
  140,000 files in `/tmp/pytest-of-ntw` and 144,000 in `/tmp/authpt`. That is not this session's
  to clean.
- **The 8-word title page, then a 372-word book page, as the CLI install-test fixture.** The 8-word
  page failed at 0.875 over one misread word. The book page was dropped once the owner said these
  are not quality tests.
- **Overriding HOME breaks uv's settings.** The walkthrough agent's first launch set `HOME` to
  scratch with a wrong `UV_CACHE_DIR`. It downloaded about 18 GB, mostly CUDA PyTorch, again into
  `~/.cache/uv`. The real cache is `/mnt/work/caches/uv`. Nothing was deleted.

## Key decisions

- The pin range stays `>=0.31.3,<0.32`. The owner said no to a release-time `==` pin.
- The install-test workflows are `workflow_dispatch` only, under the 2026-09-13 rule that nothing
  runs on GitHub automatically.
- The TTS pick for narration is Kokoro-82M: Apache 2.0, runs on CPU, so it doesn't compete with
  ComfyUI. Qwen3-TTS covers voice design and cloning. Chatterbox (reported unmaintained) and
  models with research-only licences were ruled out.

## Current state

- GUI master `e7220fa` and CLI master `7bd9aef` are clean and pushed. No processes from this
  session are running. The GUI on 8014 was stopped by PID.
- The worktrees `gui-port-selection`, `gui-walkthrough` and `gui-handoff` (the one this handoff is
  written in) all exist.
- `lgs-tts` may still be running in herdr. Read it with `herdr agent read lgs-tts --source
  recent-unwrapped --lines 80`.

## Pointers

- `/mnt/work/projects/pdomain/.worktrees/gui-port-selection` (branch `fix/port-selection`)
- `/mnt/work/projects/pdomain/.worktrees/gui-walkthrough` (branch `docs/usage-walkthrough`)
- `/mnt/scratch/claude-pdomain-21e115b6/walkthrough/walkthrough-script.md`: narration, one spoken
  paragraph per step, with the exact Playwright actions
- `/mnt/scratch/claude-pdomain-21e115b6/walkthrough/scripts/drive_walkthrough.py`: Playwright
  driver; run it with `--with playwright==1.65.1`
- `/mnt/scratch/claude-pdomain-21e115b6/walkthrough/scripts/start-app.sh`: launches 0.5.7 on 8030
  with HOME, TMPDIR and the uv paths pinned
- `/mnt/scratch/claude-pdomain-21e115b6/walkthrough/ia/wind-in-the-willows-p004.jpg`
- `/mnt/scratch/claude-pdomain-21e115b6/walkthrough/final`: full-colour shots, screen text, the
  two downloaded zips
- `/mnt/scratch/claude-pdomain-21e115b6/lgs-tts-brief.md`
- `/mnt/work/projects/local-generation-services/research/tts-2026-11-14/`: TTS report, samples
  and `sources.tsv`
- `scripts/windows_acceptance.py`: working selectors for the whole GUI flow
- `.github/workflows/macos-install.yml`, `.github/workflows/windows-install.yml`,
  `scripts/install-test.sh`

## Resume steps

1. Read the `lgs-tts` report and its `tts-setup` handoff in local-generation-services. Play the
   samples to the owner and get a voice choice.
2. In `gui-walkthrough`, apply the review fixes in Not yet done item 1, run the readability pass
   and `AI=1 just ci`, then amend the commit with a final title.
3. Merge `fix/port-selection`, then `docs/usage-walkthrough`, into GUI master. Resolve the README
   conflict and run `AI=1 just ci`. Ask the owner before pushing or releasing v0.5.8.
4. Build the video from the narration script and driver with the chosen voice.
5. Ask the owner about the sibling-repo port bugs and the app bugs in item 5, and whether to
   delete the 18 GB copy in `~/.cache/uv`.

## Setup & warnings

- Keep temp files off `/tmp`: set `TMPDIR`, and pytest `--basetemp`, under `/mnt/scratch`. Check
  `df -i /tmp` first. If it's above 90%, the shell can stop working with no warning.
- Run the GUI only headless or in gui-sandbox. Ports 8030 and 8031 were used for the walkthrough.
- Commit as ConcaveTrillion with the `Co-Authored-By: Claude Opus 5.5` trailer. gitlint allows a
  title of at most 72 characters, body lines of at most 100, and no "WIP" in the title.
- Don't set `UV_CACHE_DIR` to `~/.cache/uv`. The machine cache is `/mnt/work/caches/uv`.

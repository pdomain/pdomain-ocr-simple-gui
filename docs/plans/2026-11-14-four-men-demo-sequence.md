---
Status: draft
Owner: CT
Created: 2026-11-14
Last verified: 2026-11-14
Kind: plan
---

# Four Men OCR GUI demo sequence

Teach installation and full-book OCR through visible, step-by-step actions.
Mention the prepared source briefly, then process all 386 Four Men page images.
The full-book run on released 0.5.7 succeeded with all 386 pages. This document
records the sequence and runtime evidence, while remaining a draft for owner
review. The original PGDP files and original nine screenshots remain unchanged.
The [user guide](../usage/walkthrough.md) holds the user steps; editing notes
and outstanding checks belong here.

## Agent Index

- **Kind:** plan
- **Status:** draft
- **Read when:** reviewing or preparing the Four Men OCR GUI demonstration.
- **Search terms:** Four Men, Belloc, walkthrough, IA, demo, prepared pages.

## Goal

Show installation and launch, then teach full-book input, Managed output,
engine and device choice, progress, results, correction, downloads and Jobs.
End by stopping the app. Mention source preparation briefly before page input.

## Architecture

The tutorial follows installation, launch, prepared-page input, configuration,
processing, review, correction and export. Preparation stays outside the video.
The producer records visible pointer actions and matches narration to each step.
Application code remains unchanged. Capture and narration tools live in isolated
scratch storage; no generic LGS tool was changed.

## Tech Stack

Use released OCR Simple GUI 0.5.7, a terminal, and a browser inside gui-sandbox.
Use text installation cards for Linux, macOS and Windows, then visible pointer actions. The archive source
appears only in the brief preparation mention and source credit.

Use Kokoro-82M `af_heart` at speed 0.9 for this revision, as the owner requested.
The shared video settings remain unchanged. Pronounce “pdomain” as “P-Domain”
and “JSON” as “Jason”.
After the owner authorized execution, the narration was rendered sequentially
on CUDA after OCR stopped, using two CPU threads.

## Global Constraints

- Guide ownership is exclusive to `ocr-demo-guide`, pane `w9B:p1`, in
  `/mnt/work/projects/pdomain/.worktrees/gui-walkthrough`, branch
  `docs/usage-walkthrough`, starting at clean `b89a2f4`.
- App session `w6W:p4` owns app fixes, ports, merges and releases. Its port branch
  owns README Launch wording. Both branches remain unmerged.
- The first phase allowed only documentation and read-only inspection. Downloads,
  launches, captures, builds, installs, OCR, GPU work, TTS, rendering, merges,
  releases, pushes, video/LGS edits and media commits were excluded then.
- The owner then said “do it all”, authorizing full-book demo execution.
  Runtime files, copied inputs and capture/narration tools use isolated scratch.
  New screenshots use `docs/usage/images/four-men/`. Preserve original screenshots
  and others' edits.
- App code, ports, merges and releases stay with the app owner. Leave the guide
  staged and uncommitted. Do not push or commit media. Full app CI remains with
  the app owner because this task changes no application code. Do not prompt
  the video coordinator pane; communicate through files and the coordination log.
- Record actual results and their limits. No timing promises, invented successful
  runs, or guaranteed image-in-ZIP claims.

## Source and page selection

The saved comments at
`/mnt/work/projects/pgdp/post-processing/the-four-men/projectID674a598474ee1_comments.html`
link to [IA item fourmenfarrago00belluoft](https://archive.org/details/fourmenfarrago00belluoft).
Initial read-only inspection found a raw JP2 ZIP option under DOWNLOAD OPTIONS.
The later recorded download completed; its evidence is listed below.
IA identifies T. Nelson, London,
and Kelly - University of Toronto; its edition date is uncertain. The comments'
1912 date describes the work and is not proof of this scan's edition date.

Use all prepared page PNGs from:

```text
/mnt/work/projects/pgdp/post-processing/the-four-men/projectID674a598474ee1_images/
```

The read-only inventory found 417 immediate regular files, with no subdirectories
or empty files: 386 PNG pages and 31 JPEGs whose names all start `i_`.
The prepared page set is exactly:

- 12 front-matter PNGs: `f001.png` through `f010.png`, plus `f003b.png` and
  `f003p.png`.
- 374 further PNGs: every name from `p011.png` through `p384.png`, with no gaps.
- Exclude all 31 `i_*.jpg` files from the OCR input. An inspected `i_p013.jpg`
  is the illustration extracted from p013, not another full page. The inspected
  `i_title.jpg` duplicates the title page represented by `f003.png`; it is not
  an additional prepared page. These JPEGs are illustration/title assets.

All 386 file headers identify PNG images: 334 are 1000 × 1650 and 52 are
1000 × 1649. Their total file size is 10,228,140 bytes. Header inspection is
not a full decode or an OCR quality check.

Representative visual inspection covered f001, f003b, f003p, p013–p015, p021
and p384. f003b is blank; f003p is a sideways plate. Keep both, and include
the final publisher list at p384. Do not drop prepared pages to make the demo
look cleaner. Their OCR results were inspected: the blank page had no text,
and the sideways plate produced noise. Successful processing does not promise
useful recognition on blank or picture-only pages.

All 386 PNGs were copied into a separate flat page-only folder in scratch
storage. Original files remain untouched. Do not paste the
mixed source directory directly: its 31 JPEGs are also supported by the OCR
collector and would become extra inputs, giving 417 rather than 386 files.
A flat ZIP of those same 386 PNGs was also created and checked.

The collector sorts paths by filename. Expected order starts `f001.png`,
`f002.png`, `f003.png`, `f003b.png`, `f003p.png`, `f004.png`, continues through
`f010.png`, then p011–p384. This is project filename order, not a verified
mapping to IA scan leaves. Preserve the zero padding and check output order.

These prepared PNGs already existed. They are not claimed outputs of the recorded
download. Their filenames are local project names, not verified IA leaf numbers.

## Verified whole-folder and whole-ZIP routes

Use the page-only local folder for the main demonstration. Under **OR PASTE A
PATH**, paste its server-accessible path and click **Open**. In local-container
mode the panel is headed **Existing folder or zip**, and the path must exist
inside the container. Local paths are hidden and rejected in managed-server
mode. **Managed (download)** is the output choice, not that server-mode setting.

Also explain the browser routes. **Browse folder...** opens the hidden
`webkitdirectory` input where uploads are offered. Its files are posted through
`FormData` to `/api/uploads`; this copies files rather than passing a local
directory path. The frontend does not submit relative paths, and the backend
keeps only each basename. Folder uploads therefore flatten paths and can
overwrite duplicate names. A folder browser may enumerate descendants, but
this is not safe recursive folder preservation. Use the flat page-only folder.
Runtime checks verified 386 files in the browser picker and a successful upload. Dragging a directory is not the
documented route: the drop handler uses `dataTransfer.files` without walking
directory entries.

For ZIP input, place all 386 PNGs at the archive root. **Choose file...** or
dragging the ZIP uploads and extracts it through `/api/uploads`. Alternatively,
paste the ZIP path in local mode; `LocalPathSource` extracts it into a temporary
directory. Both feed `collect_images`, which scans immediate children only.
Images inside a wrapper folder or nested folders are not collected. Do not
promise that an arbitrary whole-book ZIP layout will work unchanged.

The actual OCR collector recognizes PNG, JPG/JPEG, TIF/TIFF, and JPEG 2000
JP2/J2K/JPF/JPX/JPM, case-insensitively; it skips old `.viewer.png` image caches.
It does not recurse. The picker advertises PDF and the local adapter accepts
WebP, but the inspected collector does not collect either format. The guide
therefore recommends the verified image formats instead of promising those
advertised formats or conversion of PDF pages.

Browser uploads default to 2 GiB total and 5,000 files per request. Uploaded
ZIP expansion defaults to the configured upload-byte cap; local ZIP expansion
has a fixed 2 GiB cap. The 386 PNGs total well below those byte/count defaults,
but another machine still needs disk space, models and a successful runtime
check. This run succeeded. A pasted directory avoids upload copying and its request
caps; it does not promise unlimited processing or a completion time.

## Demo sequence and draft narration

The revised video teaches installation and the OCR workflow one step at a time.
The audience is a first-time desktop user with a prepared book to process.
Use one continuous example: all 386 prepared Four Men PNG pages. Keep the
project name `The Four Men - full prepared book` throughout.

The owner requested this redesign after viewing the first cut. That cut remains
an archived draft, not the editorial model for the revision. Replace its long
archive-download opening and repeated qualifications with the sequence below.

### Teaching approach

Use the verified pointer-led recordings for the interface steps and text cards
for installation on each platform. Reuse the completed full-book results. Reuse progress footage only
after verifying that it shows changing counts; otherwise capture a fresh run.
A voice-over-only recut would retain the missing pointer and installation shots.
A fully new OCR run would repeat processing without improving these teaching steps.
This recording approach is the author's choice, based on the owner's direction.

Every instruction follows the same pattern: name the control, move the pointer
to it, pause, click, then show what changed. Keep the pace slow enough to follow
without pausing the video. Build the edit around the actions before recording
the final narration. Keep the established shared voice and pronunciation settings.

### Installation and launch shots

Show text instructions for each platform. No macOS or Windows screenshots are
needed. Linux and macOS use the published install script. Windows uses the
existing PowerShell steps, as the owner selected.

Linux and macOS, in Terminal:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.sh | sh
```

Windows, in PowerShell, install uv if needed:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Reopen PowerShell, then install the app:

```powershell
uv tool install pdomain-ocr-simple-gui --python 3.13 --index-strategy first-index --index pdomain=https://pdomain.github.io/pdomain-index-pip/simple/
```

Windows also needs the [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vc14/vc_redist.x64.exe).
Its installer may require administrator approval. The commands install the
current release; the app footage shows 0.5.7. Each card wraps long commands for
readability. The companion text file supplies each command on one copyable line.

Launch on every platform with `pdomain-ocr-simple-gui`. Keep the terminal open
and use the browser address it prints. The existing launch footage uses an
isolated 0.5.7 executable. Do not use the machine's global 0.5.5 executable.

The Linux script completed in a fresh isolated environment. Its log is under
`/mnt/scratch/ocr-four-men-installer-20261115/install/terminal.log`.
macOS and Windows instructions were checked against README Install and
[Astral's uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
They were not run for this recording. The final video uses text cards for all
three platforms, following the owner's latest direction.

### Shot list and spoken script

The narration below is the script. Production instructions stay in the middle
column and are not spoken. Credit and technical evidence remain in the end card
and written notes. The source preparation mention happens once, in scene 4.

| Scene | Picture, pointer and action | Spoken narration |
| --- | --- | --- |
| 1. What we will do | Briefly show a scanned page beside editable OCR text. Title: Turn a scanned book into editable text. | “Let's turn a scanned book into editable text. We'll install OCR Simple GUI, process the book, correct a page, and save the results.” |
| 2. Install | Show Linux, macOS and Windows text instruction cards in spoken order. Supply full copyable commands beside the video. | “On Linux, open a terminal and run the install script shown here. On a Mac, open Terminal and run the same script. On Windows, open PowerShell. Install uv if needed, reopen PowerShell, then run the app installation command. Windows also needs Microsoft's Visual C plus plus runtime. You can copy all these commands from the instructions beside this video.” |
| 3. Launch | Type the newly installed app command and press Enter. Show its real local address, then the home page. | “Now start OCR Simple GUI. It opens in your browser. Keep this terminal open while you work.” |
| 4. Prepared book | Show the page-only folder, a readable page thumbnail and the 386-file selection. No archive browser or download sequence. End with the app home page. | “These Four Men scans came from Internet Archive. With the pages cropped and prepared in grayscale, let's process the whole book: 386 pages.” |
| 5. Open the folder | Move to Browse folder..., pause and click. In the real folder dialog select the flat page-only folder and confirm. Show the loaded source and configuration form. | “Click Browse folder and select the folder containing your prepared pages. Keep the page files together, with names in reading order.” |
| 6. ZIP alternative | Use a separate short input demonstration. Move to Choose file..., click, select the flat prepared-pages ZIP and confirm. Show the loaded source, then return to the one main folder configuration. Do not submit a duplicate job. | “You can also process the whole book as a ZIP. Click Choose file and select your ZIP. Put the page images directly inside the archive.” |
| 7. Name and output | Move to Project name, click and enter the exact project name. Move to Managed (download), pause and select it. Show that it remains selected. | “Give the project a name so you can find it later. Choose Managed, download, to save the results from your browser.” |
| 8. Engine and device | Move to Engine and select DocTR. Move to CPU while explaining it, then GPU, then Auto. Finally explicitly select GPU for this recording and hold its detected-device message. | “Choose DocTR as the OCR engine. CPU uses your computer's main processor. GPU uses a supported graphics card and usually processes pages faster. Choose CPU if the app doesn't detect a GPU. Auto uses the detected GPU when available, or CPU otherwise. This computer has a supported GPU, so we'll select GPU.” |
| 9. Process the book | Move to Run OCR, pause and click. Use verified footage with changing page counts, or capture a fresh run after resource coordination. Cut the waiting section, then show that run's actual succeeded result and 386-page total. | “Click Run OCR to process the book. Watch the page count as the job runs. When it finishes, check that all 386 pages completed.” |
| 10. Review a page | Move to the p014 row and open it. Point to the source image, then the recognized text. Zoom to the relevant printed passage. | “Open a page to check the result. Compare the text with the scan. Here, the word earn has landed in the wrong place.” |
| 11. Correct and save | Show the original misplaced earn, move to the editable text and make the real correction. Move to Save edits, pause, click and hold Saved. Then use the next-page control once. | “Move earn back to the end of its sentence. Click Save edits. The saved message confirms the change. Use the page controls to continue checking the book.” |
| 12. Download the results | Return to results. Move to the first download control, pause and click. Show the ZIP and its text files. Return and point to the second control. Match its actual on-screen wording without implying it contains source images. | “Back on the results page, download the text ZIP. It contains a text file for each page and one combined file for the book, including your saved edits. The second download adds JSON files for software that needs structured page data. Keep your original images too.” |
| 13. Return to saved work | Move to header Jobs, pause, click and reopen The Four Men entry. Show the saved p014 correction. Do not tour storage settings or explain job identifiers. | “To return to your work, click Jobs and open the project. Your saved correction is still here.” |
| 14. Finish | Return to the launch terminal and show Ctrl+C stopping the app. Finish with a short source-credit card and guide link. | “When you're finished, save your edits and download the results. Return to the terminal and press Control C to stop the app.” |

Scene 8 teaches the choice; it does not compare processing times or run a second
CPU job. Keep GPU driver and PyTorch troubleshooting in the companion guide.
The app's detected-device message confirms the available processing device.

The prepared example is an existing local set, separate from the recorded IA
archive. No new cropping or grayscale conversion is demonstrated. The spoken
preparation instruction describes what viewers do before OCR. The black-and-white
prepared pages remain unchanged.

## Video editing notes, separate from user steps

1. Record a visible pointer throughout every interface action. Use smooth movement
   to the centre of the real control, a brief hover, then a click. Show a small
   click ring. Keep the pointer off text while the viewer reads it.
2. Keep a stable window size and readable text. Frame the active panel closely
   enough to read its labels. Use a gentle zoom for the device choices and the
   p014 correction, then restore the wider view before navigating.
3. Move and click at the spoken instruction. Leave a short pause after the UI
   responds. Do not show a static screenshot while narrating an unseen click.
4. Browser video capture alone may omit the native pointer and file dialogs.
   Verify a short capture that includes pointer movement, a click and the folder
   dialog before recording the full sequence. Record inside gui-sandbox. If a
   cursor must be composited, drive it from recorded pointer coordinates and
   synchronize it with the actual interactions. Do not guess button positions.
5. Shorten the OCR wait with a simple “Wait shortened” label.
   Do not narrate the editing policy, evidence checks or timing caveats. Preserve
   enough real changing progress to show that the book is processing.
6. Do not reuse the first cut's frozen 0/386 progress hold as the entire progress
   section. Existing logs contain changing counts; the revised video needs
   changing on-screen progress. Reuse matching real footage if available;
   otherwise record a fresh authorized run after resource coordination.
7. Capture the original p014 error and its correction as one clear teaching
   sequence. Preserve the original response before changing it. Finish with
   the saved confirmation and a corrected download.
8. Remove the archive-download scenes, byte totals, provenance narration, job-ID
   explanation, settings tour, blank/sideways-page tour and repeated accuracy
   disclaimers from the main video. Keep those facts in the guide or evidence.
   End-card credit names Belloc, the IA item and Kelly - University of Toronto.
9. Preserve the first cut and original captures. Write the revision under a new
   output name. The original nine screenshot assets and app code stay untouched.
10. Check the new cut for teaching quality: every named control appears when
    spoken; every click has a visible pointer; platform commands are readable;
    CPU/GPU/Auto choices are explained; the full book completes; the correction
    is saved and present in the export. Review motion and narration alignment,
    not only isolated still frames.

### Caption layout and narration speed

Keep the 1280 × 800 picture intact. Add a 160-pixel black band below it,
producing a 1280 × 960 video. Burn white captions into that band only, with
one or two short lines at a time. Time phrases to the spoken words and leave
the band blank during pauses. Use narration speed 0.9. Deliver a separately
named `captions.srt` to avoid automatic duplicate captions in players.

### Revision recording status

The current text-card revision replaces installation footage with platform text
cards. It runs 3:36 at 1280 × 960, with narration speed 0.9 and captions below
the picture. Its delivery is
`/mnt/work/projects/pdomain-videos/ocr-simple-gui/out/four-men-fullbook-20261115-installer/four-men-walkthrough.mp4`.
The current companion files are `captions.srt` and `install-and-launch.txt`.

The previous revised video runs 3:30 and remains preserved. That cut shows an
isolated 0.5.7 installation, the native pointer and folder/ZIP dialogs,
CPU/GPU/Auto selection, changing full-book progress, the p014 correction,
exports, Jobs and Ctrl+C shutdown. Its delivery is
`/mnt/work/projects/pdomain-videos/ocr-simple-gui/out/four-men-fullbook-20261115-revised/four-men-walkthrough-revised.mp4`.
Matching subtitles and `install-and-launch.txt` accompany that earlier cut.

The first 4:27 cut and its captures remain preserved.

Fresh job `0aedefc5-e7b4-4cf4-ac67-34f8c17014ce` completed all 386 pages.
Both ZIPs retain the saved correction. Their combined text matches all 386
page text files in filename order.

The recording app and sandboxes are stopped. Application code remains unchanged.
Frame review passed. The earlier 3:30 cut also passed a speech-to-text check
through the closing instruction. The current revision uses native narration
word timestamps for its short captions.

Current evidence is under `/mnt/scratch/ocr-four-men-installer-20261115/`.
Earlier evidence and review receipts remain under
`/mnt/scratch/ocr-four-men-redesign-20261115/`.

Earlier full-book evidence below remains valid for its named run.

## Evidence and reconciled guide review

Read the local app handoff
`/mnt/work/projects/pdomain/pdomain-ocr-simple-gui/docs/handoff/2026-11-15-005406-install-tests-port-fix-walkthrough-tts.md`
and both video handoffs under `/mnt/work/projects/pdomain-videos/docs/handoff/`:
`2026-11-15-021021-tts-narration-setup.md` and
`2026-11-15-021123-ocr-simple-gui-video-transfer.md`.
Their earlier results are historical evidence, not a new Four Men test.

| Previous finding | Draft disposition |
| --- | --- |
| Managed must be explicit | Direct selection instruction before Run OCR and ZIP steps. |
| Job ID unexplained | Address format and relationship to filenames/folders explained. |
| OCR, terminal, GiB, JSON, stop command unclear | Plain definitions added at first use or stop instructions. |
| Missing Jobs-list image | Header Jobs list captured separately from Settings > Jobs. |
| Next to source needs checking | Source checked: JobConfigInline enables it for `source.kind === "path"`; OutputConfigPanel filters it otherwise. Runtime check deferred. |
| Timing language too strong | Removed duration promises and any full-book extrapolation. |
| Page-view glyph differs | Source shows `⤓`, now reflected in guide. |
| Download table too dense | Reduced to two rows; explained limitations in prose. |
| Closing-tab persistence untested | Saved p014 text survived tab close/reopen and server restart. |
| Stop behavior | Prior Ctrl+C/SIGINT confirmation retained. The published guide does not recommend stopping by process name. That method stays untested. |
| Wrong source for new example | Four Men credit and local prepared provenance added; old screenshot credit retained as historical. |
| Image claims in ZIPs | This full-book Managed run had zero images in both ZIPs. |

Source checks used this guide worktree at `b89a2f4`:
`frontend/src/components/SourcePicker.tsx`, `JobConfigInline.tsx`,
`OutputConfigPanel.tsx`, `frontend/src/pages/ResultsPage.tsx`, `PageViewPage.tsx`,
and `src/pdomain_ocr_simple_gui/routes/downloads.py`. Full-book input inspection
also checked `frontend/src/pages/HomePage.tsx`,
`frontend/src/statecharts/jobCreationMachine.ts`,
`src/pdomain_ocr_simple_gui/routes/uploads.py`, `routes/jobs.py`,
`sources/local_path.py`, `sources/uploaded_files.py`, and `pipeline.py`.
These input-path files match current local master `5ee2466`.
The export filters text/JSON from the output folder and includes any other files
already present. It does not establish that prepared images reach that folder.
The app owner may change behavior later; recheck against the recording version.

The earlier draft's independent substantive review found one medium issue: project-only paths could
block readers who do not have this book project. The guide now labels those
paths as recording-only and explains how to use a reader's own prepared pages.
Independent substantive review of the full-book revision found no actionable
issues. Final readability and static integrity checks follow before delivery.
The runtime evidence below covers the named 0.5.7 run only.

## Runtime evidence and remaining checks

Evidence is under `/mnt/scratch/ocr-four-men-fullbook-20261115/`:

- Pinned released GUI 0.5.7 ran at `http://127.0.0.1:8047`, with HOME, XDG paths
  and temporary files isolated. Machine uv cache and Python installation paths
  were preserved. The global unpinned executable was not used.
- `downloads/raw-download.json` records the actual IA archive: 257,861,622 bytes.
  Its ZIP integrity check passed. `downloads/sources.tsv` records the source.
- `state.json` identifies job `86023a3d-3771-453d-99f4-e36bbb10a5b8`.
  `job-latest.json` records 386/386 succeeded with no failed pages.
- `review.json` records the verified p014 correction and both exports. The first
  has 386 page text files plus combined text: 387 members. The second adds
  386 page JSON files: 773 members. Both have zero source images. Saved text
  was checked in the per-page export, combined text and JSON edited text.
- `inputs.json` records successful browser ZIP and folder uploads without a
  second OCR submission. The ZIP has 386 root-level PNGs; the folder picker
  supplied 386 files. The local folder route was the full-book OCR input.
- `reopen.json` verifies the completed job and saved correction after server
  restart. Earlier review also closed and reopened the tab. Server logs record
  clean SIGINT shutdowns. The final app process and GUI sandbox were stopped
  after the paced recording.
- `captures/` holds original browser videos, screenshots and screen text;
  `evidence/events.jsonl` holds event times. The original short headed
  submission clip had a resize artefact. Its authentic full-frame progress
  screenshot is held with “OCR wait shortened”; app-action scenes use new
  fixed-size headless recordings. No new OCR job is submitted for those scenes.
- `narration/audio/` holds 13 Kokoro `af_heart` scene WAVs at speed 0.8 and
  24,000 Hz. Their measured total is 266.725 seconds: narration length, not
  an OCR runtime estimate.
- The local delivery folder is
  `/mnt/work/projects/pdomain-videos/ocr-simple-gui/out/four-men-fullbook-20261115/`.
  It holds `four-men-walkthrough.mp4`, matching SRT subtitles and runtime
  metadata. Media stays outside git. The current delivery video uses H.264 at
  1280 × 800 and AAC narration; it is not a software release or publication.

Other browsers, managed-server mode, pasted local-ZIP extraction, full-book
Tesseract and desktop-shortcut stopping were not runtime-tested. Flat ZIP
upload and browser folder upload were tested. The local-ZIP route and
nonrecursive limits were checked against source. Full app CI, merges and
releases remain with the app owner. No application source changed.

Keep the quality limit explicit: job success is not proof of accurate
transcription. The blank page and sideways plate were retained and inspected;
their OCR can contain little text or noise. Publication location is undecided.
Deliver the local video and reviewed guide without prompting coordinator panes.

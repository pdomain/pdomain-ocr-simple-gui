---
Status: active
Owner: CT
Created: 2026-11-13
Last verified: 2026-11-13
Kind: research
---

# Windows GUI proof, 2026-11-13

## Agent Index

- **Kind:** research
- **Status:** active
- **Read when:** changing path handling, startup output, engine detection or
  page-view layout, or judging what real Windows coverage the app has.
- **Search terms:** Windows, Edge, Playwright, standard user, WinError 126,
  Visual C++ Redistributable, path containment, cp1252, page view overflow.

## Goal

Find out whether a Windows user can install pdomain-ocr-simple-gui 0.5.4 and
use it end to end: upload, real OCR, edit, save, download, rerun, download
again. Fix what stops them.

## Method

The app ran in the `omarchy-windows` VM: Windows 11 build 26100, Windows
PowerShell 5.1.26100.7920, 6 CPU cores, no GPU, UAC on. Every run used the
local standard account `pdtest`, opened with `runas`.

1. Installed the app with
   `uv tool install pdomain-ocr-simple-gui --python 3.13 --index-strategy first-index --index pdomain=https://pdomain.github.io/pdomain-index-pip/simple/`.
   The README's manual command uses Unix line continuations and
   `--extra-index-url`, so it does not run as written in PowerShell.
2. Ran a Python Playwright driver, `uv run --no-project --with playwright`,
   that starts the installed app with `--no-browser` and drives the Edge
   already on Windows (`channel="msedge"`, headed). It mirrors
   `tests/e2e/test_real_ocr_acceptance.py`, uses DocTR for the rerun because
   Tesseract is not installed, and records each step to JSON.
3. Fixed each failure on Linux with a failing test first, rebuilt the wheel,
   installed it over the release with `--reinstall`, and ran the driver again.
4. Uninstalled the Visual C++ runtime to see what the app does without it,
   then reinstalled 14.52.37029.
5. Ran the final wheel twice: with the released pdomain-ops 0.12.4, and with
   the pdomain-ops branch `fix/windows-suite-bootstrap`.

## Evidence

**Startup crash.** 0.5.4 exited with code 1 at once: pdomain-ops prints an
emoji at startup, and with output redirected Windows Python writes cp1252.

**Every job rejected.** With `PYTHONIOENCODING=utf-8` as a workaround, upload
and job creation worked, then `GET /api/jobs/<id>` returned 400. Project id
validation required the resolved path to start with the store root plus `/`.
Windows paths use `\`. Three other checks, two for uploads and one for local
ZIP sources, had the same flaw.

**Suite routes and a waiting page.** pdomain-ops rejected
`C:\Users\pdtest\.local\bin\pdomain-ocr-simple-gui.exe` as not absolute, so the
suite routes did not mount. The SPA fallback then answered `/api/suite/prefs`
and any other unknown API path with `index.html` and status 200.

**Slow first start.** The first `GET /api/config` took 51.7 s and later calls
took 0.0 s. That is the first torch import on a cold Windows CPU start. Later
cold starts took 3.5 s to 4.9 s. The home page showed only "Loading...".

**Missing runtime.** Without the Visual C++ runtime, `/api/config` answered in
0.3 s and still listed DocTR as available. The job then failed with "PyTorch is
not available in this environment". After the first failed import, torch raises
"can only be initialized once" for every later import in the process.

**Page view overflow.** At Edge's default 1280x720 viewport, the page view's
button row was wider than its panel, a download click scrolled the panel
sideways, and the OCR text was out of view. On Linux the toolbar needed 1131 px
in a 608 px panel at 1280x720, and was still too wide at 1920x1080.

**Line endings.** Exported `.txt` and `.json` files use CRLF on Windows; the
JSON `edited_text` field keeps LF. The CLI also writes CRLF on Windows.

**Final runs.** With the final wheel, `pdomain_ocr_simple_gui-0.5.5.dev6+g1718b99e5`,
both runs passed every step in about 26 s:

| Step | pdomain-ops 0.12.4 | pdomain-ops fix branch |
| --- | --- | --- |
| Server start, no encoding workaround | passed | passed |
| `/api/suite/prefs` | 404 JSON | 200 JSON |
| Unknown API path | 404 JSON | 404 JSON |
| Real DocTR OCR, word overlap | 1.0 | 1.0 |
| Saved edit in ZIP text and JSON | passed | passed |
| DocTR rerun keeps the edit, changes engine output | passed | passed |
| Tesseract rerun button without Tesseract | hidden | hidden |

The final page-view screenshot at 1280x720 shows the buttons on two rows and
the edited text in view. Without the runtime, the home page showed "DocTR
cannot run on this computer" with the Visual C++ download link.

## Conclusions

- 0.5.4 cannot be used on Windows: it does not start with redirected output,
  and when started it cannot open any job.
- The unreleased fixes on local `master` make the full flow work on Windows
  with the released pdomain-ops 0.12.4. Only the settings panel still needs
  the pdomain-ops fix.
- Driving the real installed app with Playwright and the system Edge works on
  Windows without downloading a browser, and it found six real defects that
  the Linux suite did not.

## Next steps

- Release the GUI fixes, and review, merge and release the pdomain-ops branch,
  when the owner approves.
- Give the GUI a Windows install path with the CLI's Visual C++ runtime check,
  and fix the README's manual install command for PowerShell.
- Keep the Windows driver as a repeatable manual acceptance run.

## What this does NOT establish

- No GPU or CUDA run: the VM has no GPU.
- Tesseract was not installed, so no Tesseract OCR ran on Windows.
- Only one fixture page was used; no PDF, TIFF, ZIP or folder source ran on
  Windows, so the fixed ZIP containment check has only Linux tests that use
  Windows path rules.
- The settings panel itself was not opened in the browser.
- Only Edge on Windows 11 ran; no other browser or Windows version.
- The app was launched by the driver, not by a desktop shortcut or the
  browser auto-open.

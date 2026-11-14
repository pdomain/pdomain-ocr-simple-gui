---
Status: active
Owner: CT
Created: 2026-11-13
Last verified: 2026-11-13
Kind: runbook
---

# Windows acceptance run

## Agent Index

- **Kind:** runbook
- **Status:** active
- **Read when:** a release changes anything that can behave differently on
  Windows, or you need to check the installed app on a real Windows machine.
- **Search terms:** Windows, acceptance, Edge, Playwright, standard user,
  windows_acceptance.py, PowerShell, uv tool.

## Trigger

Run this before a release that affects Windows. That means changes to path
handling, startup output, engine detection, file writes, or the web pages.
The release helper cannot run it, because it needs a Windows machine.

The script is `scripts/windows_acceptance.py`. It is the maintained version of
the driver proven on 2026-11-13 in
[the Windows GUI proof](../research/2026-11-13-windows-gui-proof.md). It
mirrors `tests/e2e/test_real_ocr_acceptance.py`, but it tests the installed
tool in Microsoft Edge and never imports the app package.

## Preconditions

- Windows 10 or 11 with Microsoft Edge.
- [uv](https://docs.astral.sh/uv/) installed.
- A standard user account, not an administrator. The proof used one, and it
  catches permission and path bugs that an administrator hides.
- The Microsoft Visual C++ Redistributable (x64), so DocTR can load.
  See [README Tier 3](../../README.md#tier-3--manual-install-via-uv).
- The app installed with the PowerShell command from README Tier 3.
- A checkout of this repo at the release commit. The script uses the fixtures
  under `tests/e2e/fixtures`.

## Steps

Install the release candidate (add `--reinstall` to replace an older install):

```powershell
uv tool install pdomain-ocr-simple-gui --python 3.13 --index-strategy first-index --index pdomain=https://pdomain.github.io/pdomain-index-pip/simple/
```

Run the acceptance script from the repo checkout:

```powershell
uv run --no-project --with playwright python scripts\windows_acceptance.py --out-dir C:\Users\Public\acceptance
```

The run opens a visible Edge window and takes several minutes on a CPU. Do not
use the machine's browser during the run.

Options:

| Option | Default | Use |
|--------|---------|-----|
| `--out-dir` | `windows-acceptance-out` | Where results, screenshots and the server log go. |
| `--fixtures` | `tests/e2e/fixtures` | A directory, a `.png`, or a `.gt.txt`. Each page needs a `.png` and a `.gt.txt`. |
| `--browser-channel` | `msedge` | Playwright browser channel. |
| `--headless` | off | Hide the browser window. |
| `--exe` | search `PATH` | Full path to `pdomain-ocr-simple-gui`. |
| `--skip-text-quality` | off | Smoke runs with fake OCR only. See below. |

The script starts the installed app on a free port, then:

1. Times `/api/config` twice, and checks `/api/suite/prefs` and an unknown
   `/api` path.
2. Uploads the fixture page, runs OCR, and waits for the job to succeed.
3. Checks that the OCR text shares at least 60% of its words with the ground
   truth.
4. Edits and saves the text, then downloads the ZIP of images, text and JSON.
   The edit must be in the page text, the page JSON `edited_text` and the
   combined text. Windows writes CRLF line endings, so the script converts
   them to LF before it compares.
5. Reruns the page with DocTR and downloads the ZIP again. The edit must
   survive, and the engine output must change.
6. Records whether the Tesseract rerun button is enabled. This is information,
   not a pass condition.

### Smoke run on Linux

`--skip-text-quality` skips the two checks that need real OCR output: the word
overlap and the changed engine output after the rerun. Use it only to prove the
script works against the fake OCR engine, never for acceptance. On Linux, start
the check with `PDOMAIN_OCR_FAKE_DISPATCHER=1` and Playwright's own chromium:

```bash
PDOMAIN_OCR_FAKE_DISPATCHER=1 uv run python scripts/windows_acceptance.py --headless --browser-channel chromium --skip-text-quality
```

## Verification

The run passes when the last line is `WINDOWS-ACCEPTANCE PASS` and the exit code
is 0. Any failed check prints `WINDOWS-ACCEPTANCE FAIL` with the check names,
and the exit code is 1. A run with `--skip-text-quality` is a smoke run, not an
acceptance result.

Results go to `--out-dir`:

- `results.json`: every step with timings, every check, and any error.
- `server.log`: the app's output.
- `page-view.png` and `after-rerun.png`: screenshots.
- `zip-after-edit.json`: the text and JSON files from the first export.

Attach `results.json` to the release notes or the issue that asked for the run.

## Rollback

The script changes nothing outside `--out-dir` and the app's own job store. If
a check fails, do not release. Fix the defect and run again. To remove the
install, run `uv tool uninstall pdomain-ocr-simple-gui`.

## Known gaps

- No GPU. The run covers CPU DocTR only.
- No Tesseract. The proof machine had none, so the script records the button
  state and does not test a Tesseract rerun.
- One page, one fixture. It does not cover multi-page jobs or folder sources.
- Edge only by default. Other browsers need `--browser-channel`.
- The flow was first proven on 2026-11-13, as recorded in
  [the proof](../research/2026-11-13-windows-gui-proof.md). The script itself
  then passed all 12 checks on Windows 11 as a standard user with Edge and
  real DocTR on the CPU, in 32.7 s, with the pdomain-ops fix branch
  installed. With pdomain-ops 0.12.4 the `suite-prefs-route` check fails,
  because the settings routes do not mount on Windows.

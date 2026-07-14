---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-07-14
Kind: runbook
---

# Linux installation

## Agent Index

- **Kind:** runbook
- **Status:** active
- **Read when:** installing, upgrading, or removing the browser application.
- **Search terms:** install, Linux, AppImage wizard, uv tool, browser.

## Trigger

Use this runbook to install or repair `pdomain-ocr-simple-gui` on Linux.

## Preconditions

Use Linux x86_64 with internet access. The AppImage installer wizard is the
preferred interactive route when a graphical session is available. The
fallback requires `uv`; the installer can bootstrap it.

## Steps

Run `install.sh` from a release checkout or release bundle. It selects the
AppImage wizard when supported and otherwise installs the plain
`pdomain-ocr-simple-gui` package with `uv tool install`. The application is
browser-based; there is no supported `desktop` extra or Qt launch mode.

For a direct fallback install, run:

```bash
uv tool install pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/
pdomain-ocr-simple-gui
```

The default URL is `http://localhost:8004`. Jobs default to
`~/.local/share/pdomain-suite/simple-gui/projects/`; suite registration uses
`~/.local/share/pdomain-suite/installed.toml`. A configured environment or
saved jobs-location preference can override the project root.

## Verification

Confirm the process starts, the browser can open the default URL, and a small
OCR job completes. Repository verification for this contract lives in
`tests/test_install_sh.py` and `tests/packaging/test_install_engine.py`.

## Rollback

Remove the tool with `uv tool uninstall pdomain-ocr-simple-gui`. Preserve or
back up the jobs directory separately; uninstalling the package does not make
project data disposable.

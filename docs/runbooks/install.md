---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-11-07
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

Use Linux x86_64 with internet access. The install needs `uv`; the installer
can bootstrap it.

## Steps

Run `install.sh` from a release checkout or release bundle. It uses the
AppImage installer wizard when the latest release carries the AppImage and a
graphical session is available. Otherwise it installs the plain
`pdomain-ocr-simple-gui` package with `uv tool install`. Only releases v0.3.5
through v0.4.0 carry the AppImage. The workflow that built it was removed on
2026-09-13, so v0.5.0 installs through `uv tool install`. The application is
browser-based; there is no supported `desktop` extra or Qt launch mode.

For a direct fallback install, run:

```bash
uv tool install pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/
pdomain-ocr-simple-gui
```

The default URL is `http://127.0.0.1:8004`; if port 8004 is taken, the app
uses the next free port. Jobs default to
`~/.local/share/pdomain-suite/simple-gui/projects/`; suite registration uses
`~/.local/share/pdomain-suite/installed.toml`. A configured environment or
saved jobs-location preference can override the project root.

## API token

When `PDOMAIN_API_TOKEN` is set on the server, every mutating request must
carry a matching bearer token or the backend returns 401. Set it from
**Settings > API Token** in the browser app: paste the token, click Save, and
the status line reads `set`. Click Clear to remove it.

For headless setups (no browser session available), set the same
`pdomain.apiToken` localStorage key from the browser's developer console:

```js
localStorage.setItem('pdomain.apiToken', '<token>');
```

The frontend reads this key on every API call and attaches
`Authorization: Bearer <token>` automatically. Clear it with
`localStorage.removeItem('pdomain.apiToken')`.

## Verification

Confirm the process starts, the browser can open the default URL, and a small
OCR job completes. Repository verification for this contract lives in
`tests/test_install_sh.py` and `tests/packaging/test_install_engine.py`.

## Rollback

Remove the tool with `uv tool uninstall pdomain-ocr-simple-gui`. Preserve or
back up the jobs directory separately; uninstalling the package does not make
project data disposable.

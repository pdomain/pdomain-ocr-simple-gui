---
Status: active
Owner: CT
Created: 2026-05-17
Last verified: 2026-07-14
Kind: usage
---

# pdomain-ocr-simple-gui

A minimal drag-and-drop OCR app — drop a folder of scanned images, run OCR,
get plain-text output. Built on FastAPI + React/Vite, using `pdomain-book-tools`
for OCR and `pdomain-ops` for suite plumbing. Serves as the Phase 3 reference
consumer that validates `pdomain-ops`' `LocalStageDispatcher`.

Contributors and coding agents must start with [AGENTS.md](AGENTS.md).

The app runs as a local web server and **opens your default browser automatically**
on launch. No native window or Qt library is required.

## Install

### Tier 1 — curl one-liner (easiest, Linux x86\_64)

Paste this into a terminal. It downloads the AppImage, marks it executable, and
launches the installer wizard automatically — no separate steps needed:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.sh | sh
```

The wizard walks you through the gated install steps (uv, `uv tool install`,
desktop shortcut).

On non-desktop systems (CI, headless servers, macOS, non-x86\_64), or when the
AppImage asset is unavailable, the script falls back to a uv-tool install
automatically.

To skip the AppImage wizard and use uv-tool directly:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.sh | sh -s -- --no-appimage
# or: NO_APPIMAGE=1 curl -sSL .../install.sh | sh
```

### Tier 2 — AppImage download (Linux x86\_64)

Download the `.AppImage` from the [Releases](https://github.com/pdomain/pdomain-ocr-simple-gui/releases) page.

Browsers download files without the executable bit set — this is standard Linux
behavior, not specific to this app. You must mark the file executable once before
it can run.

**Without a terminal (file manager):** right-click the `.AppImage` → Properties →
Permissions tab → check "Allow executing file as program" (wording varies by file
manager; in Nemo on Linux Mint it is exactly that) → then double-click it.

**Terminal equivalent:**

```sh
chmod +x pdomain-ocr-simple-gui-installer-x86_64.AppImage
./pdomain-ocr-simple-gui-installer-x86_64.AppImage
```

### Tier 3 — manual install via uv

```sh
uv tool install pdomain-ocr-simple-gui \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/
```

## Launch

```sh
pdomain-ocr-simple-gui
```

The app starts the local web server and opens `http://localhost:8004` in your
default browser automatically. Drop a folder of images, pick an OCR engine,
and run. Output `.txt` files appear in the directory you choose.

To suppress the browser auto-open (headless servers, CI, docker):

```sh
pdomain-ocr-simple-gui --no-browser
# then open http://localhost:8004 in your browser
```

## Uninstall

One-liner:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh
```

The script removes the desktop shortcut (if installed), unregisters from the
suite registry, and uninstalls the tool via `uv tool uninstall`. It also offers
to remove `uv` itself, defaulting to yes only if this installer originally
bootstrapped it.

Unattended (skip all prompts):

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh -s -- -y
```

User data (`~/.local/share/pdomain-ocr-simple-gui/`) is not removed
automatically. OCR model weights (`~/.cache/doctr/`) are also left in place.

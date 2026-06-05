# pdomain-ocr-simple-gui

A minimal drag-and-drop OCR app — drop a folder of scanned images, run OCR,
get plain-text output. Built on FastAPI + React/Vite, using `pdomain-book-tools`
for OCR and `pdomain-ops` for suite plumbing. Serves as the Phase 3 reference
consumer that validates `pdomain-ops`' `LocalStageDispatcher`.

## Install

One-liner (handles uv, CUDA detection, and WebKitGTK check automatically):

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/install.sh | sh
```

Manual install via `uv`:

```sh
uv tool install "pdomain-ocr-simple-gui[desktop]" \
  --extra-index-url https://pdomain.github.io/pdomain-index-pip/simple/
```

The `[desktop]` extra (`pdomain-ops[desktop]`) adds the native window via
`pywebview`. Browser mode works without it.

## Launch

Desktop window (native, requires WebKitGTK system library):

```sh
pdomain-ocr-simple-gui --desktop
```

Browser mode:

```sh
pdomain-ocr-simple-gui
```

Opens at `http://localhost:8004`. Drop a folder of images, pick an OCR engine,
and run. Output `.txt` files appear in the directory you choose.

## Uninstall

One-liner:

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh
```

The script removes the desktop shortcut (if installed), unregisters from the
suite registry, and uninstalls the tool via `uv tool uninstall`. It also offers
to remove `uv` itself, defaulting to yes only if this installer originally
bootstrapped it.

Unattended (skip all prompts):

```sh
curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/main/uninstall.sh | sh -s -- -y
```

User data (`~/.local/share/pdomain-ocr-simple-gui/`) is not removed
automatically. OCR model weights (`~/.cache/doctr/`) are also left in place.

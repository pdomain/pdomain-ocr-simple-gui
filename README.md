# pdomain-ocr-simple-gui

A minimal drag-and-drop OCR app — drop a folder of scanned images, run OCR,
get plain-text output. Built on FastAPI + React/Vite, using `pdomain-book-tools`
for OCR and `pdomain-ocr-ops` for suite plumbing. Serves as the Phase 3 reference
consumer that validates `pdomain-ocr-ops`' `LocalStageDispatcher`.

## Install

```sh
uv tool install pdomain-ocr-simple-gui \
  --index-url https://pdomain.github.io/pdomain-index-pip/simple/
```

## Launch

```sh
pdomain-ocr-simple-gui
```

Opens at `http://localhost:8004`. Drop a folder of images, pick an OCR engine,
and run. Output `.txt` files appear in the directory you choose.

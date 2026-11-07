---
Status: active
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-07
Kind: issue
Level: I2
---

# The page viewer's PNG cache files get picked up as extra OCR pages

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I2
- **Last verified:** 2026-11-07
- **Resolution:** Open
- **Severity:** Medium — a later job on the same folder OCRs cache files as if
  they were scanned pages.
- **Affected version:** v0.5.0; `master` at `c029c52`
- **Read when:** changing the page image route, the browser transcode cache, or
  which files `collect_images` accepts.
- **Search terms:** viewer.png, viewer.webp, transcode cache,
  _transcode_for_browser, collect_images, _IMAGE_SUFFIXES, extra pages,
  duplicate pages.
- **Relates to:** [runtime flows](../architecture/runtime-flows.md),
  [intent map](../context/intent-map.md)

## Summary

When the browser does not accept WebP, the page viewer leaves a PNG copy of the
page, named `<name>.viewer.png`, next to the original scan. The next job started
on the same folder OCRs every such copy as an extra page. The app writes the
copy to show the page in the browser. Files ending in `.png` count as pages, so
nothing keeps the copy out.

## Impact

- A later job on the same source folder gets extra pages. They duplicate the
  real pages, and their names sort among the real ones.
- Every source that is not a PNG is affected: JPEG, TIFF and the JPEG 2000
  family (`.jp2`, `.j2k`, `.jpf`, `.jpx`, `.jpm`). A PNG source is served as is
  and gets no cache file.
- Only browsers that do not send `image/webp` in their `Accept` header trigger
  it. Current Chrome, Firefox and Safari send it, so this is rare.
- The app writes into the user's source folder, which the user may not expect.

## Environment / versions

```text
pdomain-ocr-simple-gui v0.5.0 (master c029c52)
src/pdomain_ocr_simple_gui/routes/pages.py   (_transcode_for_browser)
src/pdomain_ocr_simple_gui/pipeline.py       (collect_images, _IMAGE_SUFFIXES)
```

## Evidence

### 1. The cache file is written next to the source scan

`_transcode_for_browser` in `routes/pages.py` names the cache
`source.with_name(f"{source.name}.viewer{suffix}")`. The suffix is `.webp` when
the `Accept` header includes `image/webp`, and `.png` otherwise. A source
`scan_001.jpg` therefore gets `scan_001.jpg.viewer.png` in the same folder.

### 2. Page collection keeps any file whose last suffix is `.png`

`collect_images` in `pipeline.py` returns every child whose
`suffix.lower()` is in `_IMAGE_SUFFIXES`. That set includes `.png`, and
`Path("scan_001.jpg.viewer.png").suffix` is `.png`. Nothing filters out
`.viewer.` names.

### 3. The WebP cache is safe only because `.webp` is not a page suffix

`.webp` is left out of `_IMAGE_SUFFIXES`, so `.viewer.webp` files are skipped.
Commit `22e82d7` kept it that way on purpose, and the no-images error now lists
only the accepted suffixes.

## Root-cause hypotheses

1. **(Confirmed by reading the code) The cache lives in the source folder and
   uses a page suffix.** Page collection cannot tell a cache file from a scan.

## Defects to fix

1. **Cache location:** write viewer caches into the project directory that holds
   `project.json`, not into the source folder. (Primary) `_transcode_for_browser`
   then needs a destination argument. Its staleness check compares the source
   and cache modification times, which still works after the move.
2. **Collection filter:** skip names containing `.viewer.` in `collect_images`.
   This also ignores the caches already written into users' source folders.

## Next steps

1. Write a failing test: a folder with `a.jpg`, `a.jpg.viewer.png`, `b.jp2` and
   `b.jp2.viewer.png` must collect two pages.
2. Add the `.viewer.` filter to `collect_images`.
3. Move the cache into the project directory. Then decide whether to clean up
   caches already written into source folders.

## What is NOT broken (to scope the fix)

- WebP caches, which are never collected.
- PNG sources, which are served without a cache.
- The original scans, which the transcode never changes.

## Resolution

_Open._

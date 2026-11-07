---
Status: active
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-07
Kind: issue
Level: I2
---

# The CUDA setup link in the Compute panel points to a page the app does not serve

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I2
- **Last verified:** 2026-11-07
- **Resolution:** Open
- **Severity:** Low — a help link leads to the app's home screen instead of
  the CUDA guide.
- **Affected version:** v0.5.0; `master` at `c029c52`
- **Read when:** changing the Settings > Compute panel, or deciding where
  in-app help links should point.
- **Search terms:** cudaDocsUrl, CUDA setup, Compute panel, help link,
  cuda-setup.md, SPA fallback.
- **Relates to:** [CUDA setup runbook](../runbooks/cuda-setup.md),
  [intent map](../context/intent-map.md)

## Summary

The Compute panel in Settings links to `/docs/runbooks/cuda-setup.md` for CUDA
help. The app does not serve the repo's `docs/` folder, so that URL falls
through to the app's catch-all route, which returns the app's own page. A user
looking for CUDA help never sees the guide.

## Impact

- A user who needs GPU setup help clicks the link and lands back in the app.
- Nothing shows an error, so the user may not realise the guide exists.

## Environment / versions

```text
pdomain-ocr-simple-gui v0.5.0 (master c029c52)
frontend/src/App.tsx            (cudaDocsUrl)
src/pdomain_ocr_simple_gui/app.py (spa_fallback)
```

## Evidence

### 1. The panel links to a repo path

`frontend/src/App.tsx` passes `cudaDocsUrl="/docs/runbooks/cuda-setup.md"` to
the Compute panel.

### 2. The server serves only the built frontend

`app.py` mounts `/assets` from the frontend build, then registers
`spa_fallback` for every other non-API path. `spa_fallback` serves a real file
only when it exists inside the frontend build directory. `docs/` is not copied
into the build or the wheel, so the request gets the app's `index.html`.

## Root-cause hypotheses

1. **(Confirmed by reading the code) The link assumes the repo's docs are
   served, and they are not.**

## Defects to fix

1. **Dead link:** point `cudaDocsUrl` at a URL that works for an installed app.
   (Primary)

## Next steps

1. Point the prop at the runbook on GitHub:
   `https://github.com/pdomain/pdomain-ocr-simple-gui/blob/master/docs/runbooks/cuda-setup.md`.
   The link must be an `http://` or `https://` URL, because pdomain-ui's
   `ComputeTargetPanel` opens only those as external links. The panel picks the
   URL in this order: the `cudaDocsUrl` prop, then `cuda_docs_url` from the
   backend, then its own default, the PyTorch install page. Removing the prop
   also works, but the PyTorch page does not cover this app's installer.
2. Update `cudaDocsUrl` in `frontend/src/App.tsx` and the assertion in
   `frontend/src/__tests__/AppSettingsPanels.test.tsx` (around line 173),
   which expects the old path.

## What is NOT broken (to scope the fix)

- The Compute panel itself, including CPU and GPU selection.
- The runbook, which was rechecked against the code on 2026-11-07.

## Resolution

_Open._

---
Status: active
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-07
Kind: issue
Level: I2
---

# The page-view re-run shortcuts check for Tesseract on the wrong shortcut

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I2
- **Last verified:** 2026-11-07
- **Resolution:** Open
- **Severity:** Medium — the DocTR shortcut is dead without Tesseract, and the
  Tesseract shortcut sends a request the server rejects.
- **Affected version:** v0.5.0; `master` at `c029c52`
- **Read when:** fixing keyboard shortcuts in the page view, or changing how
  the page view checks which engines are available.
- **Search terms:** Ctrl+R, Ctrl+Shift+R, mod+r, re-run shortcut,
  tesseractAvailable, PageViewPage, B-PAGEVIEW-013, B-PAGEVIEW-014, 400.
- **Relates to:** [page view behavior spec](../specs/behavior/screen-page-view.md),
  [intent map](../context/intent-map.md)

## Summary

In the page view, the check for "Tesseract installed" guards the wrong
shortcut. Ctrl+R re-runs DocTR, but it only works when Tesseract is installed.
Ctrl+Shift+R re-runs Tesseract, and it fires even when Tesseract is missing. The
two on-screen buttons are guarded correctly; only the shortcuts are swapped.

## Impact

- On a machine without Tesseract, Ctrl+R does not re-run DocTR. The skipped
  binding does not call `preventDefault`, so the browser's own Ctrl+R reloads
  the page, as the B-PAGEVIEW-013 entry in the
  [page view behavior spec](../specs/behavior/screen-page-view.md) records.
  DocTR is the default engine (`default_engine: str = "doctr"` in
  `models.py`), so this hits most users.
- On the same machine, Ctrl+Shift+R sends a Tesseract re-run, and the server
  answers 400.
- With Tesseract installed, both shortcuts work. That is why the bug is easy to
  miss on a developer machine.

## Environment / versions

```text
pdomain-ocr-simple-gui v0.5.0 (master c029c52)
frontend/src/pages/PageViewPage.tsx
Affects machines where GET /api/config reports Tesseract as unavailable.
```

## Evidence

### 1. The Tesseract check sits on the DocTR shortcut

In `frontend/src/pages/PageViewPage.tsx`, the shortcut list reads:

```ts
{
  keys: "mod+r",
  label: "Re-run DocTR",
  handler: () => { void shortcutCtxRef.current.handleRerun("doctr"); },
  when: () =>
    !shortcutCtxRef.current.loading &&
    shortcutCtxRef.current.rerunStatus === "idle" &&
    shortcutCtxRef.current.tesseractAvailable,
},
{
  keys: "mod+shift+r",
  label: "Re-run Tesseract",
  handler: () => { void shortcutCtxRef.current.handleRerun("tesseract"); },
  when: () =>
    !shortcutCtxRef.current.loading &&
    shortcutCtxRef.current.rerunStatus === "idle",
},
```

### 2. The buttons are guarded correctly

The "Re-run Tesseract" button renders only inside
`{tesseractAvailable ? (...) : ...}`, and the DocTR button has no Tesseract
check. So the shortcuts disagree with the buttons they mirror.

## Root-cause hypotheses

1. **(Confirmed by reading the code) The `tesseractAvailable` condition was put
   on the wrong entry.** Moving it from `mod+r` to `mod+shift+r` makes the
   shortcuts match the buttons.

## Defects to fix

1. **Swapped guard:** remove `tesseractAvailable` from the `mod+r` entry and add
   it to the `mod+shift+r` entry. (Primary)
2. **Test gap:** no test presses either shortcut with Tesseract unavailable.

## Next steps

1. Write a failing frontend test. With Tesseract unavailable, Ctrl+R must call
   the DocTR re-run, and Ctrl+Shift+R must do nothing.
2. Move the condition.
3. Check that the behavior spec entries B-PAGEVIEW-013 and B-PAGEVIEW-014 still
   describe the fixed behavior, and drop their known-gap notes.

## What is NOT broken (to scope the fix)

- The "Re-run DocTR" and "Re-run Tesseract" buttons.
- The server's re-run endpoint, which correctly rejects an unavailable engine.
- The other page-view shortcuts, such as Save edits.

## Resolution

_Open._

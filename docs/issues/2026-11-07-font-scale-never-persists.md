---
Status: active
Owner: CT
Created: 2026-11-07
Last verified: 2026-11-07
Kind: issue
Level: I2
---

# The font-size setting never saves because the frontend sends `fontScale` and the backend reads `font_scale`

## Agent Index

- **Kind:** issue
- **Status:** active
- **Level:** I2
- **Last verified:** 2026-11-07
- **Resolution:** Open
- **Severity:** Medium — a user setting is silently lost on every reload.
- **Affected version:** v0.5.0; `master` at `c029c52`
- **Read when:** fixing font-size persistence, touching `uiPrefsConfig` in
  `frontend/src/App.tsx`, or changing the `ui_prefs` shape of `/api/prefs`.
- **Search terms:** fontScale, font_scale, font size, UI prefs, ui_prefs,
  B-SHELL-010, CommonUIPrefs, extra ignore, persistCommon.
- **Relates to:** [app shell behavior spec](../specs/behavior/screen-app-shell.md),
  [intent map](../context/intent-map.md)

## Summary

The font-size slider in Settings never saves. The frontend sends and reads the
value as `fontScale`, but the backend model names it `font_scale` and drops
keys it does not know. Every reload resets the font size to 1.0. The e2e test
for this behavior passes only because it writes `font_scale` straight to the
API and never goes through the frontend.

## Impact

- Anyone who changes the font size loses the setting on the next page load.
- Nothing reports the failure. The PUT returns 200, so no error toast appears.
- Theme and density are not affected. They use the same key name on both sides.

## Environment / versions

```text
pdomain-ocr-simple-gui v0.5.0 (master c029c52)
pdomain-ops 0.11.2 (CommonUIPrefs in pdomain_ops/suite/types.py)
@pdomain/pdomain-ui ^0.12.1
```

## Evidence

### 1. The frontend writes and reads `fontScale`

`persistCommon` in `frontend/src/App.tsx` sends the pdomain-ui prefs object as
is: `body: JSON.stringify({ ui_prefs: prefs })`. That object carries
`fontScale`. The loader reads it back under the same name:

```ts
ui_prefs?: { theme?: string; density?: string; fontScale?: number };
...
fontScale: typeof ui.fontScale === "number" ? ... : 1.0,
```

### 2. The backend model names the field `font_scale` and ignores unknown keys

`AppPrefs.ui_prefs` in `src/pdomain_ocr_simple_gui/models.py` is a
`CommonUIPrefs` from `pdomain-ops`. In `pdomain_ops/suite/types.py`, that model
has `extra="ignore"` and the field
`font_scale: Annotated[float, Field(ge=0.8, le=1.4)] = 1.0`. A `fontScale` key
is dropped, and `font_scale` stays at its default.

### 3. The test bypasses the frontend

`test_fontscale_persists_via_api` in `tests/e2e/test_click_paths_app_shell.py`
covers B-SHELL-010. It checks only that the slider is visible, then PUTs
`{"ui_prefs": {"font_scale": 1.2}}` with `httpx` and reads it back. It never
moves the slider or checks that the frontend reads the value after a reload.

## Root-cause hypotheses

1. **(Confirmed by reading the code) The two sides use different key names.**
   The frontend speaks the pdomain-ui camelCase shape, and the backend model is
   snake_case. No layer maps one to the other.

## Defects to fix

1. **Key mismatch:** map `fontScale` to `font_scale` in `persistCommon`, and map
   `font_scale` back to `fontScale` in the loader. (Primary) Fix it in the
   frontend, not with a backend alias. `CommonUIPrefs` lives in `pdomain-ops`
   and other suite apps share it, so changing it reaches beyond this repo.
   No other key needs mapping, because `fontScale` is the only camelCase key in
   the pdomain-ui prefs.
2. **Test gap:** the B-SHELL-010 test must exercise the frontend's own save and
   load, not only the API.

## Next steps

1. Write a failing frontend test: `persistCommon({ fontScale: 1.2, ... })` must
   send `font_scale: 1.2`, and a load of `{ ui_prefs: { font_scale: 1.2 } }`
   must return `fontScale: 1.2`.
2. Add the mapping in `uiPrefsConfig` in `frontend/src/App.tsx`.
3. Update the tests that encode the broken key. `frontend/src/__tests__/App.test.tsx`
   (around lines 570 to 604) asserts that the PUT body carries `fontScale`.
   Four e2e tests in `tests/e2e/test_click_paths_app_shell.py` PUT `fontScale`
   (lines 488, 588, 715 and 756).
4. Extend the B-SHELL-010 e2e test to set the value through the UI and check it
   after a reload.
5. Remove the known-gap notes for B-SHELL-010 and B-SHELL-011 in
   [the app shell behavior spec](../specs/behavior/screen-app-shell.md).

## What is NOT broken (to scope the fix)

- Theme and density save and load correctly.
- The backend stores and returns `font_scale` correctly when it receives it.
- The range clamp of 0.8 to 1.4 works on both sides.

## Resolution

_Open._

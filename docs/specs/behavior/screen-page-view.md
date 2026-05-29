# Behavior unit spec — Page view

- **Unit type:** screen
- **Address:** `/jobs/:id/pages/:idx`
- **Implementation:** `frontend/src/pages/PageViewPage.tsx`
- **Backend / collaborators touched:** `routes/pages.py` (page metadata,
  image, PUT text, rerun page), `routes/words.py`

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path. *Observable output* is whatever the user perceives on this
surface (DOM / toasts / route).

Records added during capture (M5).

## Known regressions

List the IDs of records tagged `Regression: yes`, with a one-line note on
what re-broke before, so reviewers know which behaviors are load-bearing.

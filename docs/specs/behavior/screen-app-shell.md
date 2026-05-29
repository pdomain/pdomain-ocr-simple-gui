# Behavior unit spec — App shell

- **Unit type:** screen
- **Address:** shell / header (wraps every route)
- **Implementation:** `frontend/src/App.tsx`
- **Backend / collaborators touched:** `routes/prefs.py`, `routes/config.py`

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path. *Observable output* is whatever the user perceives on this
surface (DOM / toasts / route).

Records added during capture (M6).

## Known regressions

List the IDs of records tagged `Regression: yes`, with a one-line note on
what re-broke before, so reviewers know which behaviors are load-bearing.

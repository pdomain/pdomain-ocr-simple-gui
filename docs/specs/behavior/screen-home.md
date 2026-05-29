# Behavior unit spec — Home

- **Unit type:** screen
- **Address:** `/` and `/new-job`
- **Implementation:** `frontend/src/pages/HomePage.tsx`
- **Backend / collaborators touched:** `routes/uploads.py`, `routes/jobs.py`,
  `routes/config.py`, `sources/*`

## Behavior records

A record is **incomplete** until both *Observable output* and *Backend /
side-effects* are filled. Every record needs a good path and at least one
bad path. *Observable output* is whatever the user perceives on this
surface (DOM / toasts / route).

Records added during capture (M3).

## Known regressions

List the IDs of records tagged `Regression: yes`, with a one-line note on
what re-broke before, so reviewers know which behaviors are load-bearing.

# Projects page — design (stub / future)

- **Date:** 2026-05-29
- **Repo:** pdomain-ocr-simple-gui
- **Status:** stub / future — not scheduled, no implementation

## Motivation

Today the only project-management surface is the **recent-projects list** at
the bottom of the HomePage (`RecentProjectsList`, `B-HOME-012` /
`B-HOME-013`). It is read-only: it renders whatever `recent_projects` the
prefs adapter happens to hold and lets the user open a row. Nothing on the
HomePage **writes** `recent_projects`, and there is no way to delete or clean
up old projects from the UI. This is a gap, not a bug — the population /
management surface was deferred.

A dedicated **Projects page** would own that surface:

- **Manage projects.** List every project under the projects root (not just
  the prefs-cached recent set), with name, last-opened, page count, engine,
  and status.
- **View previous runs.** Open any project's results, re-run, or inspect
  per-page output.
- **Delete / clean up.** Remove a project (calls the existing
  `DELETE /api/jobs/{id}`, which also prunes `recent_projects`) and clean up
  its on-disk artifacts (projects dir, output mirror, staged upload).
- **Populate `recent_projects`.** Be the authoritative writer that records a
  completed job into prefs so the HomePage recent-projects list is actually
  fed (closing the `B-HOME-012` "who writes recent_projects?" gap).

## Scope (when picked up)

- A new route (e.g. `/projects`) + `ProjectsPage` component backed by
  `GET /api/jobs` (already lists all projects) and `DELETE /api/jobs/{id}`.
- A writer that appends/updates a `recent_projects` entry on job completion
  (likely server-side in the jobs pipeline, mirroring `_remove_from_recent_projects`).
- Its own behavior spec (`screen-projects.md`) with full records once the UI
  is defined.

## Out of scope for this stub

- No implementation, no tests, no route yet.
- The stale-recent-row → 404-on-open behavior (clicking a recent row whose
  project was deleted) is tracked against **ResultsPage / M4**, not here.

## Referenced by

- `docs/specs/behavior/screen-home.md` — `B-HOME-012` and `B-HOME-013` point
  here for the future population/management surface.

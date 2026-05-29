# Behavior specs

These per-screen specs are the **source of truth** for what each screen
does. The Playwright e2e tests assert against them.

- Each behavior gets a stable ID: `B-<SCREEN>-NNN`
  (e.g. `B-HOME-001`). Cross-screen flows use `F-<FLOW>-NN`.
- A record is complete only when both its *Observable output* and its
  *Backend / side-effects* are filled, with a good path and at least one
  bad path.
- Tests cite the IDs they cover via a `Covers: B-...` docstring line or a
  `@behavior("B-...")` marker.
- `coverage.md` is **generated** — run `make behavior-coverage` to
  regenerate it. Do not edit it by hand. The gate fails on unlinked
  citations (a cited ID with no record) or uncovered regression-tagged
  records.

## Files

- `screen-home.md` — `/` and `/new-job` (HomePage)
- `screen-results.md` — `/jobs/:id` (ResultsPage)
- `screen-page-view.md` — `/jobs/:id/pages/:idx` (PageViewPage)
- `screen-app-shell.md` — shell / header (App)
- `flows.md` — cross-screen end-to-end flows
- `coverage.md` — generated traceability report

See `/workspaces/ocr-container/docs/process/behavior-e2e-capture.md` for
the methodology.

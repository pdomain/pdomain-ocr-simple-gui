---
Status: active
Owner: CT
Created: 2026-05-30
Last verified: 2026-07-14
Kind: spec
---

# Behavior specs

## Adversarial Review

- **Stage:** post-implementation
- **Source:** 2026-07-14 docgraph migration; independent read-only review of current code, tests, history, and related docs.
- **Accepted findings:** The review compared the documented contract with current implementation and accepted the material deviations recorded in the architecture and authored context.
- **Effect on result:** Shipped behavior remains active; obsolete UI or workflow assumptions are not treated as current truth.
- **Implementation deviations:** The shared jobs dock and fixed job-level download buttons replaced parts of the earlier projected surfaces. Recent projects are written at job creation. Upload/edit/download coverage does not prove edited text is present in the exported ZIP.
- **Residual risks:** Per-page edits and reruns can leave the job output mirror stale; the download redesign remains deferred.

These per-screen specs are the **source of truth** for what each screen
does. The Playwright e2e tests assert against them.

- Each behavior gets a stable ID: `B-<SCREEN>-NNN`
  (e.g. `B-HOME-001`). Cross-screen flows use `F-<DESCRIPTIVE-SEGMENTS>-NN`
  (multi-segment descriptive names allowed, e.g. `F-UPLOAD-OCR-DOWNLOAD-01`,
  `F-PREFS-ROUNDTRIP-01`).
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

## Running the tests

### Tier A — deterministic, fake dispatcher (CI)

`make e2e-fast` runs the whole `tests/e2e/` directory with `-n auto`. The
`-n auto` flag is **mandatory** — running serially causes cross-file fixture
pollution and ~29 spurious failures.

In a local-dev worktree where the registry `pdomain-ui` is broken, build
the frontend with `make local-frontend-build` first. The pytest step itself
can then run directly:

```bash
UV_NO_SYNC=1 uv run --group e2e pytest tests/e2e/ \
  -m "(slow or e2e) and not real_ocr" -n auto --no-cov
```

### Tier B — real OCR engine, GPU, opt-in (`real_ocr` marker)

Run `make local-setup-py` first to restore the editable `pdomain-book-tools`
sibling (plain `uv run` auto-syncs and reverts it to the registry pin,
causing 180 s job timeouts). Then:

```bash
UV_NO_SYNC=1 make e2e-real-ocr
```

`UV_NO_SYNC=1` is required to keep the editable sibling in place. Runs on
the local GPU box; pause if a CPU core hits ≥ 90°C.

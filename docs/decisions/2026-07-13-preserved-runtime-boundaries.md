---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-07-13
Kind: decision
---

# Preserved runtime boundaries

## Agent Index

- **Kind:** decision
- **Status:** active
- **Read when:** changing application scope, test-data handling, or packaging
  verification.
- **Search terms:** minimal consumer, test isolation, purge jobs, packaging,
  installer verification.

## Keep the application a minimal reference consumer

- **Context:** The app proves that a user can install one small OCR surface
  without installing the wider labeling or training suite.
- **Decision:** Keep the app independently installable and keep shared OCR,
  suite, and UI behavior in `pdomain-book-tools`, `pdomain-ops`, and
  `@pdomain/pdomain-ui`.
- **Rationale:** The smallest consumer exposes accidental coupling in shared
  packages and gives users a direct image-to-text workflow.
- **Evidence:** `docs/architecture/00-overview.md`, `pyproject.toml`,
  `frontend/package.json`, `pipeline.py`, and suite-registration tests. The
  original package names and phase boundaries changed, but this lower-bound
  role still ships.
- **Remaining work:** None unless a new feature would pull specialized labeler
  or trainer behavior into this app.

## Purge test artifacts instead of hiding them

- **Context:** Browser and integration fixtures can leave project artifacts in
  developer storage when cleanup is interrupted.
- **Decision:** Isolate test roots and purge recognized test artifacts. Do not
  hide leaked jobs with production list filters.
- **Rationale:** Filtering makes contaminated production state look correct and
  can hide real user projects that happen to match a test naming pattern.
- **Evidence:** `storage.py`, `_testjobs.py`,
  `src/pdomain_ocr_simple_gui/scripts/purge_test_jobs.py`,
  `tests/test_storage_isolation_guard.py`, and `tests/test_purge_test_jobs.py`.
  Current practice replaced the early filtering proposal with root isolation
  and explicit cleanup.
- **Remaining work:** Keep fixture classification synchronized with purge tests.

## Verify distribution boundaries separately

- **Context:** Unit tests run against a source checkout and cannot prove that a
  wheel contains the SPA, resources, entry points, or install-time behavior.
- **Decision:** Keep wheel, installer, and launch verification separate from
  ordinary unit and frontend tests while retaining all of them in the release
  gate.
- **Rationale:** Packaging failures appear only after files and metadata cross
  the distribution boundary.
- **Evidence:** `tests/test_packaging.py`, `tests/packaging/test_install_engine.py`,
  `tests/test_install_sh.py`, `tests/test_uninstall_sh.py`, and the Makefile
  build and release gates. The verification surface has expanded beyond the
  original one-time plan.
- **Remaining work:** Add platform coverage only when that platform becomes a
  supported distribution target.

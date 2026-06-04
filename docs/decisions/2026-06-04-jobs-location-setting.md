# Decision: configurable jobs/projects location

Date: 2026-06-04
Status: accepted

## Context

Jobs (projects) were stored under a single hardcoded default
(`~/.local/share/pdomain-suite/simple-gui/projects`), overridable only by the
`PD_OCR_SIMPLE_GUI_PROJECTS_ROOT` env var (used by tests/CI for isolation).
Users had no in-app way to choose where new OCR output lands.

## Decision

Add a user-facing `jobs_location` app pref, surfaced in a Settings → Jobs
panel, with a three-tier resolution order.

### Precedence: env > pref > default

`storage._projects_root()` resolves the projects root per call:

1. `PD_OCR_SIMPLE_GUI_PROJECTS_ROOT` env var — wins when set. This keeps the
   test-suite / CI storage-isolation guard authoritative; no test can have its
   data root silently moved by a saved pref.
2. `AppPrefs.jobs_location` pref — when non-empty, expanded (`~`) and resolved
   to an absolute path.
3. The shipped default.

Resolution is per-call, so a saved setting applies immediately (no restart).
The pref is read through the same `LocalFilePrefs` adapter the `/api/prefs`
route uses (lazy import in `storage.py` to avoid an app→routes→storage cycle).

### Switch-not-migrate

Changing `jobs_location` affects only NEW jobs. Existing jobs in the previous
location are not moved. The Settings panel states this explicitly.

### Validation on save

`PUT /api/prefs` validates a non-empty `jobs_location`: expand + resolve,
`mkdir(parents=True, exist_ok=True)`, and a write-probe. On failure it returns
`400` with `jobs location is not writable: <path>`. An empty value is always
valid (means: fall back to env/default).

`GET /api/prefs` additionally returns a read-only `effective_jobs_location`
(the root the backend would use right now) so the UI can show the current
location even when the env var is overriding the pref.

## Consequences

- Test isolation is preserved: env precedence is first, and the autouse
  conftest guard still fails the session if any resolved root escapes tmp.
- Output/jobs-meta/uploads roots are unchanged — scope is the jobs/projects
  root only.

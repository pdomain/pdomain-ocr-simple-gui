# Deep Code Review and Security Scan - 2026-05-22

Repo: `ConcaveTrillion/pd-ocr-simple-gui`

Scope: backend API/runtime, frontend GUI/privacy, dependency and supply-chain posture, CI/config, and static security scans. Four read-only subagents reviewed independent areas; the coordinating pass verified route behavior and ran local scanners.

## Verification Performed

- `cd frontend && pnpm audit --audit-level low --json`
- `uvx pip-audit --path .venv --format json`
- `uvx pip-audit --progress-spinner off --desc --format json`
- `uv run ruff check --select S src tests`
- `uvx bandit -r src -f json`
- Secret-pattern scan over tracked source with `rg`
- Manual route review and temporary-storage validation for encoded `project_id` deletion
- GitHub advisory API checks for `GHSA-4w7w-66w2-5vf9`, `GHSA-67mh-4wv8-2f99`, and the unverified Starlette advisory candidate

## Findings

### High

1. Encoded `project_id` path traversal can recursively delete the project store.
   - Evidence: `src/pd_ocr_simple_gui/storage.py:15`, `src/pd_ocr_simple_gui/routes/jobs.py:143`, `src/pd_ocr_simple_gui/routes/jobs.py:148`, `src/pd_ocr_simple_gui/storage.py:111`.
   - Impact: `DELETE /api/jobs/%2e` deletes the projects root because the route parameter is joined directly into `_PROJECTS_ROOT` and then passed to `shutil.rmtree()`.
   - Recommendation: validate `project_id` as a UUID on every route, reject decoded dot segments/separators, resolve the target, and require it to be a direct child of `_PROJECTS_ROOT`.

### Medium

2. Arbitrary local image disclosure through caller-controlled `source_path`.
   - Evidence: `src/pd_ocr_simple_gui/routes/jobs.py:25`, `src/pd_ocr_simple_gui/routes/jobs.py:99`, `src/pd_ocr_simple_gui/pipeline.py:36`, `src/pd_ocr_simple_gui/routes/pages.py:81`, `src/pd_ocr_simple_gui/routes/pages.py:91`.
   - Impact: any client that can reach the API can create a job pointing at readable local image files/directories and stream page images back through `FileResponse`.
   - Recommendation: add a per-launch capability token/auth gate, canonicalize and allowlist source roots, reject symlinks/out-of-root files, and validate served file types.

3. Unauthenticated OCR job and rerun endpoints allow CPU/GPU denial of service.
   - Evidence: `src/pd_ocr_simple_gui/routes/jobs.py:94`, `src/pd_ocr_simple_gui/routes/jobs.py:119`, `src/pd_ocr_simple_gui/pipeline.py:42`, `src/pd_ocr_simple_gui/pipeline.py:142`, `src/pd_ocr_simple_gui/routes/pages.py:112`, `src/pd_ocr_simple_gui/routes/pages.py:156`.
   - Impact: repeated submissions or reruns against large directories can consume OCR workers, CPU/GPU, and disk.
   - Recommendation: add auth/capability checks, rate limits, queue limits, max page/file-size limits, OCR timeouts, and cancellation.

4. Mounted suite launch API allows unauthenticated local process spawning.
   - Evidence: `src/pd_ocr_simple_gui/app.py:94`, `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:47`, `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:55`, `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/sibling_spawn.py:92`, `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/sibling_spawn.py:93`.
   - Impact: reachable clients can launch enabled suite apps from the local registry, consuming resources and exposing additional local services.
   - Recommendation: protect suite routes with the same auth/capability token and consider disabling launch routes unless explicitly configured.

5. Vite dev server path traversal advisory is present.
   - Evidence: `frontend/package.json:29`, `frontend/pnpm-lock.yaml:51`, `frontend/pnpm-lock.yaml:1881`, `frontend/pnpm-lock.yaml:3890`; `pnpm audit` reports `GHSA-4w7w-66w2-5vf9`.
   - Impact: affected Vite dev servers can expose optimized dependency source map files outside the intended project boundary under advisory conditions.
   - Recommendation: upgrade Vite to a patched line and update compatible frontend tooling pins.

6. esbuild dev server CORS advisory is present via Vite.
   - Evidence: `frontend/pnpm-lock.yaml:3190`, `frontend/pnpm-lock.yaml:3890`; `pnpm audit` reports `GHSA-67mh-4wv8-2f99`.
   - Impact: malicious websites can read responses from the esbuild development server, disclosing local dev-served source content.
   - Recommendation: upgrade the Vite toolchain so `esbuild` resolves to a patched version, or add a compatible `pnpm` override.

7. Private `pd-book-tools` artifacts are locked without integrity hashes.
   - Evidence: `uv.lock:1770`, `uv.lock:1795`, `uv.lock:1797`.
   - Impact: the lockfile does not cryptographically bind the private release artifacts; a changed release asset or compromised private index could be consumed without the same hash protection used for PyPI artifacts.
   - Recommendation: publish private simple-index entries with hash fragments/metadata or pin direct artifacts with hash verification and regenerate the lock.

### Low

8. Project metadata and preferences are readable/writable without authentication.
   - Evidence: `src/pd_ocr_simple_gui/routes/jobs.py:123`, `src/pd_ocr_simple_gui/routes/jobs.py:128`, `src/pd_ocr_simple_gui/routes/prefs.py:14`, `src/pd_ocr_simple_gui/routes/prefs.py:28`, `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:58`, `/workspaces/ocr-container/pd-ocr-ops/pd_ocr_ops/suite/routes.py:63`.
   - Impact: reachable clients can read project names, output paths, recent-project data, and suite preferences, then modify preferences.
   - Recommendation: require auth/capability checks and avoid returning absolute local paths where not needed.

9. Local UI loads third-party Google Fonts.
   - Evidence: `frontend/index.html:7`, `frontend/index.html:9`, `src/pd_ocr_simple_gui/frontend/index.html:7`, `src/pd_ocr_simple_gui/frontend/index.html:9`.
   - Impact: opening the local OCR app makes third-party network requests that disclose IP, user agent, and usage timing.
   - Recommendation: self-host bundled fonts or use system fonts; add a restrictive CSP once external font loading is removed.

10. Output directory is exposed as a raw `file://` href.
    - Evidence: `frontend/src/pages/ResultsPage.tsx:153`, `frontend/src/pages/ResultsPage.tsx:156`.
    - Impact: full local paths are exposed in the DOM and link target, leaking usernames and directory structure to browser extensions, screenshots, or copied links.
    - Recommendation: replace the raw link with a backend open-folder action keyed by project ID, or render only sanitized path text.

11. Suite launcher opens new tabs without `noopener`.
    - Evidence: `frontend/src/App.tsx:91` enables the launcher; `frontend/node_modules/@concavetrillion/pd-ui/dist/RightPanel-Z4PwHl58.js:19` calls `window.open(url, "_blank")`.
    - Impact: a launched sibling app can keep a `window.opener` reference and navigate the OCR GUI tab.
    - Recommendation: update the launcher to use `noopener,noreferrer` and explicitly null `opener` if needed.

12. `pd-ocr-ops` is an unversioned editable sibling dependency.
    - Evidence: `pyproject.toml:17`, `pyproject.toml:56`, `uv.lock:1801`.
    - Impact: builds and audits depend on mutable workspace state outside this repo rather than an immutable artifact, version, or commit.
    - Recommendation: depend on a versioned `pd-ocr-ops` artifact or pinned git commit; keep editable use as a local override.

13. CI uses mutable action/tool references.
    - Evidence: `.github/workflows/ci.yml:20`, `.github/workflows/ci.yml:21`, `.github/workflows/ci.yml:23`.
    - Impact: CI behavior can change when action tags or the latest `uv` release move.
    - Recommendation: pin third-party actions to commit SHAs and pin `uv` to an exact reviewed version.

14. Bandit B110: suite unregister failure is silently swallowed.
    - Evidence: `src/pd_ocr_simple_gui/__main__.py:52`.
    - Impact: unregister failures can leave stale suite registry entries without operator visibility.
    - Recommendation: log the exception at debug/warning level or return a clear CLI error where appropriate.

15. Bandit B110: suite self-registration failure is silently swallowed.
    - Evidence: `src/pd_ocr_simple_gui/app.py:61`.
    - Impact: startup can silently skip suite registration, making local routing/launch state hard to audit.
    - Recommendation: log the exception with context while preserving best-effort startup behavior.

16. Bandit B110: suite route mounting failure is silently swallowed.
    - Evidence: `src/pd_ocr_simple_gui/app.py:99`.
    - Impact: suite API and health-route availability can silently diverge from expectations.
    - Recommendation: log the exception with context and expose health diagnostics for disabled suite routes.

17. Bandit B110: failed-status persistence failure is silently swallowed.
    - Evidence: `src/pd_ocr_simple_gui/routes/jobs.py:90`.
    - Impact: a background OCR failure can leave stale queued/running state with no durable error trail.
    - Recommendation: log the secondary persistence failure and retain the original job failure context.

18. Bandit B110: recent-project preference update failure is silently swallowed.
    - Evidence: `src/pd_ocr_simple_gui/routes/jobs.py:200`.
    - Impact: deleted projects can remain in recent-project metadata without visibility.
    - Recommendation: log the prefs update failure at debug/warning level.

19. Bandit B110: unreadable project directories are silently skipped.
    - Evidence: `src/pd_ocr_simple_gui/storage.py:106`.
    - Impact: malformed or tampered project records disappear from listings without audit visibility.
    - Recommendation: log skipped project directories with enough context for troubleshooting.

## Non-Finding Notes

- A reported candidate Starlette advisory for `GHSA-86qp-5c8j-p5mr` could not be verified: GitHub's advisory API returned 404, web search did not find the advisory, and a fresh `pip-audit` run did not report Starlette. No issue was filed for that candidate.
- `uvx pip-audit --path .venv --format json` reported no known Python vulnerabilities in the installed environment.
- The secret-pattern scan found no tracked application secrets.

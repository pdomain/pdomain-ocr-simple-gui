---
Status: active
Owner: CT
Created: 2026-11-13
Last verified: 2026-11-13
Kind: architecture
---

# Quality gates and distribution

The local Just gate verifies the Python app, frontend, browser behavior, and
packaged SPA together. These checks remain separate because a source test
cannot prove what a wheel contains. The
[preserved runtime boundaries](../decisions/2026-07-13-preserved-runtime-boundaries.md)
record that constraint.

## Gate ownership and order

The Python recipes use uv. Frontend recipes use the `frontend-` prefix and run
pnpm in `frontend/`, through mise when it is installed. The pinned Node and pnpm
versions come from `mise.toml`. Setup installs the Python lock with `--locked`.
Frontend installation uses `--frozen-lockfile` and snapshots
`frontend/pnpm-workspace.yaml`; an install that rewrites it restores the snapshot
and fails, including when installation itself failed.

The `ci` dependency graph runs that frozen frontend install once. It includes
pre-commit, read-only Python lint/format checks, configured basedpyright,
frontend typecheck/build, ordinary pytest, behavior coverage, smoke, packaging
tests, frontend format/lint checks, Vitest, knip, and fast browser e2e. It then
builds release artifacts and runs strict docgraph.

`ci-slow` is the release preflight. It runs `ci`, then the real-OCR acceptance
test (`just real-ocr-acceptance`, `tests/e2e/test_real_ocr_acceptance.py`).
That test uploads a page in headless chromium, runs real DocTR on the CPU with
CUDA hidden, saves an edit, reruns the page with Tesseract, and checks the
downloaded ZIP after each step. It has no skip path. A missing chromium, model
weight, or `tesseract` binary fails the recipe. The recipe also fails when
pytest reports no test run or any skip. `scripts/do-release.sh` pins
`RELEASE_PREFLIGHT` to `just ci-slow`, so an environment override cannot drop
it. Plain `ci` does not run this test and prints a note saying so.

Ordinary pytest keeps `tests/ -v -n auto` and the `not slow` selection and
branch-coverage options in `pyproject.toml`. Smoke selects `slow or e2e`.
Packaging selects slow tests from `tests/test_packaging.py`. Fast browser e2e
uses the fake dispatcher, selects `(slow or e2e) and not real_ocr`, and disables
coverage for that browser run. The other real-OCR browser tests
(`just e2e-real-ocr`, on the GPU) remain opt-in.
OpenAPI export is not part of this app's CI graph.

Frontend typecheck is `tsc --noEmit`; build is `tsc && vite build`. CI checks
ESLint with zero allowed warnings, and Vitest runs without an empty-suite
success override. Generated API types stay out of Prettier. Formatting and
lint checks do not fix source. The separate fix recipes remain available.

Every public recipe supports `AI=1`: the full output goes to `.ci-ai.log`, with
one success line or the failure tail on the terminal. The contributor
[guidance](../../CLAUDE.md) lists commands.

## Test servers and asynchronous completion

Browser and smoke subprocesses bind uvicorn to port zero and read the actual
bound port from its startup log. They never reserve a free port, close its
socket, and assume the later server owns it. Readiness checks target that
server, and startup fails when the child exits before publishing a port.
Tests hold a decoy port to verify that another server cannot be adopted.

Browser assertions wait for the condition they measure. The successful word
overlay test waits for a positive word count. Its empty-state counterpart
waits for the words response and checks 404 before asserting zero. The upload
flow polls until the job is terminal before checking success. These waits
preserve the distinction between an initial empty render and a completed
operation.

The ordinary test runner gives early imports a temporary `PD_SUITE_DATA_DIR`.
Shared fixtures isolate the remaining storage roots. Browser server fixtures
require a temporary suite directory before launching; this prevents reset
fixtures from overwriting the desktop's real suite data.

## SPA distribution

Build order is frontend build, explicit `uv build --sdist`, then explicit
`uv build --wheel`, both from the source checkout. The ignored SPA lives under
`src/pdomain_ocr_simple_gui/frontend/`. Hatch's global `artifacts` setting
includes it in both distributions. A wheel rebuilt from an unpacked sdist must
also contain the SPA. Packaging tests verify all three artifact paths.

The release helper runs the preflight before creating an annotated tag, pushes
the branch and exact tag, builds locally, and attaches the wheel and sdist to a
GitHub Release. Index publication is a separate operation. No installed
consumer or live service is upgraded by these recipes. Follow the
[release runbook](../runbooks/release.md) for the procedure.

## Evidence

- Code: `justfile`, `pyproject.toml`, `mise.toml`,
  `frontend/package.json`, `tests/conftest.py`, `tests/e2e/conftest.py`,
  `tests/smoke/test_e2e.py`, `scripts/do-release.sh`, and
  `scripts/release-common.sh`.
- Tests: `tests/test_e2e_boot_server.py`, `tests/test_smoke_boot_server.py`,
  `tests/test_setup_defaults.py`, `tests/test_packaging.py`,
  `tests/e2e/test_click_paths_page_viewer.py`, `tests/e2e/test_flows.py`,
  `tests/e2e/test_real_ocr_acceptance.py`, and `tests/test_download_freshness.py`.
- Artifacts: the SPA, wheel, and source distribution in `dist/`.
- Verified: 2026-11-13 by source inspection against commits `996bc7e`,
  `6889d3f`, `e4c3c14`, `630e2e0`, `0451c26`, `73cacdd`, and `60020aa`.

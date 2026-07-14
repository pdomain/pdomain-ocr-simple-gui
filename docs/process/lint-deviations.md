---
Status: active
Owner: CT
Created: 2026-05-26
Last verified: 2026-07-14
Kind: process
---

# Lint-rule Deviations — pdomain-ocr-simple-gui

Standing suppressions and per-file rule overrides in this repo.
Each entry records: the rule, the tool, the file(s) affected, and
the justification. Update this file whenever a new suppression is added.

---

## Global ruff ignores (`[tool.ruff.lint] ignore`)

| Rule | Justification |
|------|---------------|
| `B008` | FastAPI's `Depends()` is called in function defaults — the canonical FastAPI DI pattern; flagging it is a false positive. |
| `E501` | Line-length enforced by formatter at `line-length = 110`; no need to duplicate as an error. |
| `D203` | Conflicts with `D211` (no blank line before class docstring). `D212` style chosen. |
| `D212` | See `D203` — pydocstyle multi-line format; only one of the pair can be active. |
| `D100` | Missing module docstring — thin module files (routes, models) are self-describing via their contents. |
| `D104` | Missing package `__init__` docstring — all `__init__.py` files are empty or re-export only. |
| `D107` | Missing `__init__` method docstring — Pydantic models inherit docs from class; redundant on `__init__`. |
| `PLR0913` | Too-many-arguments — FastAPI route functions necessarily accept many path/query/body parameters at once. |
| `PLR2004` | Magic-value comparison — HTTP status codes (`== 200`, `== 404`, etc.) are more readable as literals. |
| `TRY003` | Long exception messages — informative error messages in `raise` are preferred over short codes. |
| `TRY301` | Abstract-raise helpers would split short, local validation branches without improving reuse. |
| `COM812` | Trailing comma enforcement conflicts with ruff formatter's own comma handling; formatter is authoritative. |
| `PLC0415` | Import not at top-level — suite registration block in `app.py` uses deferred import to avoid circular deps on startup. |
| `PLR0912` | Too-many-branches — pipeline and route handlers have inherent branching; refactoring would obscure intent. |
| `PLR0911` | Too-many-return-statements — similar rationale to `PLR0912`. |
| `PLR0915` | Too-many-statements — same rationale. |
| `ANN401` | `Any` in type annotation — used in a small number of FastAPI dependency overrides where `Any` is correct. |
| `D205` | Blank line required between summary and description — style conflicts with project docstring style. |
| `D105` | Missing docstring in magic method — `__repr__`, `__str__`, etc. are self-describing. |

---

## Per-file ignores (`[tool.ruff.lint.per-file-ignores]`)

### `tests/*`

Suppressed: `E741 N806 S101 S104 S105 S106 S301 S311 S603 T201 ANN D PLR2004 PT011 PT018 S108 PLR0133 PLW2901 PLW1510 PERF401 PERF402 TRY BLE001 TC`

**Justification:** Test files use `assert` (S101), `print` for debugging (T201),
magic numbers for expected HTTP status codes (PLR2004), subprocess calls (S603),
hardcoded bind addresses (S104), and do not require type annotations or docstrings.
These suppressions are standard across all pd-* repos.

### `scripts/*.py`

Suppressed: `T201 D ANN S603 S607 PLW1510`

**Justification:** Scripts are developer tooling, not library code — print output
is intentional, docstrings are optional, and subprocess calls are expected.

### `**/__init__.py`

Suppressed: `D104 F401 TC`

**Justification:** Package init files are legitimately empty or contain only
re-exports. `F401` (imported but unused) is suppressed because re-exports look
unused to linters.

### `**/_*.py`

Suppressed: `D`

**Justification:** Private implementation modules (named `_*.py`) do not require
public-facing docstrings.

### `src/pdomain_ocr_simple_gui/__main__.py`

Suppressed: `ANN D T201`

**Justification:** Entry-point script — no annotations or docstrings required;
`print` output to stderr for startup messages is intentional.

---

## Inline suppressions

This inventory records every current inline suppression location. New entries
must use a narrow Ruff code or basedpyright-native `pyright: ignore` rule and a
local safety rationale. Historical mypy-style comments are migration debt, not
an approved pattern.

### `BLE001` (blind exception catch) — multiple files

**Files:** `src/pdomain_ocr_simple_gui/scripts/purge_test_jobs.py` and
`installer/install_engine.py`.

**Suppression form:** `except Exception:  # noqa: BLE001`

**Justification:** At startup and in background tasks, broad exception catching is
intentional at these boundaries. The purge command treats malformed JSON and I/O
failures as unreadable input; installer probes treat unavailable system commands
as absent capabilities.

### `TC002`/`TC003` (type-checking imports) — `models.py`

**Files:** `src/pdomain_ocr_simple_gui/models.py`

**Suppression form:** `# noqa: TC002` / `# noqa: TC003`

**Justification:** `datetime` and `CommonUIPrefs` are used both at runtime (for
Pydantic field types) and for type annotations. Moving them inside `TYPE_CHECKING`
would break Pydantic's runtime introspection.

### `PLW0603` (global statement) — `app.py`

**Files:** `src/pdomain_ocr_simple_gui/app.py`

**Suppression form:** `global _prefs_adapter, _dispatcher  # noqa: PLW0603`

**Justification:** Module-level singleton state for the FastAPI lifespan pattern.
The globals are initialized once in `startup` and torn down in `shutdown`; this
is the standard pattern for FastAPI app-level state before `app.state` was common.

### Other inline Ruff suppressions

- `N818`: `statecharts/job_lifecycle.py` and `sources/__init__.py`; public
  exception names preserve the domain vocabulary used by callers.
- `TC002`/`TC003`: `models.py` and `output/config.py`; Pydantic needs these
  annotation types at runtime.
- `SIM112`: `runtime/container_detect.py`; OCI runtimes define the lowercase
  `container` variable.
- `S104`: `__main__.py`; wildcard bind addresses are normalized to loopback for
  browser launch.
- `S603`, `S607`, and `T201`: `installer/install_engine.py`,
  `installer/wizard.py`, and `scripts/purge_test_jobs.py`; these command-line
  tools intentionally run fixed subprocess arguments and print operator output.

### Type-checker boundary suppressions

**Production and installer files:** `app.py`, `auth.py`, `models.py`,
`storage.py`, `routes/downloads.py`, `runtime/ocr_engines.py`,
`statecharts/job_lifecycle.py`, `scripts/purge_test_jobs.py`,
`installer/install_engine.py`, and `installer/wizard.py`.

**Test files:** `tests/conftest.py`, `tests/e2e/conftest.py`,
`tests/e2e/fixtures/_make_known_good_page.py`, `tests/factories.py`,
`tests/packaging/test_install_engine.py`, `tests/smoke/test_e2e.py`,
`tests/test_dynamic_port.py`, `tests/test_entrypoint.py`,
`tests/test_fake_dispatcher.py`, `tests/test_jobs_location_pref.py`,
`tests/test_models.py`, `tests/test_pipeline.py`, `tests/test_purge_test_jobs.py`,
`tests/test_security_auth_token.py`, `tests/test_suite.py`,
and `tests/test_update_github_actions.py`.

**Justification:**

- Third-party boundaries cover dynamic FastAPI dependency defaults,
  `python-statemachine`, untyped `pytesseract`, and resource traversables.
- Test-only boundaries cover dynamic fixtures, monkeypatches, fake callables,
  `subprocess.CompletedProcess` generics, socket tuples, and deliberately broad
  factory inputs.
- `scripts/purge_test_jobs.py`, `storage.py`, `app.py`, and several tests still
  contain historical mypy-style comments. They are fully catalogued here but
  must be converted when the affected boundary is next changed.

### Configured basedpyright suppression

**Rule:** `reportImportCycles = "none"` in `pyproject.toml`.

**Justification:** FastAPI route registration and application assembly create
intentional import cycles that do not affect runtime initialization. All other
recommended diagnostics remain enabled and warnings fail the type gate.

---

## Frontend ESLint suppressions

### `react-hooks/exhaustive-deps` — `PageViewPage.tsx`

**Files:** `frontend/src/pages/PageViewPage.tsx` (two focused disables)

**Suppression form:** `// eslint-disable-next-line react-hooks/exhaustive-deps`

**Justification:** The page loader and navigation effects intentionally exclude
derived callbacks whose identity changes without changing the requested job or
page. The local comments identify the dependency boundary.

## Audit method

The 2026-07-14 migration compared this catalogue with source and configuration
using `rg` over Python, TOML, YAML, and frontend files, then ran Ruff and
basedpyright. The unused speculative `UP042` global ignore was removed.

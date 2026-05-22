# Lint-rule Deviations — pd-ocr-simple-gui

Standing suppressions and per-file rule overrides in this repo.
Each entry records: the rule, the tool, the file(s) affected, and
the justification. Update this file whenever a new suppression is added.

---

## Global ruff ignores (`[tool.ruff.lint] ignore`)

| Rule | Justification |
|------|---------------|
| `B008` | FastAPI's `Depends()` is called in function defaults — the canonical FastAPI DI pattern; flagging it is a false positive. |
| `UP042` | No current use; reserved so rule doesn't block future stdlib compat code. |
| `E501` | Line-length enforced by formatter at `line-length = 110`; no need to duplicate as an error. |
| `D203` | Conflicts with `D211` (no blank line before class docstring). `D212` style chosen. |
| `D212` | See `D203` — pydocstyle multi-line format; only one of the pair can be active. |
| `D100` | Missing module docstring — thin module files (routes, models) are self-describing via their contents. |
| `D104` | Missing package `__init__` docstring — all `__init__.py` files are empty or re-export only. |
| `D107` | Missing `__init__` method docstring — Pydantic models inherit docs from class; redundant on `__init__`. |
| `PLR0913` | Too-many-arguments — FastAPI route functions necessarily accept many path/query/body parameters at once. |
| `PLR2004` | Magic-value comparison — HTTP status codes (`== 200`, `== 404`, etc.) are more readable as literals. |
| `TRY003` | Long exception messages — informative error messages in `raise` are preferred over short codes. |
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

### `src/pd_ocr_simple_gui/__main__.py`

Suppressed: `ANN D T201`

**Justification:** Entry-point script — no annotations or docstrings required;
`print` output to stderr for startup messages is intentional.

---

## Inline suppressions

### `BLE001` (blind exception catch) — multiple files

**Files:** `app.py`, `storage.py`, `routes/jobs.py`, `routes/pages.py`, `pipeline.py`, `__main__.py`

**Suppression form:** `except Exception:  # noqa: BLE001`

**Justification:** At startup and in background tasks, broad exception catching is
intentional — the app must not crash if optional integrations (suite registration,
prefs loading, OCR engine init) fail. Each `except` block logs the error and
continues gracefully. The `S110` co-suppression (`try-except-pass` without logging
is also silenced where logging is deliberately omitted for non-critical paths).

### `TC002`/`TC003` (type-checking imports) — `models.py`

**Files:** `src/pd_ocr_simple_gui/models.py`

**Suppression form:** `# noqa: TC002` / `# noqa: TC003`

**Justification:** `datetime` and `CommonUIPrefs` are used both at runtime (for
Pydantic field types) and for type annotations. Moving them inside `TYPE_CHECKING`
would break Pydantic's runtime introspection.

### `PLW0603` (global statement) — `app.py`

**Files:** `src/pd_ocr_simple_gui/app.py`

**Suppression form:** `global _prefs_adapter, _dispatcher  # noqa: PLW0603`

**Justification:** Module-level singleton state for the FastAPI lifespan pattern.
The globals are initialized once in `startup` and torn down in `shutdown`; this
is the standard pattern for FastAPI app-level state before `app.state` was common.

### `E402` (module-level import not at top) — `app.py`

**Files:** `src/pd_ocr_simple_gui/app.py`

**Suppression form:** `# noqa: E402` on three router imports

**Justification:** Router imports follow a try/except block that loads optional
suite integration. Placing the imports before the try block would introduce a
circular import. The deferred pattern is intentional.

### `type: ignore[no-any-return]` / `type: ignore[arg-type]` / `type: ignore[attr-defined]` — various

**Files:** `storage.py`, `app.py`, `tests/test_suite.py`, `tests/e2e/conftest.py`

**Suppression form:** `# type: ignore[<code>]`

**Justification:**

- `storage.py: no-any-return` — `json.loads()` returns `Any`; the caller knows
  the shape and validates via Pydantic downstream.
- `storage.py: arg-type` — aggregated state value from a dict comprehension is
  a string, which the `ProjectStatusState` literal accepts; basedpyright doesn't
  narrow through the dict lookup.
- `app.py: attr-defined` — `importlib.resources` traversable objects have
  `.read_bytes()` at runtime but basedpyright doesn't resolve the protocol fully.
- `test_suite.py: attr-defined` — same importlib traversable issue in test helpers.
- `conftest.py: return-value` — `socket.getsockname()` returns a tuple; indexing
  returns `Any` which we know is `int` here.

---

## Frontend ESLint suppressions

### `@typescript-eslint/no-explicit-any` — test files

**Files:** `App.test.tsx`, `JobConfigDialog.test.tsx`, `PageViewPage.test.tsx`,
`ResultsPage.test.tsx`

**Suppression form:** `// eslint-disable-next-line @typescript-eslint/no-explicit-any`

**Justification:** Test mocks for `vi.fn()` return types and MSW handler bodies
need `any` to accept arbitrary response shapes. Production code does not use `any`.

### `react-hooks/exhaustive-deps` — `ResultsPage.tsx`

**Files:** `frontend/src/pages/ResultsPage.tsx`

**Suppression form:** `// eslint-disable-next-line react-hooks/exhaustive-deps`

**Justification:** The polling `useEffect` deliberately excludes `pollingActive`
from its dependency array to avoid re-starting the interval on every render tick.
The interval is controlled by the `pollingActive` ref, not re-created on state
changes. Adding it to deps would break the polling logic.

### `react/no-unknown-property` — `DropZone.tsx`

**Files:** `frontend/src/components/DropZone.tsx`

**Suppression form:** `// eslint-disable-next-line react/no-unknown-property`

**Justification:** The `webkitdirectory` attribute is a non-standard but widely
supported DOM attribute for directory picker inputs. React's JSX type definitions
do not include it; the suppression is intentional and the attribute works in all
target browsers.

---

## Needs review

None currently flagged.

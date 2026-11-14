set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set positional-arguments

# Copy this wrapper and install-hooks with the shell setting to sibling justfiles.
[private]
_ai +args:
    #!/usr/bin/env bash
    set -euo pipefail
    if env AI= just --quiet "$@" > .ci-ai.log 2>&1; then
        printf 'PASS: %s\n' "$*"
    else
        result=$?
        printf 'FAIL: %s (exit %s)\n' "$*" "$result"
        if [[ -f scripts/ai_filter_log.py ]]; then
            uv run python scripts/ai_filter_log.py .ci-ai.log
        else
            tail -50 .ci-ai.log
        fi
        exit "$result"
    fi

install-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai install-hooks; fi
    if [[ -f .git ]]; then
        echo "hooks: worktree checkout - the canonical repo owns them, skipping"
    elif [[ -n "$(git config --get core.hooksPath || true)" ]]; then
        echo "hooks: core.hooksPath is set - leaving it alone, skipping"
    else
        uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
    fi

[private]
_pnpm +args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd frontend
    printf 'pnpm (%s):' "$PWD"
    printf ' %q' "$@"
    printf '\n'
    mise="$(command -v mise || printf '%s/.local/bin/mise' "$HOME")"
    if [[ -x "$mise" ]]; then
        exec "$mise" exec -- pnpm "$@"
    elif command -v pnpm >/dev/null 2>&1; then
        exec pnpm "$@"
    else
        echo "No pnpm/mise available. Install the pinned tools with mise install." >&2
        exit 1
    fi

help:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai help; fi
    just --list

setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai setup; fi
    uv sync --locked --group dev --group e2e
    uv run --group e2e playwright install chromium || true
    just --quiet install-hooks

install:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai install; fi
    just --quiet setup

uninstall:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai uninstall; fi
    uv tool uninstall pdomain-ocr-simple-gui || true
    echo "pdomain-ocr-simple-gui uninstalled."

remove-venv:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai remove-venv; fi
    rm -rf "${UV_PROJECT_ENVIRONMENT:-.venv}"

reset:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai reset; fi
    just --quiet _task-reset

[private]
_task-reset: clean remove-venv setup
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Environment Reset!"

upgrade-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai upgrade-deps; fi
    for marker in "${UV_PROJECT_ENVIRONMENT:-.venv}/.pdomain-local-mode" "${UV_PROJECT_ENVIRONMENT:-.venv}/.pdomain-dev-local"; do
        if [[ -f "$marker" ]]; then
            echo "Refusing dependency upgrades while $marker exists" >&2
            exit 1
        fi
    done
    uv lock --upgrade
    uv sync --group dev

dev-local:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai dev-local; fi
    echo "dev-local is deprecated. Use local-dev for the standard local-dev workflow."
    just --quiet local-dev

lint:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai lint; fi
    uv run ruff check --select I --fix
    uv run ruff check --fix

lint-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai lint-check; fi
    uv run ruff format --check
    uv run ruff check

format:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai format; fi
    uv run ruff format

format-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai format-check; fi
    uv run ruff format --check

typecheck:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai typecheck; fi
    uv run basedpyright src/pdomain_ocr_simple_gui installer/

pre-commit-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai pre-commit-check; fi
    uv run pre-commit run --all-files

update-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai update-hooks; fi
    uv run pre-commit autoupdate --freeze

test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai test; fi
    # Imports before test fixtures must not discover the owner's suite registry.
    suite_data="$(mktemp -d)"
    trap 'rm -rf "$suite_data"' EXIT
    PD_SUITE_DATA_DIR="$suite_data" uv run pytest tests/ -v -n auto

behavior-coverage:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai behavior-coverage; fi
    uv run python -m scripts.behavior_coverage

smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai smoke; fi
    uv run pytest tests/smoke/ -v -n auto -m "slow or e2e"

packaging-test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai packaging-test; fi
    just --quiet _task-packaging-test

[private]
_task-packaging-test: _task-frontend-build
    #!/usr/bin/env bash
    set -euo pipefail
    uv run pytest tests/test_packaging.py -m slow -v -n auto

e2e-fast:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai e2e-fast; fi
    just --quiet _task-e2e-fast

[private]
_task-e2e-fast: _task-frontend-build
    #!/usr/bin/env bash
    set -euo pipefail
    PDOMAIN_OCR_FAKE_DISPATCHER=1 uv run --group e2e pytest tests/e2e/ -v -m "(slow or e2e) and not real_ocr" --no-cov -n auto

e2e-browser:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai e2e-browser; fi
    just --quiet _task-e2e-browser

[private]
_task-e2e-browser: _task-frontend-build
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --group e2e pytest tests/e2e/ -v -n auto -m "slow or e2e" --no-cov

e2e-real-ocr:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai e2e-real-ocr; fi
    just --quiet _task-e2e-real-ocr

[private]
_task-e2e-real-ocr: _task-frontend-build
    #!/usr/bin/env bash
    set -euo pipefail
    uv run --group e2e pytest tests/e2e/test_real_ocr_*.py -v -n auto -m "real_ocr" --no-cov

# Release acceptance: real OCR on the CPU in headless chromium (upload, OCR, edit, rerun, ZIP export).
real-ocr-acceptance:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai real-ocr-acceptance; fi
    just --quiet _task-real-ocr-acceptance

[private]
_task-real-ocr-acceptance: _task-frontend-build
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v tesseract >/dev/null; then
        echo "ERROR: real-OCR acceptance needs the tesseract binary; install it. Release is blocked." >&2
        exit 1
    fi
    report_dir=$(mktemp -d)
    trap 'rm -rf "$report_dir"' EXIT
    rc=0
    PDOMAIN_OCR_FAKE_DISPATCHER= PDOMAIN_GPU_BACKEND=cpu CUDA_VISIBLE_DEVICES= \
        uv run --group e2e pytest tests/e2e/test_real_ocr_acceptance.py -v -m real_ocr --no-cov \
        -p no:cacheprovider --junitxml="$report_dir/report.xml" || rc=$?
    if [[ "$rc" -ne 0 ]]; then
        echo "ERROR: real-OCR acceptance failed (pytest exit $rc). Release is blocked." >&2
        exit "$rc"
    fi
    uv run python - "$report_dir/report.xml" <<'PY'
    import sys
    import xml.etree.ElementTree as ET

    suite = ET.parse(sys.argv[1]).getroot()
    suite = suite if suite.tag == "testsuite" else suite[0]
    tests, skipped = int(suite.get("tests", "0")), int(suite.get("skipped", "0"))
    if tests < 1 or skipped:
        sys.exit(f"ERROR: real-OCR acceptance ran {tests} test(s), skipped {skipped}. Release is blocked.")
    print(f"real-OCR acceptance: {tests} passed, 0 skipped")
    PY

frontend-install:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-install; fi
    # Detect pnpm's rewrite even when installation fails, then restore the snapshot.
    cp frontend/pnpm-workspace.yaml frontend/pnpm-workspace.yaml.preinstall
    rc=0
    CI=true just --quiet _pnpm install --frozen-lockfile || rc=$?
    if ! diff -q frontend/pnpm-workspace.yaml.preinstall frontend/pnpm-workspace.yaml >/dev/null 2>&1; then
        echo "pnpm install mutated frontend/pnpm-workspace.yaml:"
        diff frontend/pnpm-workspace.yaml.preinstall frontend/pnpm-workspace.yaml || true
        echo "Add the new dependency build-script approval to frontend/pnpm-workspace.yaml."
        mv frontend/pnpm-workspace.yaml.preinstall frontend/pnpm-workspace.yaml
        exit 1
    fi
    rm -f frontend/pnpm-workspace.yaml.preinstall
    exit "$rc"

frontend-test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-test; fi
    just --quiet _task-frontend-test

[private]
_task-frontend-test: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run test

frontend-build:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-build; fi
    just --quiet _task-frontend-build

[private]
_task-frontend-build: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run build

frontend-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-dev; fi
    just --quiet _task-frontend-dev

[private]
_task-frontend-dev: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run dev

frontend-typecheck:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-typecheck; fi
    just --quiet _task-frontend-typecheck

[private]
_task-frontend-typecheck: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run typecheck

frontend-lint:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-lint; fi
    just --quiet _task-frontend-lint

[private]
_task-frontend-lint: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm exec eslint . --fix

frontend-lint-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-lint-check; fi
    just --quiet _task-frontend-lint-check

[private]
_task-frontend-lint-check: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm exec eslint . --max-warnings 0

frontend-format:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-format; fi
    just --quiet _task-frontend-format

[private]
_task-frontend-format: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run format

frontend-format-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-format-check; fi
    just --quiet _task-frontend-format-check

[private]
_task-frontend-format-check: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run format:check

frontend-knip:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai frontend-knip; fi
    just --quiet _task-frontend-knip

[private]
_task-frontend-knip: frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run knip

openapi-export:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai openapi-export; fi
    uv run python scripts/export_openapi.py openapi.json
    mise="$(command -v mise || printf '%s/.local/bin/mise' "$HOME")"
    cd frontend
    if [[ -x "$mise" ]]; then
        "$mise" exec -- npx --yes openapi-typescript ../openapi.json -o src/api/types.gen.ts
    else
        npx --yes openapi-typescript ../openapi.json -o src/api/types.gen.ts
    fi

clean:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai clean; fi
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    rm -rf dist/ 2>/dev/null || true

build:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai build; fi
    just --quiet frontend-build
    uv build --sdist
    uv build --wheel

[private]
_task-build: _task-frontend-build
    #!/usr/bin/env bash
    set -euo pipefail
    uv build --sdist
    uv build --wheel

[default]
ci:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai ci; fi
    just --quiet _task-ci

[private]
_task-ci: setup frontend-install pre-commit-check lint-check typecheck _task-frontend-typecheck _task-frontend-build test behavior-coverage smoke _task-packaging-test _task-frontend-format-check _task-frontend-lint-check _task-frontend-test _task-frontend-knip _task-e2e-fast _task-build
    #!/usr/bin/env bash
    set -euo pipefail
    docgraph check --strict
    echo "NOTE: just ci does not run the real-OCR browser acceptance test; just ci-slow (the release preflight) does."

# Release preflight: the full gate plus the real-OCR acceptance test.
ci-slow:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai ci-slow; fi
    just --quiet ci
    just --quiet _task-real-ocr-acceptance

ci-full:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai ci-full; fi
    just --quiet _task-ci-full

[private]
_task-ci-full: _task-ci _task-e2e-browser smoke

run:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai run; fi
    spa_bundle=src/pdomain_ocr_simple_gui/frontend/index.html
    spa_srcs=(frontend/src frontend/index.html frontend/package.json frontend/vite.config.ts frontend/postcss.config.js frontend/tsconfig.json frontend/tsconfig.node.json)
    if [[ ! -f "$spa_bundle" ]] || [[ -n "$(find "${spa_srcs[@]}" -newer "$spa_bundle" 2>/dev/null)" ]]; then
        echo "SPA bundle stale or missing; running frontend-build first..."
        just --quiet frontend-build
    else
        echo "SPA bundle up to date."
    fi
    uv run pdomain-ocr-simple-gui ${ARGS:-}

local-setup:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-setup; fi
    ./scripts/local-setup.sh

local-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-dev; fi
    ./scripts/local-dev.sh

local-check:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-check; fi
    ./scripts/local-check.sh

local-upgrade-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-upgrade-deps; fi
    ./scripts/local-upgrade-deps.sh

local-run:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-run; fi
    ./scripts/local-run.sh

local-setup-py:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-setup-py; fi
    ./scripts/local-setup-py.sh

local-frontend-install:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-frontend-install; fi
    ./scripts/local-frontend-install.sh

ci-against-master:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai ci-against-master; fi
    ./scripts/ci-against-master.sh

local-frontend-build:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-frontend-build; fi
    just --quiet _task-local-frontend-build

[private]
_task-local-frontend-build: local-frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run build

local-frontend-test:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-frontend-test; fi
    just --quiet _task-local-frontend-test

[private]
_task-local-frontend-test: local-frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run test

local-frontend-dev:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai local-frontend-dev; fi
    just --quiet _task-local-frontend-dev

[private]
_task-local-frontend-dev: local-frontend-install
    #!/usr/bin/env bash
    set -euo pipefail
    just --quiet _pnpm run dev

update-pdomain-deps:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai update-pdomain-deps; fi
    for marker in "${UV_PROJECT_ENVIRONMENT:-.venv}/.pdomain-local-mode" "${UV_PROJECT_ENVIRONMENT:-.venv}/.pdomain-dev-local"; do
        if [[ -f "$marker" ]]; then
            echo "Refusing dependency upgrades while $marker exists" >&2
            exit 1
        fi
    done
    ./scripts/update-pdomain-deps.sh

upgrade-pdomain-book-tools:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai upgrade-pdomain-book-tools; fi
    echo "upgrade-pdomain-book-tools is deprecated. Use update-pdomain-deps for all sibling deps."
    just --quiet update-pdomain-deps

release-patch:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai release-patch; fi
    BUMP=patch ./scripts/do-release.sh

release-minor:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai release-minor; fi
    BUMP=minor ./scripts/do-release.sh

release-major:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai release-major; fi
    BUMP=major ./scripts/do-release.sh

[private]
_do-release:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "${AI:-}" ]]; then exec just --quiet _ai _do-release; fi
    BUMP="${BUMP:-minor}" ./scripts/do-release.sh

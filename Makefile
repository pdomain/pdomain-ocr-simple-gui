AI ?=
LOG := .ci-ai.log

ifdef AI
_goals := $(or $(MAKECMDGOALS),ci)
.PHONY: $(_goals)
$(_goals):
	@rm -f $(LOG)
	@$(MAKE) --no-print-directory AI= $@ > $(LOG) 2>&1 \
		&& echo "✅ $@ passed (log: $(LOG))" \
		|| (echo "❌ $@ failed:"; grep -E "(FAILED|ERROR|error|Error)" $(LOG) | head -30; echo "(full log: $(LOG))"; exit 1)

else

MISE := $(shell command -v mise 2>/dev/null || echo $$HOME/.local/bin/mise)
HAVE_MISE = [ -x "$(MISE)" ]
MISE_RUN = if $(HAVE_MISE); then $(MISE) exec --; fi

# Run pnpm through mise if available, else fall back to PATH pnpm/npm
define _pnpm
	if $(HAVE_MISE); then \
		$(MISE) exec -- pnpm $(1); \
	elif command -v pnpm >/dev/null 2>&1; then \
		pnpm $(1); \
	else \
		echo "❌ no pnpm/mise available. Run 'make mise-setup' or install Node."; \
		exit 1; \
	fi
endef

PEER_BOOK_TOOLS_PATH ?= ../pdomain-book-tools

.PHONY: help setup install uninstall remove-venv reset lint format format-check typecheck \
        pre-commit-check test behavior-coverage e2e-fast e2e-browser e2e-real-ocr frontend-install frontend-build frontend-dev \
        frontend-test frontend-lint frontend-format frontend-format-check frontend-knip \
        openapi-export clean ci ci-full upgrade-deps dev-local \
        local-setup local-dev local-check local-upgrade-deps local-run \
        local-setup-py local-frontend-install local-frontend-build \
        local-frontend-test local-frontend-dev \
        update-pdomain-deps upgrade-pdomain-book-tools \
        release-patch release-minor release-major _do-release ci-slow build packaging-test ci-against-master

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

setup: ## Sync deps + install pre-commit hooks + install Playwright chromium
	@echo "📦 Installing dependencies..."
	uv sync --group dev --group e2e
	@echo "🌐 Installing Playwright chromium..."
	PLAYWRIGHT_BROWSERS_PATH=$${PLAYWRIGHT_BROWSERS_PATH:-/cache/shared-ai/ms-playwright} uv run --group e2e playwright install chromium || true
	@echo "🪝 Setting up pre-commit hooks..."
	@[ -n "$$(git config --get core.hooksPath 2>/dev/null)" ] || [ -f .git ] || uv run pre-commit install
	@echo "✅ Setup complete!"

install: setup ## Alias for setup

uninstall: ## Remove the installed pdomain-ocr-simple-gui uv tool
	@uv tool uninstall pdomain-ocr-simple-gui || true
	@echo "✅ pdomain-ocr-simple-gui uninstalled."

remove-venv: ## Remove the virtual environment
	rm -rf .venv

reset: clean remove-venv setup ## Rebuild the virtual environment
	@echo "✅ Environment Reset!"

upgrade-deps: ## Upgrade dependencies and sync local environment
	@echo "⬆️ Upgrading dependency lockfile..."
	uv lock --upgrade
	@echo "📦 Syncing upgraded dependencies..."
	uv sync --group dev
	@echo "✅ Dependencies upgraded and environment synced!"

dev-local: ## [DEPRECATED] Use 'make local-dev' instead
	@echo "⚠️  dev-local is deprecated. Use 'make local-dev' for the standard local-dev workflow."
	@$(MAKE) --no-print-directory local-dev

# ---------------------------------------------------------------------------
# Lint / format / typecheck / test
# ---------------------------------------------------------------------------

lint: ## Run ruff checks
	uv run ruff check --select I --fix
	uv run ruff check --fix

format: ## Format code with ruff
	uv run ruff format
	@$(MAKE) --no-print-directory lint

format-check: ## Check Python formatting with ruff (no writes)
	uv run ruff format --check
	uv run ruff check --select I

typecheck: ## Run basedpyright at warnings level (failOnWarnings=true in pyproject.toml)
	uv run basedpyright src/pdomain_ocr_simple_gui installer/

pre-commit-check: ## Run pre-commit on all files
	uv run pre-commit run --all-files

test: ## Run pytest (excludes slow/e2e tests)
	uv run pytest tests/ -v -n auto

behavior-coverage: ## Regenerate behavior coverage.md + gate (declared vs cited IDs)
	uv run python -m scripts.behavior_coverage

smoke: ## Run slow/e2e smoke tests (requires real OCR; use make ci AI=1 to include)
	uv run pytest tests/smoke/ -v -m "slow or e2e"

packaging-test: frontend-build ## Build-path regression tests (slow; verifies wheel+sdist ship the frontend SPA)
	uv run pytest tests/test_packaging.py -m slow -v

e2e-fast: frontend-build ## Run full behavior e2e suite (fake dispatcher, no model weights; part of make ci)
	@echo "🌐 Running full behavior e2e suite (fake dispatcher)..."
	PLAYWRIGHT_BROWSERS_PATH=$${PLAYWRIGHT_BROWSERS_PATH:-/cache/shared-ai/ms-playwright} \
	PDOMAIN_OCR_FAKE_DISPATCHER=1 \
	uv run --group e2e pytest tests/e2e/ -v -m "(slow or e2e) and not real_ocr" --no-cov -n auto

e2e-browser: frontend-build ## Run all Playwright browser e2e tests (requires chromium; includes e2e-fast tests)
	@echo "🌐 Running Playwright e2e tests..."
	PLAYWRIGHT_BROWSERS_PATH=$${PLAYWRIGHT_BROWSERS_PATH:-/cache/shared-ai/ms-playwright} \
	uv run --group e2e pytest tests/e2e/ -v -m "slow or e2e" --no-cov

e2e-real-ocr: frontend-build ## Run Tier-B real-OCR e2e on the GPU (opt-in; NOT in make ci; requires model weights + chromium)
	@echo "🧠 Running Tier-B real-OCR e2e (real engine, GPU)..."
	PLAYWRIGHT_BROWSERS_PATH=$${PLAYWRIGHT_BROWSERS_PATH:-/cache/shared-ai/ms-playwright} \
	uv run --group e2e pytest tests/e2e/test_real_ocr_*.py -v -m "real_ocr" --no-cov

frontend-install: ## Install frontend dependencies
	@# pnpm >=11 rewrites pnpm-workspace.yaml (appends an unfilled `allowBuilds:`
	@# placeholder) when it meets an un-approved build script. The committed file
	@# already lists `allowBuilds: { esbuild: true }`, so a clean install must be
	@# idempotent. Snapshot it, install, and — whether install succeeds or fails —
	@# detect any mutation, restore the committed file, and fail loudly. A mutation
	@# means a new dependency ships an un-approved build script and needs an entry
	@# in the `allowBuilds:` map of frontend/pnpm-workspace.yaml.
	@cp frontend/pnpm-workspace.yaml frontend/pnpm-workspace.yaml.preinstall
	@( cd frontend && $(call _pnpm,install) ); rc=$$?; \
	if ! diff -q frontend/pnpm-workspace.yaml.preinstall frontend/pnpm-workspace.yaml >/dev/null 2>&1; then \
		echo "❌ pnpm install mutated frontend/pnpm-workspace.yaml:"; \
		diff frontend/pnpm-workspace.yaml.preinstall frontend/pnpm-workspace.yaml || true; \
		echo "   A dependency ships an un-approved build script. Add it to the"; \
		echo "   'allowBuilds:' map in frontend/pnpm-workspace.yaml (set true/false)."; \
		mv frontend/pnpm-workspace.yaml.preinstall frontend/pnpm-workspace.yaml; \
		exit 1; \
	fi; \
	rm -f frontend/pnpm-workspace.yaml.preinstall; \
	exit $$rc

frontend-test: frontend-install ## Run frontend vitest suite
	cd frontend && $(call _pnpm,run test)

frontend-build: frontend-install ## Build the React/Vite SPA to src/pdomain_ocr_simple_gui/frontend/
	cd frontend && $(call _pnpm,run build)

frontend-dev: frontend-install ## Run Vite dev server (frontend only, hot-reload)
	cd frontend && $(call _pnpm,run dev)

frontend-lint: frontend-install ## Run ESLint on the SPA
	@echo "🧹 Running frontend ESLint..."
	cd frontend && $(call _pnpm,run lint)

frontend-format: frontend-install ## Apply Prettier formatting to the SPA
	@echo "🎨 Applying Prettier to the frontend..."
	cd frontend && $(call _pnpm,run format)

frontend-format-check: frontend-install ## Check SPA formatting with Prettier
	@echo "🎨 Checking frontend formatting (Prettier)..."
	cd frontend && $(call _pnpm,run format:check)

frontend-knip: frontend-install ## Run knip dead-export detector (blocking)
	@echo "🔍 Running knip dead-export scan..."
	cd frontend && $(call _pnpm,run knip)

openapi-export: ## Regenerate openapi.json + frontend/src/api/types.gen.ts
	@echo "📤 Exporting OpenAPI schema and regenerating TS types..."
	uv run python scripts/export_openapi.py openapi.json
	@if $(HAVE_MISE); then \
		cd frontend && $(MISE) exec -- npx --yes openapi-typescript ../openapi.json -o src/api/types.gen.ts; \
	else \
		cd frontend && npx --yes openapi-typescript ../openapi.json -o src/api/types.gen.ts; \
	fi
	@echo "✅ frontend/src/api/types.gen.ts regenerated."

clean: ## Clean cache + build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true

build: frontend-build ## Build release artifacts (sdist + wheel, both from source)
	# Build sdist and wheel as SEPARATE explicit commands (NOT bare `uv build`).
	# Bare `uv build` builds the wheel from the sdist in a non-git temp dir;
	# if artifacts config is incomplete, the gitignored frontend/ is silently
	# dropped from the wheel. Building both from source eliminates this risk.
	uv build --sdist
	uv build --wheel

ci: setup frontend-install pre-commit-check lint typecheck frontend-build test behavior-coverage smoke packaging-test frontend-format-check frontend-lint frontend-test frontend-knip e2e-fast ## Full CI pipeline (includes fast browser click-path tier)

ci-slow: ci ## Full pre-flight for releases (alias of ci today; reserved for slower checks if added later)

ci-full: ci e2e-browser smoke ## Full CI including all Playwright browser tests + real-OCR smoke (requires --group e2e + chromium + model weights)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

# SPA_BUNDLE is the built index.html; SPA_SRCS lists the frontend source
# inputs whose mtime, if newer than the bundle, means a rebuild is needed.
# Only paths that actually exist in frontend/ are listed (a stray path would
# make `find` print a warning and the guard could misfire).
SPA_BUNDLE := src/pdomain_ocr_simple_gui/frontend/index.html
SPA_SRCS := frontend/src frontend/index.html frontend/package.json \
        frontend/vite.config.ts frontend/tailwind.config.js \
        frontend/postcss.config.js frontend/tsconfig.json \
        frontend/tsconfig.node.json

# `make run` rebuilds the SPA only when the bundle is missing or stale
# (any frontend source newer than the built index.html). Fast restarts when
# nothing changed; automatic rebuild when sources change.
# Caveat: `git checkout` does not preserve file mtimes, so the very first
# `make run` after a fresh clone may rebuild once even if the bundle was
# committed. Use `make frontend-build` as the explicit force-rebuild path.
# NOTE: local-run / local-frontend-build are the local-dev-link flow and
# keep their own behaviour — this guard applies only to the `run` target.
run: ## Build SPA if missing or stale, then launch pdomain-ocr-simple-gui
	@if [ ! -f $(SPA_BUNDLE) ] || [ -n "$$(find $(SPA_SRCS) -newer $(SPA_BUNDLE) 2>/dev/null)" ]; then \
		echo "SPA bundle stale or missing; running frontend-build first..."; \
		$(MAKE) --no-print-directory frontend-build; \
	else \
		echo "SPA bundle up to date."; \
	fi
	uv run pdomain-ocr-simple-gui $(ARGS)

# ---------------------------------------------------------------------------
# Local dev (editable sibling deps)
# ---------------------------------------------------------------------------

local-setup: ## Clone any missing sibling pd-* repos
	@./scripts/local-setup.sh

local-dev: ## Switch to local-dev mode (siblings editable + marker)
	@./scripts/local-dev.sh

local-check: ## Print local-dev mode status
	@./scripts/local-check.sh

local-upgrade-deps: ## Upgrade deps then restore editable siblings
	@./scripts/local-upgrade-deps.sh

local-run: ## Run the SPA against local-dev workspace
	@./scripts/local-run.sh

# Parallel local-* family — like the frontend-* / setup targets, but
# preserve `pnpm link` and `uv pip install -e` overlays after a fresh
# `pnpm install` / `uv sync`. Normal frontend-*/setup targets remain
# registry-resolved; only the local-* family is local-link-sticky.
# Spec: workspace decision noted in docs/process/local-dev.md.

local-setup-py: ## Re-apply editable Python siblings (idempotent)
	@./scripts/local-setup-py.sh

local-frontend-install: ## frontend-install + restore pnpm link overlays for npm siblings
	@./scripts/local-frontend-install.sh

local-frontend-build: local-frontend-install ## Vite build using local-linked siblings
	cd frontend && $(call _pnpm,run build)

local-frontend-test: local-frontend-install ## vitest using local-linked siblings
	cd frontend && $(call _pnpm,run test)

local-frontend-dev: local-frontend-install ## Vite dev server using local-linked siblings
	cd frontend && $(call _pnpm,run dev)

ci-against-master: ## Validate against pd-* siblings' latest master, then revert (transient)
	@./scripts/ci-against-master.sh

# ---------------------------------------------------------------------------
# Sibling-dep refresh (spec #363)
# ---------------------------------------------------------------------------

update-pdomain-deps: ## Bump pd-* sibling deps to registry latest; leaves diff for review
	@./scripts/update-pdomain-deps.sh

upgrade-pdomain-book-tools: ## [DEPRECATED] Use 'make update-pdomain-deps' instead
	@echo "⚠️  upgrade-pdomain-book-tools is deprecated. Use 'make update-pdomain-deps' for all sibling deps."
	@$(MAKE) --no-print-directory update-pdomain-deps

# ---------------------------------------------------------------------------
# Releases
# ---------------------------------------------------------------------------

release-patch: ## Release: bump patch, run ci-slow, tag, push (e.g. v0.4.2 → v0.4.3)
	@$(MAKE) --no-print-directory _do-release BUMP=patch

release-minor: ## Release: bump minor, run ci-slow, tag, push (e.g. v0.4.2 → v0.5.0)
	@$(MAKE) --no-print-directory _do-release BUMP=minor

release-major: ## Release: bump major, run ci-slow, tag, push (e.g. v0.4.2 → v1.0.0)
	@$(MAKE) --no-print-directory _do-release BUMP=major

# scripts/do-release.sh handles repo-state guards, runs the ci-slow pre-flight,
# creates a three-component tag, and pushes main + tag.
# Pass FORCE=1 to skip the repo-state guards (pre-flight still runs).
# Pass SKIP_PUSH=1 to create the tag locally without pushing.
_do-release:
	@BUMP=$(or $(BUMP),minor) ./scripts/do-release.sh

endif

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

PEER_BOOK_TOOLS_PATH ?= ../pd-book-tools

.PHONY: help setup install uninstall remove-venv reset lint format typecheck \
        pre-commit-check test e2e-browser frontend-build frontend-test clean ci ci-full \
        upgrade-deps dev-local

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

setup: ## Sync deps + install pre-commit hooks
	@echo "📦 Installing dependencies..."
	uv sync --group dev
	@echo "🪝 Setting up pre-commit hooks..."
	uv run pre-commit install || true
	@echo "✅ Setup complete!"

install: setup ## Alias for setup

uninstall: ## Remove the installed pd-ocr-simple-gui uv tool
	@uv tool uninstall pd-ocr-simple-gui || true
	@echo "✅ pd-ocr-simple-gui uninstalled."

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

dev-local: ## [local-dev] Install pd-book-tools from ../pd-book-tools as editable (overlays the wheel)
	@if [ ! -d "$(PEER_BOOK_TOOLS_PATH)" ]; then \
		echo "❌ $(PEER_BOOK_TOOLS_PATH) not found. Clone pd-book-tools as a sibling directory."; \
		exit 1; \
	fi
	@echo "🔧 Installing local editable pd-book-tools from $(PEER_BOOK_TOOLS_PATH)..."
	uv sync --group dev
	uv pip install --editable "$(PEER_BOOK_TOOLS_PATH)"
	@echo "✅ Local editable pd-book-tools active. Canonical baseline: make setup"

# ---------------------------------------------------------------------------
# Lint / format / typecheck / test
# ---------------------------------------------------------------------------

lint: ## Run ruff checks
	uv run ruff check --select I --fix
	uv run ruff check --fix

format: ## Format code with ruff
	uv run ruff format
	@$(MAKE) --no-print-directory lint

typecheck: ## Run basedpyright at recommended mode
	uv run basedpyright src/pd_ocr_simple_gui --level error

pre-commit-check: ## Run pre-commit on all files
	uv run pre-commit run --all-files

test: ## Run pytest (excludes slow/e2e tests)
	uv run pytest tests/ -v -n auto

smoke: ## Run slow/e2e smoke tests (requires real OCR; use make ci AI=1 to include)
	uv run pytest tests/smoke/ -v -m "slow or e2e"

e2e-browser: frontend-build ## Run Playwright browser e2e tests (requires chromium)
	@echo "🌐 Running Playwright e2e tests..."
	PLAYWRIGHT_BROWSERS_PATH=/cache/shared-ai/ms-playwright \
	uv run --group e2e pytest tests/e2e/ -v -m "slow or e2e" --no-cov

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

frontend-build: frontend-install ## Build the React/Vite SPA to src/pd_ocr_simple_gui/frontend/
	cd frontend && $(call _pnpm,run build)

clean: ## Clean cache + build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true

ci: setup frontend-install pre-commit-check lint typecheck frontend-build test smoke frontend-test ## Full CI pipeline (smoke tests run via make smoke)

ci-full: ci e2e-browser ## Full CI including Playwright browser tests (requires --group e2e + chromium)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

run: ## Launch pd-ocr-simple-gui on :8004
	@echo "🚀 Launching pd-ocr-simple-gui at http://127.0.0.1:8004 ..."
	uv run pd-ocr-simple-gui $(ARGS)

endif

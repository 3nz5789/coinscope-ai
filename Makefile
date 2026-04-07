# ─────────────────────────────────────────────────────────────
#  CoinScopeAI — Makefile
#  Common development commands for the monorepo
# ─────────────────────────────────────────────────────────────

.PHONY: help dev-infra dev-engine dev-dashboard test lint clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ────────────────────────────────────────────

dev-infra: ## Start dev infrastructure (PostgreSQL, Redis)
	docker-compose -f infra/docker/docker-compose.dev.yml up -d

dev-infra-down: ## Stop dev infrastructure
	docker-compose -f infra/docker/docker-compose.dev.yml down

# ── Trading Engine ────────────────────────────────────────────

dev-engine: ## Run the trading engine in development mode
	cd services/trading-engine && uvicorn app.main:app --reload --port 8001

# ── Dashboard ─────────────────────────────────────────────────

dev-dashboard: ## Run the dashboard in development mode
	cd apps/dashboard && npm run dev

# ── Testing ───────────────────────────────────────────────────

test: ## Run all tests
	pytest tests/ -v --tb=short

test-engine: ## Run trading engine tests
	cd services/trading-engine && pytest tests/ -v --tb=short

test-dashboard: ## Run dashboard tests
	cd apps/dashboard && npm test

# ── Linting ───────────────────────────────────────────────────

lint: ## Run linters on all Python code
	flake8 coinscope_trading_engine/ services/ ai/ --max-line-length=120

lint-fix: ## Auto-format Python code with black
	black coinscope_trading_engine/ services/ ai/

# ── Cleanup ───────────────────────────────────────────────────

clean: ## Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

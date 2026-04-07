# ─────────────────────────────────────────────────────────────
#  CoinScopeAI — Makefile
#  Single-command operations for the full dev stack.
#
#  Quick start:
#    make setup    # first-time setup
#    make up       # start core services (db, redis, engine)
#    make status   # check what's running
#    make down     # stop everything
# ─────────────────────────────────────────────────────────────

COMPOSE := docker compose -f infra/docker/docker-compose.dev.yml

.PHONY: help setup up up-full down restart status logs \
        db-shell db-reset db-dump db-tables \
        engine-logs engine-shell engine-health \
        ingest ingest-full ingest-symbol \
        backtest backtest-wf backtest-custom \
        recorder recorder-logs recorder-stats \
        paper-trade paper-trade-v2 paper-trade-status paper-trade-kill \
        dev-engine dev-dashboard \
        test test-unit test-ingestion test-backtesting test-paper-trading test-docker \
        lint lint-fix build build-engine build-no-cache \
        clean nuke

# ── Default ──────────────────────────────────────────────────
help: ## Show this help
	@echo ""
	@echo "  CoinScopeAI — Development Commands"
	@echo "  ─────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ────────────────────────────────────────────────────
setup: ## First-time setup: create .env, build images
	@echo "▸ Creating .env from template..."
	@cp -n .env.example .env 2>/dev/null || true
	@echo "▸ Building Docker images..."
	$(COMPOSE) build
	@echo "▸ Setup complete. Run 'make up' to start."

# ── Core Stack ───────────────────────────────────────────────
up: ## Start core services (db, redis, engine)
	$(COMPOSE) up -d db redis engine
	@echo "▸ Waiting for services to be healthy..."
	@sleep 3
	@$(MAKE) status

up-full: ## Start ALL services including tools
	$(COMPOSE) --profile full --profile tools up -d
	@sleep 3
	@$(MAKE) status

down: ## Stop all services
	$(COMPOSE) --profile full --profile tools --profile ingestion --profile backtesting --profile paper-trading --profile paper-trading-v2 down
	@echo "▸ All services stopped."

restart: ## Restart all running services
	$(COMPOSE) restart
	@$(MAKE) status

status: ## Show status of all services
	@echo ""
	@echo "  CoinScopeAI Service Status"
	@echo "  ─────────────────────────────────────────"
	@$(COMPOSE) --profile full --profile tools ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
		$(COMPOSE) --profile full --profile tools ps
	@echo ""
	@echo "  Endpoints:"
	@echo "    Engine API:  http://localhost:$${ENGINE_PORT:-8001}/health"
	@echo "    Adminer:     http://localhost:$${ADMINER_PORT:-8080}"
	@echo "    PostgreSQL:  localhost:$${DB_PORT:-5432}"
	@echo "    Redis:       localhost:$${REDIS_PORT:-6379}"
	@echo ""

# ── Logs ─────────────────────────────────────────────────────
logs: ## Tail logs for all services
	$(COMPOSE) --profile full logs -f --tail=50

engine-logs: ## Tail engine logs
	$(COMPOSE) logs -f --tail=100 engine

# ── Database ─────────────────────────────────────────────────
db-shell: ## Open psql shell in the database
	$(COMPOSE) exec db psql -U coinscopeai -d coinscopeai_dev

db-reset: ## Drop and recreate the database (DESTRUCTIVE)
	@echo "▸ WARNING: This will destroy all data. Press Ctrl+C to cancel."
	@sleep 3
	$(COMPOSE) down -v
	$(COMPOSE) up -d db
	@echo "▸ Database reset. Schema will be re-initialized on start."

db-dump: ## Dump database to file
	@mkdir -p backups
	$(COMPOSE) exec db pg_dump -U coinscopeai coinscopeai_dev > backups/dump_$$(date +%Y%m%d_%H%M%S).sql
	@echo "▸ Database dumped to backups/"

db-tables: ## List all tables and row counts
	$(COMPOSE) exec db psql -U coinscopeai -d coinscopeai_dev -c \
		"SELECT schemaname, tablename, n_live_tup as row_count \
		 FROM pg_stat_user_tables ORDER BY tablename;"

# ── Data Ingestion ───────────────────────────────────────────
ingest: ## Run incremental data ingestion
	$(COMPOSE) --profile ingestion run --rm ingestion \
		python -m data.ingestion.cli --incremental

ingest-full: ## Run full 24-month data ingestion (slow)
	$(COMPOSE) --profile ingestion run --rm ingestion \
		python -m data.ingestion.cli

ingest-symbol: ## Ingest a single symbol (usage: make ingest-symbol SYMBOL=ETHUSDT)
	$(COMPOSE) --profile ingestion run --rm ingestion \
		python -m data.ingestion.cli --symbols $(SYMBOL) --incremental

# ── Backtesting ──────────────────────────────────────────────
backtest: ## Run default backtest (SMA crossover on BTCUSDT 1h)
	$(COMPOSE) --profile backtesting run --rm backtesting

backtest-wf: ## Run walk-forward analysis
	$(COMPOSE) --profile backtesting run --rm backtesting \
		python -m services.backtesting.cli --walk-forward --wf-splits 5

backtest-custom: ## Custom backtest (usage: make backtest-custom ARGS="--symbol ETHUSDT --timeframe 4h")
	$(COMPOSE) --profile backtesting run --rm backtesting \
		python -m services.backtesting.cli $(ARGS)

# ── Market Data Recorder ────────────────────────────────────
recorder: ## Start the 24/7 market data recorder
	$(COMPOSE) up -d recorder
	@echo "▸ Recorder started. Recording trades, orderbook, funding, liquidations."

recorder-logs: ## Tail recorder logs
	$(COMPOSE) logs -f --tail=100 recorder

recorder-stats: ## Check recorder statistics
	$(COMPOSE) exec recorder python3 -c "from services.market_data.streams.recorder import *; print('Running')"

# ── Paper Trading ───────────────────────────────────────────
paper-trade: ## Start paper trading engine v1 (testnet only)
	$(COMPOSE) --profile paper-trading up -d paper-trading
	@echo "▸ Paper trading v1 started (TESTNET ONLY)."

paper-trade-v2: ## Start paper trading engine v2 with EventBus (testnet only)
	$(COMPOSE) --profile paper-trading-v2 up -d paper-trading-v2
	@echo "▸ Paper trading v2 started with EventBus integration (TESTNET ONLY)."

paper-trade-status: ## Check paper trading status
	@python3 -m services.paper_trading.status 2>/dev/null || echo "Paper trading not running locally"

paper-trade-kill: ## Emergency kill switch — flatten all positions
	@python3 -m services.paper_trading.kill
	@echo "▸ KILL SWITCH ACTIVATED. All positions closed."

# ── Local Dev (without Docker) ───────────────────────────────
dev-engine: ## Run the trading engine locally (no Docker)
	cd coinscope_trading_engine && uvicorn api:app --reload --port 8001

dev-dashboard: ## Run the dashboard locally (no Docker)
	cd apps/dashboard && npm run dev

# ── Engine ───────────────────────────────────────────────────
engine-shell: ## Open a shell in the engine container
	$(COMPOSE) exec engine /bin/bash

engine-health: ## Check engine health endpoint
	@curl -sf http://localhost:$${ENGINE_PORT:-8001}/health | python3 -m json.tool 2>/dev/null || \
		echo "Engine not reachable at port $${ENGINE_PORT:-8001}"

# ── Testing ──────────────────────────────────────────────────
test: ## Run all unit tests (local, not in Docker)
	python3 -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	python3 -m pytest tests/unit/ -v --tb=short

test-ingestion: ## Run ingestion tests
	python3 -m pytest tests/unit/data_ingestion/ -v --tb=short

test-backtesting: ## Run backtesting tests
	python3 -m pytest tests/unit/backtesting/ -v --tb=short

test-paper-trading: ## Run paper trading tests
	python3 -m pytest tests/unit/paper_trading/ -v --tb=short

test-docker: ## Run tests inside Docker
	$(COMPOSE) --profile backtesting run --rm backtesting \
		python -m pytest tests/unit/ -v --tb=short

# ── Linting ──────────────────────────────────────────────────
lint: ## Run linters on all Python code
	flake8 coinscope_trading_engine/ services/ data/ --max-line-length=120

lint-fix: ## Auto-format Python code with black
	black coinscope_trading_engine/ services/ data/

# ── Build ────────────────────────────────────────────────────
build: ## Build all Docker images
	$(COMPOSE) --profile full build

build-engine: ## Build engine image only
	$(COMPOSE) build engine

build-no-cache: ## Build all images without cache
	$(COMPOSE) --profile full build --no-cache

# ── Cleanup ──────────────────────────────────────────────────
clean: ## Stop services and remove containers + caches
	$(COMPOSE) --profile full --profile tools --profile ingestion --profile backtesting down --remove-orphans 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "▸ Cleaned up."

nuke: ## NUCLEAR: remove everything including volumes and images
	@echo "▸ WARNING: This removes ALL data, volumes, and images."
	@echo "▸ Press Ctrl+C within 5 seconds to cancel."
	@sleep 5
	$(COMPOSE) --profile full --profile tools --profile ingestion --profile backtesting down -v --rmi local --remove-orphans
	docker volume rm coinscopeai-pgdata coinscopeai-redisdata coinscopeai-backtest-reports coinscopeai-recorded-data coinscopeai-paper-trading-state 2>/dev/null || true
	@echo "▸ Everything removed."

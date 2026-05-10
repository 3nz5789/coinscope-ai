# CoinScopeAI — Makefile
# Common operator commands. Run from the repo root.
# Requires: Python 3.11+, Docker, pip

.PHONY: help dev test lint typecheck guardrail sync clean install docs

# Default target
help:
	@echo ""
	@echo "CoinScopeAI — available targets"
	@echo "────────────────────────────────────────────────────────"
	@echo "  make install     Install Python dependencies"
	@echo "  make dev         Start engine + Redis locally"
	@echo "  make test        Run full test suite with coverage"
	@echo "  make lint        Run ruff + black checks (no auto-fix)"
	@echo "  make format      Auto-fix with ruff + black"
	@echo "  make typecheck   Run mypy type checks"
	@echo "  make guardrail   Run drift detector + threshold guardrail"
	@echo "  make sync        Run session-end sync verifier"
	@echo "  make status      Morning engine status brief (all 6 endpoints)"
	@echo "  make clean       Remove build/cache artefacts"
	@echo "────────────────────────────────────────────────────────"
	@echo ""

# ── Install ───────────────────────────────────────────────────────────────────
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install ruff black mypy pytest pytest-asyncio pytest-cov

# ── Dev server ────────────────────────────────────────────────────────────────
dev:
	@echo "Starting Redis + engine..."
	docker compose up -d redis
	@sleep 1
	cd coinscope_trading_engine && uvicorn api:app --reload --port 8001

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest -x -q tests/ coinscope_trading_engine/tests/ \
		--cov=coinscope_trading_engine \
		--cov-report=term-missing \
		--cov-fail-under=60

smoke:
	pytest -x -q tests/test_ci_smoke.py -W ignore::pytest.PytestConfigWarning

# ── Lint (no auto-fix) ────────────────────────────────────────────────────────
lint:
	@echo "Running ruff..."
	ruff check .
	@echo "Running black --check..."
	black --check .
	@echo "Lint clean ✓"

# ── Format (auto-fix) ─────────────────────────────────────────────────────────
format:
	ruff check --fix .
	black .
	@echo "Format applied ✓"

# ── Type checking ─────────────────────────────────────────────────────────────
typecheck:
	mypy coinscope_trading_engine --ignore-missing-imports --no-error-summary

# ── Protective scripts ────────────────────────────────────────────────────────
guardrail:
	@echo "Running drift detector..."
	python3 scripts/drift_detector.py
	@echo "Running risk threshold guardrail..."
	python3 scripts/risk_threshold_guardrail.py
	@echo "Guardrail clean ✓"

sync:
	python3 scripts/sync_verify.py

status:
	./scripts/daily_status.sh

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	find . -name "coverage.xml" -delete 2>/dev/null || true
	@echo "Clean ✓"

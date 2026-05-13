# Changelog

All notable changes to CoinScopeAI are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Validation phase note:** The engine is in P0 testnet validation through ~May 31, 2026.
> No version is tagged as stable until PCC v2 §8 readiness criteria are met.

---

## [Unreleased]

### Added
- `docs/validation/p0-public-summary.md` — one-page outsider-facing P0
  validation summary covering what is live, what is testnet only, what
  is blocked, what has passed, and what has not. Linked from the README
  header alongside Dashboard / API Docs / Disclosures. Hand-curated;
  refreshed at each tagged release. The internal evidence pack and
  invariant matrix remain the source of truth.
- `apps/dashboard/src/components/SignalConsoleCard.tsx` — one-panel operator
  console view for the primary signal. Surfaces confluence, regime, Kelly
  size, gate pass/fail, breaker state, and a deterministic action-guidance
  row (HALT / SKIP / WATCH / CONSIDER / EXECUTE) derived from those five
  inputs. Collapses a workflow that previously required jumping between
  Live Scanner, Risk Gate, Position Sizer, and Regime State views.
- `LiveScanner` now renders the highest-confluence active signal through
  `SignalConsoleCard` above the existing signal table, with a best-effort
  gate/breaker join from the risk-gate snapshot until per-signal joins
  to `/position-size` and `/risk-gate` are wired.
- Full GitHub repository setup: branch protection on `main`, squash-only merge,
  auto-delete head branches, required CI status checks (`Tests` + `Security Scan`)
- PR template with validation-phase gate checklist
- Issue templates: bug report, feature request, strategy/risk change, config.yml chooser
- CODEOWNERS covering `risk_management/`, `engine/exchange/`, `engine/integrations/`,
  `coinscope.env.example`, `configs/environments/`, `CLAUDE.md`
- `Makefile` with `dev`, `test`, `lint`, `guardrail`, `sync`, `typecheck`, `clean` targets
- `pyproject.toml` with ruff, black, and pytest configuration
- Lint job added to CI (`ruff check` + `black --check`)
- `CHANGELOG.md` (this file)

### Changed
- `configs/environments/*.yaml`: `max_daily_loss_pct` corrected from `0.03` to `0.05`,
  `max_open_positions` corrected from `3` to `5`
- `risk_management/risk_gate.py`: constructor defaults corrected (`daily_loss 0.10→0.05`,
  `drawdown 0.20→0.10`)
- `coinscope_trading_engine/config.py`: `max_daily_loss_pct` default corrected `2.0→5.0`
- `coinscope_trading_engine/.env.example` / `.env.template`: `MAX_DAILY_LOSS_PCT` corrected
- README: correct repo structure, env filename, regime table, full endpoint list,
  circuit-breaker/reset endpoint, ADR table, validation freeze table
- CONTRIBUTING: two-reviewer paths corrected to v1 structure, protective scripts section added
- SECURITY: Sev-1/2/3 severity tiers added, coordinated disclosure policy
- Repo description updated to new tagline

### Fixed
- Stale `MAX_LEVERAGE=20x` references replaced with canonical `10x` across all docs
- Stale `MAX_OPEN_POSITIONS=3` references replaced with canonical `5` across all docs

---

## [0.1.0-testnet] — 2026-05-01

### Added
- Engine core: FastAPI HTTP layer, asyncio orchestrator, 5-scanner pipeline
- Risk gate: circuit breakers, exposure tracker, correlation analyzer, position sizer
- HMM regime detector (v3) — Trending / Mean-Reverting / Volatile / Quiet
- Telegram alert system (`@ScoopyAI_bot`) with rate limiting and priority queuing
- Binance USDT-M Testnet integration (REST + WebSocket)
- Redis cache layer with TTL management
- Prometheus metrics exporter on `:9090`
- Structured JSON logging with rotating file handler
- GitHub Actions CI: 15 smoke tests + security scan
- Business plan v1 locked across 16 sections (§1–§16)
- Canonical risk thresholds locked via PCC v2 §8 (2026-05-01):
  - `MAX_LEVERAGE=10x`, `MAX_OPEN_POSITIONS=5`, `MAX_DRAWDOWN_PCT=10%`,
    `MAX_DAILY_LOSS_PCT=5%`, `POSITION_HEAT_CAP_PCT=80%`, `KELLY_HARD_CAP_PCT=2%`
- DigitalOcean SGP1 deployment (Docker Compose + systemd)
- Stripe billing integration (test mode)
- Protective scripts: `drift_detector.py`, `risk_threshold_guardrail.py`,
  `sync_verify.py`, `daily_status.sh`

### Architecture decisions
- ADR-0001: FastAPI + Uvicorn as engine framework
- ADR-0002: Redis + Celery for async task queue
- ADR-0003: LLM calls prohibited on the hot path

---

[Unreleased]: https://github.com/3nz5789/CoinScopeAI/compare/v0.1.0-testnet...HEAD
[0.1.0-testnet]: https://github.com/3nz5789/CoinScopeAI/releases/tag/v0.1.0-testnet

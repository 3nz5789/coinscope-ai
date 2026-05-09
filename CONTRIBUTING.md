# Contributing to CoinScopeAI

Thank you for contributing. This document explains how to work with the codebase safely, especially during the active testnet validation phase.

---

## Validation Phase Rules (Active)

The engine is in a **testnet validation freeze**. The following changes are blocked regardless of how reasonable they seem:

| Blocked change | Reason |
|---|---|
| Any canonical risk threshold | Would invalidate the validation cohort |
| `BINANCE_TESTNET=false` | Real-capital gate is locked |
| Removing or bypassing a circuit breaker | Safety regression |
| Retraining or replacing ML artifacts | Changes signal distribution |
| Order submission semantic changes | Execution integrity |

If your PR touches any of the above, close it and wait until validation ends.

---

## Branch Strategy

```
main          production-ready, protected
feature/*     new capabilities
fix/*         bug fixes
docs/*        documentation only
hotfix/*      emergency production fixes
```

Never push directly to `main`. All changes go through PRs.

---

## Commit Messages

Follow `<scope>: <summary>` format:

```
fix(risk-gate): guard against zero account balance in Kelly sizer
feat(scanner): add CVD divergence signal to confluence score
docs(runbooks): update daily-ops with new health check endpoint
config: align .env.example thresholds with canonical values
```

Scopes: `engine`, `scanner`, `risk-gate`, `regime`, `alerts`, `journal`, `api`, `config`, `docs`, `ci`, `infra`

---

## PR Process

1. Branch from `main`
2. Make changes with tests
3. Run checks locally:
   ```bash
   ruff check .
   pytest -x -q
   ```
4. Open PR using the template
5. Request review — **2 reviewers required** for risk logic, exchange adapters, or position sizing
6. Squash merge after approval

---

## Code Standards

- Linter: `ruff` (configured in `pyproject.toml`)
- Formatter: `black`
- Type hints: required on all new public functions
- Test coverage: aim for 80%+ on new modules
- Never commit `.env` — pre-commit hook enforces this

---

## Two-Reviewer Rule

Changes to the following require two approvals before merge:

- `coinscope_trading_engine/risk/`
- `coinscope_trading_engine/scanner/`
- `app/engine/`
- `app/integrations/` (any exchange adapter)
- Any file containing `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `MAX_DRAWDOWN`, `KELLY_`
- `.env.example`
- `CLAUDE.md`

---

## Testing Against Testnet

```bash
# Set in .env
BINANCE_TESTNET=true
BINANCE_TESTNET_API_KEY=<your testnet key>
BINANCE_TESTNET_API_SECRET=<your testnet secret>

# Smoke test
python -m scripts.binance_adapter_smoke --symbols BTCUSDT --duration 30
```

Get testnet keys from testnet.binancefuture.com. Never use mainnet keys locally.

---

## Issue Labels

Labels match the Linear taxonomy. Use them on all issues and PRs.

| Label | Meaning |
|---|---|
| `type: bug` | Something broken |
| `type: feature` | New capability |
| `type: infra` | Infra / DevOps |
| `type: docs` | Documentation |
| `type: research` | Investigation / spike |
| `dom: scanner` | Signal scoring |
| `dom: risk` | Risk gate / sizing |
| `dom: exchange-api` | Exchange integration |
| `dom: monitoring` | Observability |
| `SLO: No Data Loss` | Data integrity SLO |
| `SLO: Code Quality` | Code quality SLO |
| `P1 - high` | High priority |
| `P2 - medium` | Medium priority |
| `P3 - low` | Low priority |

---

## Questions

- Linear: [linear.app/coinscopeai](https://linear.app/coinscopeai)
- Notion: [CoinScopeAI OS](https://www.notion.so/33a29aaf938e81efa983e47b83e15775)
- Telegram: `@ScoopyAI_bot`

# Contributing to CoinScopeAI

This document explains how to work with the codebase safely, especially during the active P0 testnet validation phase.

---

## Validation Phase Freeze (Active through ~May 31, 2026)

The engine is in a **testnet validation freeze**. The following changes are **blocked** regardless of how reasonable they seem:

| Blocked change | Why |
|---|---|
| Any canonical risk threshold (`MAX_DAILY_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `POSITION_HEAT_CAP_PCT`, `KELLY_FRACTION`) | Would invalidate the validation cohort |
| Setting `BINANCE_TESTNET=false` | Real-capital gate is locked |
| Removing or bypassing any circuit breaker or kill switch | Safety regression |
| Retraining or replacing ML artifacts | Changes signal distribution mid-run |
| Changing order submission semantics (entry/stop/TP grouping, reduce-only flags) | Execution integrity |

If your PR touches any of the above, close it and open a `strategy_change` issue instead.

---

## Branch Strategy

```
main          production-ready, protected — never push directly
feature/*     new capabilities
fix/*         bug fixes
docs/*        documentation-only changes
hotfix/*      emergency fixes to main
```

---

## Commit Messages

Format: `<scope>: <imperative summary>`

```
fix(risk-gate): guard against zero account balance in Kelly sizer
feat(scanner): add CVD divergence signal to confluence score
docs(runbooks): update daily-ops with new health check endpoint
config: align coinscope.env.example thresholds with PCC v2 §8
```

**Scopes:** `engine`, `scanner`, `risk-gate`, `risk-mgmt`, `regime`, `signals`, `alerts`, `journal`, `api`, `config`, `docs`, `ci`, `infra`, `billing`, `frontend`

---

## PR Process

1. Branch from `main`
2. Make changes with tests
3. Run checks locally:
   ```bash
   ruff check .
   black --check .
   pytest -x -q tests/
   python3 scripts/drift_detector.py
   python3 scripts/risk_threshold_guardrail.py
   ```
4. Open PR using the template
5. Request review — **2 reviewers required** for risk logic, exchange adapters, or position sizing
6. Squash merge after approval

---

## Two-Reviewer Rule

Changes to any of the following require **two approvals** before merge:

| Path / file | Reason |
|---|---|
| `risk_management/` | Risk gate, circuit breakers, kill switch |
| `engine/exchange/` or `engine/integrations/` | Exchange adapter — order placement |
| `engine/signals/` | Signal scoring pipeline |
| Any file containing `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `MAX_DRAWDOWN`, `KELLY_` | Canonical threshold |
| `coinscope.env.example` | Canonical env template |
| `configs/environments/*.yaml` | Per-env risk defaults |
| `CLAUDE.md` | AI operator instructions |
| `docker-compose.yml` | Stack definition |

---

## Code Standards

- **Linter:** `ruff` (configured in `pyproject.toml`)
- **Formatter:** `black`
- **Type hints:** required on all new public functions and class methods
- **Test coverage:** aim for 80%+ on new modules; 100% on new risk logic
- **Never commit `.env`** — pre-commit hook enforces this; CI security scan also checks

---

## Protective Scripts

Run these after any canonical doc or config change:

```bash
python3 scripts/drift_detector.py
python3 scripts/risk_threshold_guardrail.py
python3 scripts/sync_verify.py
```

---

## Testing Against Testnet

```bash
BINANCE_TESTNET=true
BINANCE_FUTURES_TESTNET_API_KEY=<your testnet key>
BINANCE_FUTURES_TESTNET_API_SECRET=<your testnet secret>

pytest -x -q tests/
```

Get testnet keys from [testnet.binancefuture.com](https://testnet.binancefuture.com). Never use mainnet keys in local dev.

---

## Issue Labels

| Label | Meaning |
|---|---|
| `type: bug` | Something broken |
| `type: feature` | New capability |
| `type: infra` | Infra / DevOps |
| `type: docs` | Documentation only |
| `type: research` | Investigation / spike |
| `dom: scanner` | Signal scoring pipeline |
| `dom: risk` | Risk gate, sizing, circuit breakers |
| `dom: exchange-api` | Exchange adapter / connectivity |
| `dom: monitoring` | Observability, alerts, metrics |
| `dom: frontend` | Dashboard and UI |
| `dom: billing` | Stripe / subscription |
| `SLO: No Data Loss` | Data integrity SLO — P1 priority |
| `SLO: Code Quality` | Code quality SLO |
| `P0 - urgent` | Blocking — fix before anything else |
| `P1 - high` | High priority |
| `P2 - medium` | Normal priority |
| `P3 - low` | Low priority / nice to have |

---

## Questions

- **Issues & sprints:** [linear.app/coinscopeai](https://linear.app/coinscopeai)
- **Ops knowledge base:** [Notion — CoinScopeAI OS](https://www.notion.so/33a29aaf938e81efa983e47b83e15775)
- **Telegram:** `@ScoopyAI_bot`

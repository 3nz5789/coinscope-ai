# Codebase Guide

> Complete developer reference for the CoinScopeAI codebase.
> For setup: see [README](../README.md). For ops: see [docs/runbooks/](../docs/runbooks/).

---

## Module Map

### `coinscope_trading_engine/` — Core Engine

| Module | Purpose |
|---|---|
| `main.py` | FastAPI app entry point, startup/shutdown hooks |
| `api.py` | Router registration — mounts all endpoint groups |
| `config.py` | Pydantic Settings — env var schema with validation |
| `celery_app.py` | Celery worker config — Redis broker, result backend |
| `tasks.py` | Celery task definitions (purge_expired_data, etc.) |

#### `scanner/` — Signal Scoring

| File | What it does |
|---|---|
| `base_scanner.py` | Abstract `BaseScanner` interface — all scanners extend this |
| `volume_scanner.py` | Volume surge + CVD (Cumulative Volume Delta) analysis |
| `funding_rate_scanner.py` | Funding rate extreme detection (>0.08% = signal) |
| `liquidation_scanner.py` | Liquidation cluster detection |
| `orderbook_scanner.py` | Bid/ask imbalance, depth analysis |
| `pattern_scanner.py` | TA pattern recognition (EMA, RSI, ATR patterns) |

#### `scanners/` — Additional Scanners

| File | What it does |
|---|---|
| `scalp_scanner.py` | ScalpScanner — 6-factor confluence scoring (0–12) |
| `volume_scanner.py` | Volume scanner variant |
| `liquidation_scanner.py` | Liquidation scanner variant |

**Confluence scoring factors (0–2 pts each):**
1. RSI — oversold (<30) or overbought (>70)
2. EMA alignment — 20/50 EMA stack + price position
3. ATR momentum — body vs ATR ratio
4. Volume — vs 20-period average
5. Funding rate — extreme negative/positive signal
6. Open interest delta — 1h OI change confirmation

#### `core/` — Compliance Scaffold (P1.5)

| File | Purpose |
|---|---|
| `tos_gate.py` | FastAPI dependency — blocks API if ToS not accepted |
| `key_vault.py` | AES-256-GCM encrypted per-user exchange key vault |
| `cost_meter.py` | Per-user API cost tracking + tier ceiling enforcement |

#### `risk/` — Risk Gate + Position Sizing

The multi-layer defense system. Every candidate trade passes through all layers:

```
Layer 1 — Signal quality gate (scorer floor)
Layer 2 — Pre-trade risk gate (regime, heat, daily loss, kill switch)
Layer 3 — Kelly-fractional position sizing (hard 2% cap)
Layer 4 — Execution guardrails (slippage, ATR stops)
Layer 5 — Circuit breakers (drawdown, consecutive losses)
Layer 6 — Manual kill switch
```

See [`docs/risk/risk-framework.md`](../docs/risk/risk-framework.md).

#### `intelligence/` — HMM Regime Classifier

Hidden Markov Model v3 — classifies market regime in real-time:

| Regime | HMM state | Effect |
|---|---|---|
| Trending | Bull | Full multiplier (1.0) |
| Mean-Reverting | Chop | Half multiplier (0.5) |
| Volatile | — | Higher scoring floor |
| Quiet | Bear | 30% multiplier (0.3) |

See [`docs/ml/regime-detection.md`](../docs/ml/regime-detection.md).

---

### `coinscopeai-dashboard/` — React Dashboard

| Path | Purpose |
|---|---|
| `client/src/index.css` | Design system — OKLCH color tokens, HUD styles |
| `client/src/components/` | 10 CoinScopeAI HUD components |
| `client/src/components/ui/` | 45 shadcn/ui base components |
| `client/src/pages/` | Dashboard page views |
| `client/public/legal.html` | Public `/legal` disclosures page |
| `server/` | Dashboard BFF (Backend For Frontend) |

**Design tokens (key OKLCH values):**
```css
--primary:     oklch(0.70 0.17 162)  /* Emerald — profit, CTAs */
--accent:      oklch(0.75 0.12 200)  /* Cyan — highlights */
--destructive: oklch(0.60 0.22 25)   /* Crimson — loss, errors */
--background:  oklch(0.12 0.02 260)  /* Dark navy */
```

---

### `docs/` — Technical Documentation

| Path | Contents |
|---|---|
| `architecture/architecture.md` | System architecture v5 (8 tiers, 4 rails) |
| `architecture/design-system-manifest.md` | Design tokens v3, component inventory |
| `decisions/adr-000N-*.md` | Architecture Decision Records |
| `risk/risk-framework.md` | Risk philosophy, invariants, layer breakdown |
| `risk/risk-gate.md` | Gate logic detail |
| `risk/position-sizing.md` | Kelly pipeline |
| `risk/failsafes-and-kill-switches.md` | Circuit breakers, manual halt |
| `runbooks/daily-ops.md` | Daily operator checklist |
| `runbooks/local-development.md` | Local dev setup |
| `runbooks/digitalocean-deployment.md` | VPS deployment |
| `runbooks/release-checklist.md` | Pre-release gates |
| `ml/regime-detection.md` | HMM classifier design |
| `ml/confidence_scoring_baseline.md` | Confidence scoring framework |
| `incidents/` | Post-incident reports |

---

### `scripts/` — Operator Scripts

Run these from the project root:

```bash
# Check canonical doc consistency (run after any doc edit)
python3 scripts/drift_detector.py

# Check codebase for threshold violations (run after .env changes)
python3 scripts/risk_threshold_guardrail.py

# Morning engine brief (requires engine running)
./scripts/daily_status.sh

# Cross-platform structure check
python3 scripts/sync_verify.py

# Session-end auto-sync (git + drift + guardrail)
python3 scripts/auto_sync.py

# Rebuild GitHub labels (requires classic ghp_ token with repo scope)
export GH_TOKEN=ghp_your_token
python3 scripts/setup_github_labels.py
```

---

## Import Rules (post 2026-04-19 restructure)

**Exchange helpers must come from `app.integrations.<provider>`**:
```python
# ✅ Correct
from app.integrations.binance import get_klines, get_funding_rate, get_open_interest

# ❌ Wrong (stale pre-restructure path)
from app.engine.scanner import get_klines
```

OKX is **REST klines fallback only** — never for execution:
```python
# ✅ Allowed (data-only fallback for 451 regions)
from app.integrations.okx import get_klines as get_klines_okx

# ❌ Never use OKX for order placement
```

**LLM calls prohibited on the execution path** (ADR-0003):
```python
# ❌ Never import from app.integrations.openai in:
# app/engine/, app/services/, app/api/
```

---

## Environment Variables (key ones)

```bash
# Exchange (Binance Testnet)
BINANCE_TESTNET=true
BINANCE_TESTNET_API_KEY=
BINANCE_TESTNET_SECRET=

# Risk thresholds (LOCKED 2026-05-01)
MAX_LEVERAGE=10
MAX_OPEN_POSITIONS=5
MAX_DRAWDOWN_PCT=10
MAX_DAILY_LOSS_PCT=5
POSITION_HEAT_CAP_PCT=80

# Notion sync (canonical post 2026-04-23)
NOTION_API_KEY=
NOTION_SIGNAL_LOG_DB=d4bf243e-8e87-494d-838b-a96658af395b
NOTION_TRADE_JOURNAL_DB=43a542f4-b58d-4b1a-8979-043e72e9a6dd
NOTION_SCAN_HISTORY_DB=e72c5b69-fbbb-4a54-9dac-e6d4de3eb1a4

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=7296767446

# Vault (P1.5)
VAULT_MASTER_KEY=  # 32-byte base64
```

See [`.env.example`](../.env.example) for the full annotated list.

---

## PR & Commit Conventions

**Branch format:** `type/coi-NN-short-description`
```
fix/coi-55-scanner-imports
feat/coi-61-key-vault
chore/coi-53-requirements
```

**Commit format:** `type(scope): description`
```
fix(scanner): correct import paths after 2026-04-19 restructure
feat(core): add AES-256-GCM exchange key vault scaffold
docs(design-system): update manifest v3 — CSS tokens, HUD styles
chore(scripts): add auto-sync engine for session-end propagation
```

**Two-reviewer rule** applies to all changes touching:
- `risk/` — any risk logic
- `app/integrations/` — exchange adapters
- `.env.example` — threshold defaults
- `CLAUDE.md` — canonical operator instructions
- `docker-compose.yml` — infra stack
- `requirements.txt` — dependency manifest

---

## Validation Phase Rules

**Blocked until PCC v2 §8 passes:**
- Any canonical risk threshold change
- `BINANCE_TESTNET=false`
- Removing or bypassing any circuit breaker
- Retraining or replacing ML artifacts mid-validation
- Changing order submission semantics

**Free during validation:**
- Adding new scanner signals (no execution impact)
- UI / dashboard improvements
- Documentation and runbook updates
- Compliance scaffold (ToS gate, key vault, cost meter)
- Test coverage improvements

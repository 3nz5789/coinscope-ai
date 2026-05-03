# Configuration Reference

**Status:** current
**Audience:** developers and operators configuring the engine
**Related:** [`backend-overview.md`](backend-overview.md), [`../../.env.example`](../../.env.example), [`../ops/stripe-billing.md`](../ops/stripe-billing.md), [`../risk/risk-framework.md`](../risk/risk-framework.md)

Every environment variable the engine reads, what it controls, and what a sensible default is. Keep this in sync with `.env.example` — when you add a variable to one, update the other in the same PR.

The template at [`../../.env.example`](../../.env.example) is authoritative for field names and organization. This doc is authoritative for semantics.

## Required at boot

The engine fails loudly if any of these are missing.

| Variable | Example | Purpose |
| --- | --- | --- |
| `BINANCE_API_KEY` | `testkey_...` | Binance testnet API key. |
| `BINANCE_API_SECRET` | `testsecret_...` | Binance testnet API secret. |
| `BINANCE_TESTNET` | `true` | Must be `true` during validation. Flipping to `false` targets mainnet. |
| `DATABASE_URL` | `sqlite:///./journal.db` or `postgresql+psycopg://…` | Journal storage. |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + cache. |
| `API_AUTH_TOKEN` | (random string) | Bearer token for dashboard and operator calls. |

## App

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` | `local`, `staging`, or `production`. Affects log formatting. |
| `LOG_LEVEL` | `INFO` | Standard Python log levels. |
| `API_HOST` | `0.0.0.0` | Uvicorn bind host. |
| `API_PORT` | `8001` | Uvicorn bind port. Dashboard expects this. |
| `CORS_ORIGINS` | `https://coinscope.ai` | Comma-separated allowed origins. |

## Exchange — Binance

| Variable | Default | Purpose |
| --- | --- | --- |
| `BINANCE_API_KEY` | (required) | See above. |
| `BINANCE_API_SECRET` | (required) | See above. |
| `BINANCE_TESTNET` | `true` | Testnet toggle. **Locked `true` during validation.** |
| `BINANCE_REST_BASE` | auto-selected | Override REST base URL. Normally set by `BINANCE_TESTNET`. |
| `BINANCE_WS_BASE` | auto-selected | Override WS base URL. The 2026-04-23 path migration changes the default — see [`../ops/binance-adapter.md`](../ops/binance-adapter.md). |
| `BINANCE_RECV_WINDOW_MS` | `5000` | Binance `recvWindow` parameter. |
| `BINANCE_REQUEST_WEIGHT_MAX` | `1200` | Safety ceiling below Binance's 2400/min. |

## Exchange — planned (commented in `.env.example`)

Not wired up today. Values exist so that future adapters can pick them up without a config break.

- `BYBIT_*`
- `OKX_*`
- `HYPERLIQUID_*`

Leave these commented out during validation.

## Telegram alerts

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | (optional) | Bot token from @BotFather. Blank disables alerts. |
| `TELEGRAM_CHAT_ID` | (optional) | Target chat ID for alerts. |
| `TELEGRAM_ALERT_LEVEL` | `warning` | Minimum severity for alerts (`info`, `warning`, `error`, `critical`). |

Details: [`../ops/telegram-alerts.md`](../ops/telegram-alerts.md).

## Notion / operator tooling

| Variable | Default | Purpose |
| --- | --- | --- |
| `NOTION_TOKEN` | (optional) | Only used by operator scripts in `scripts/`. Not read by the engine. |
| `NOTION_DB_ID_*` | (optional) | Database IDs for operator-side sync. |

## Whale / on-chain

| Variable | Default | Purpose |
| --- | --- | --- |
| `WHALE_API_KEY` | (optional) | On-chain signal source. Currently best-effort; absence must not degrade trading. |

## OpenAI (commented)

The engine does not call an LLM on the hot path. Operator tooling may. Leave commented unless running that tooling locally.

- `OPENAI_API_KEY`

See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).

## Risk parameters — **locked during validation**

Changing any of these between 2026-04-10 and 2026-04-30 requires explicit sign-off outside the normal PR flow. The numbers below are the validation-era values.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAX_DAILY_LOSS_PCT` | `5.0` | Hard daily loss budget, as percent of equity. |
| `MAX_DRAWDOWN_PCT` | `10.0` | Peak-to-trough drawdown cap. |
| `MAX_LEVERAGE` | `10` | Per-trade leverage ceiling. Locked 2026-05-01 via PCC v2 §8 Capital Cap. |
| `MAX_OPEN_POSITIONS` | `5` | Cap on simultaneously open positions. |
| `POSITION_HEAT_CAP_PCT` | `80` | Total portfolio heat cap, as percent of equity. |
| `KELLY_FRACTION` | `0.25` | Fractional-Kelly factor. |
| `KELLY_HARD_CAP_PCT` | `2.0` | Absolute size cap per trade. |
| `REGIME_MULT_BULL` | `1.0` | HMM-bull regime multiplier. |
| `REGIME_MULT_CHOP` | `0.5` | HMM-chop regime multiplier. |
| `REGIME_MULT_BEAR` | `0.3` | HMM-bear regime multiplier. |
| `CONSECUTIVE_LOSSES_BREAKER` | `4` | Circuit-breaker threshold on losing streaks. |
| `CIRCUIT_BREAKER_RESET_HOURS` | `24` | Time to auto-reset a tripped breaker. |

## Signal thresholds

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCORER_FLOOR_DEFAULT` | `8` | Minimum confluence score to become a candidate. |
| `SCORER_FLOOR_TRENDING` | `7` | Per-regime floor override (v3 classifier). |
| `SCORER_FLOOR_VOLATILE` | `10` | Higher floor in volatile regime. |
| `ATR_STOP_MULTIPLIER` | `1.5` | Stop distance in ATR units. |
| `RR_RATIO` | `2.0` | Take-profit : stop ratio. |

## Scanner

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCANNER_UNIVERSE` | `top-50-by-volume` | Universe selection strategy. |
| `SCAN_INTERVAL_SECONDS` | `60` | Scanner cadence. |
| `SCANNER_SYMBOL_BLACKLIST` | `` | Comma-separated symbol opt-outs. |

## Regime detectors

| Variable | Default | Purpose |
| --- | --- | --- |
| `REGIME_HMM_ARTIFACT` | `ml/artifacts/hmm.pkl` | Path to the HMM artifact. |
| `REGIME_V3_ARTIFACT` | `ml/artifacts/regime_v3.joblib` | Path to the v3 classifier artifact. |
| `REGIME_REFRESH_SECONDS` | `300` | How often both detectors refresh. |

## Alpha decay

| Variable | Default | Purpose |
| --- | --- | --- |
| `ALPHA_DECAY_WINDOW_DAYS` | `30` | Rolling window for decay comparison. |
| `ALPHA_DECAY_WARN_THRESHOLD` | `0.5` | Fraction of rolling edge at which to flag. |

## Scale-up (inert during validation)

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCALE_UP_ENABLED` | `false` | Must remain `false` in validation. |
| `SCALE_UP_NOTIONAL_RAMP` | `0.01,0.05,0.25,1.0` | Ramp steps once enabled. |

## Walk-forward validation (WFV)

| Variable | Default | Purpose |
| --- | --- | --- |
| `WFV_TRAIN_WINDOW_DAYS` | `90` | Training window per WFV fold. |
| `WFV_TEST_WINDOW_DAYS` | `14` | Test window per fold. |
| `WFV_OUTPUT_DIR` | `./wfv_out` | WFV script output directory. |

## Stripe

| Variable | Default | Purpose |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | (required for billing) | Stripe server-side key. Use `sk_test_...` locally. |
| `STRIPE_WEBHOOK_SECRET` | (required for billing) | Verifies inbound webhook signatures. |
| `STRIPE_PRICE_ID_*` | (as configured) | One per product tier. |
| `BILLING_DB_URL` | `sqlite:///./billing_subscriptions.db` | Entitlements store. Can share `DATABASE_URL` in production. |

Details: [`../ops/stripe-billing.md`](../ops/stripe-billing.md).

## Observability

| Variable | Default | Purpose |
| --- | --- | --- |
| `PROMETHEUS_ENABLED` | `true` | Expose `/metrics`. |
| `METRICS_AUTH_TOKEN` | (optional) | Require a token on `/metrics` in hosted environments. |

## Changing a value

1. Edit `.env` for your machine.
2. If the variable is new, add it to `.env.example` with a comment explaining the default.
3. Update this doc in the same PR.
4. If the variable is risk-adjacent (any variable in the "Risk parameters" section), the PR is `risk-logic` and needs two reviewers. During validation, the answer is almost always "not now."

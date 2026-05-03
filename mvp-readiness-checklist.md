# CoinScopeAI MVP Readiness Checklist

**Purpose:** decide when CoinScopeAI is safe to connect to **real capital** (the post-validation, post-Phase-2 gate). This is not the "ship Phase 1 to testnet" gate — that one is COI-41.

**Last updated:** 2026-04-29
**Owner:** Mohammed
**Audit pass:** Scoopy, first cut — verify each 🟡 against current code before relying on it.

---

## Status legend

- ✅ Done · verified in main or live
- 🟡 Partial · code exists but needs verification, hardening, or wire-up
- ❌ Not started · belongs to a later phase or hasn't been built
- ⏸ N/A for MVP · explicitly Phase 3 or beyond
- 📍 Phase tag — which vendor-rollout phase is this gated on

---

## 1. Data & Providers

| Item | Status | Phase | Notes |
|---|---|---|---|
| Binance/Bybit via CCXT/CCXT Pro (REST + WS) | ✅ | P1 | Multi-exchange streams in main; Binance Testnet exec verified |
| OKX + Hyperliquid via CCXT (data) | ✅ | P1 | Data only; not used for execution during validation |
| Backtest data: Tardis.dev (tick / order book) | ❌ | P2 | Not yet wired |
| CoinGlass v4 — OI / funding / liquidations | ✅ | P1 | Live; verify `/derivatives` collector wiring |
| Binance trading-data endpoints (L/S, taker ratio) | 🟡 | P1 | Verify wiring in derivatives collector |
| CFGI.io Fear & Greed (primary) | ❌ | P2 | Not yet wired |
| CoinGlass Fear & Greed (secondary) | ❌ | P2 | Optional |
| News API — Tradefeeds (chosen for MVP) | 🟡 | P1 | Memory says Crypto News API was prior wiring — confirm Tradefeeds swap |
| Reference data — CoinGecko (primary) | 🟡 | P1 | Add if not already wired |
| Reference data — CoinMarketCap (optional) | ⏸ | P3 | Only if CMC IDs needed in reports |
| Coin Metrics (Security Master / Network Data) | ⏸ | P3 | Institutional layer; not MVP |
| Internal models defined: `Candle`, `Order`, `Position`, `FundingSnapshot`, `OiSnapshot`, `LiquidationSnapshot`, `SymbolSentiment`, `NewsItem`, `FearGreedSnapshot`, `AssetMeta` | 🟡 | P1 | Verify all 10 exist in `app/models/`; some (FearGreed, SymbolSentiment) likely don't yet |
| Engine never depends on vendor-specific field names | 🟡 | P1 | Audit ingestion adapters for leaky vendor names |

---

## 2. Data Quality, Monitoring & Failover

| Item | Status | Phase | Notes |
|---|---|---|---|
| Health checks per provider (Binance, Bybit, Tardis, CoinGlass, CFGI, news, Grok/LunarCrush) | 🟡 | P1+ | `/health` exists for engine; per-provider drilldown ❌ |
| Data status view (CLI / dashboard / API) — green/yellow/red per provider | ❌ | P1.5 | Should land in dashboard before real capital |
| Sanity check — price jump > X% vs prev tick + secondary src | ❌ | P1.5 | Not yet implemented |
| Sanity check — OI/funding/F&G clamped to historical bounds | ❌ | P1.5 | Not yet implemented |
| Fallback — WebSocket failure → REST polling | 🟡 | P1 | Verify in CCXT wrapper |
| Fallback — CFGI outage → proxy heuristic | ❌ | P2 | Gated on CFGI being wired |
| Alerting — provider outages / high error rates | 🟡 | P1 | Telegram bot built, blocked on COI-40 (VPS) |
| Alerting — stale data > N seconds on critical feeds | ❌ | P1.5 | Define thresholds + wire alerts |

---

## 3. Core Engine & Risk Controls

| Item | Status | Phase | Notes |
|---|---|---|---|
| End-to-end path tested — Signal → Risk Gate → Risk Manager → Position Sizer → Order Manager → Exchange | ✅ | P1 | Paper trading on Binance Testnet (4,955 USDT account) |
| Hard limit — max leverage per symbol | ✅ | P1 | Running: 10× (ceiling 20×) |
| Hard limit — max notional per symbol / per sector | 🟡 | P1 | Per-symbol via Position Sizer; per-sector ❌ |
| Hard limit — global account exposure cap | ✅ | P1 | `max_total_exposure_pct: 80` |
| Circuit breaker — auto-pause on data health red / extreme latency | 🟡 | P1.5 | `/circuit-breaker` endpoint exists; trigger logic needs review |
| Circuit breaker — auto-pause / flatten on daily / rolling DD beyond thresholds | ✅ | P1 | `max_daily_loss_pct: 2`, `max_drawdown: 10` |
| Fees · spread · slippage modeled in backtests | 🟡 | P1 | Verify backtest engine in main applies these realistically |

---

## 4. Backtesting & Strategy Validation

| Item | Status | Phase | Notes |
|---|---|---|---|
| `BacktestDataProvider` loads consistent slices from Tardis + CoinGlass | ❌ | P2 | Backtest engine exists in main; Tardis adapter is P2 |
| Historical coverage validated for BTC/ETH/main alts across multiple years | 🟡 | P2 | 110K+ candles in main; depth/years verify needed |
| Strategies tested across regimes (bull / bear / high-vol / low-vol / chop) | 🟡 | P2 | Regime Detector outputs labels; cross-regime test sweep TBD |
| Per-strategy metrics: CAGR, max DD, Sharpe / SQN, win rate, avg R, monthly PnL | 🟡 | P2 | Verify backtest report shape |
| Dumb baseline (always-long BTC, MA crossover) included | ❌ | P2 | Add for sanity comparison |

---

## 5. LLM & Tools Hygiene

| Item | Status | Phase | Notes |
|---|---|---|---|
| Claude is primary LLM with stable, minimal tool set | ✅ | P1 | Per Phase 1 lock |
| Tool: `get_sentiment_snapshot(symbol, timeframe)` | 🟡 | P1 | Exposed as `sentiment` tool — verify signature |
| Tool: `get_news_context(symbol, topic)` | 🟡 | P1 | Exposed as `news` tool — verify signature |
| Tool: `get_open_positions()` | 🟡 | P1 | Exposed as `positions` tool — verify signature |
| Tool: `get_backtest_summary(strategy_id)` | ❌ | P2 | Add when backtest dashboard ships |
| All tools call backend; backend calls external APIs | ✅ | P1 | ADR-004 invariant |
| Claude never sees API keys or raw vendor payloads | ✅ | P1 | ADR-004 invariant |
| Grok X Sentiment Collector writes numeric features only | ⏸ | P2 | Gated on Grok integration choice |
| Claude consumes only numeric features, not raw tweets | ⏸ | P2 | Same gate |

---

## 6. Observability & Audit Trail

| Item | Status | Phase | Notes |
|---|---|---|---|
| Structured logging with correlation IDs across components (signal → trade) | 🟡 | P1.5 | Verify log schema in `app/logging/` |
| Centralized metrics (Prometheus / Datadog / Sentry / Grafana) | ❌ | P1.5 | Observability stack is in arch but not stood up |
| Metric — API latency / error rates per provider | ❌ | P1.5 | Gated on observability stack |
| Metric — queue depths / throughput for ingestion + engine | ❌ | P1.5 | EventBus exposes counters; need scrape target |
| Metric — trading KPIs (daily PnL, open risk, per-strategy) | 🟡 | P1 | Available via `/performance` API; needs dashboard |
| Trade journal in PostgreSQL — feature snapshot + model outputs + risk overrides + final orders + realized PnL | 🟡 | P1 | EventBus journals events; verify the `journal` table shape carries everything in this list |

---

## 7. UX, Controls & Ops

| Item | Status | Phase | Notes |
|---|---|---|---|
| TradingView charts wired to own datafeed (price · entries/exits · indicators · sentiment overlays) | ❌ | P2 | TradingView is Phase 2 |
| Telegram bot — `/status` (data health + engine/risk) | 🟡 | P1 | Built; PENDING VPS (COI-40) |
| Telegram bot — `/positions` | 🟡 | P1 | Same |
| Telegram bot — `/signals` | 🟡 | P1 | Same |
| Telegram bot — `/kill_switch` | 🟡 | P1 | Same; verify wiring to `/circuit-breaker` |
| Config externalized (env / YAML / DB) and reloadable without redeploy | 🟡 | P1 | `/config` endpoint exists; reload behavior verify |
| Runbook — data vendor outage | ❌ | P1.5 | Author runbook |
| Runbook — exchange outage | ❌ | P1.5 | Author runbook |
| Runbook — massive volatility event | ❌ | P1.5 | Author runbook |
| Runbook — LLM / tool failure | ❌ | P1.5 | Author runbook |
| Deployment runbook (DO Singapore) | ✅ | P1 | `/CoinScopeAI/DO_DEPLOYMENT_GUIDE.md` |

---

## 8. Final Go-Live Checklist (real capital)

| Item | Status | Phase | Notes |
|---|---|---|---|
| All critical boxes above marked ✅ | ❌ | gate | Currently many 🟡 / ❌; full pass required |
| Dry-run period (paper trading) for ≥ N weeks with logged results | 🟡 | P1 | COI-41 30-day validation in flight (blocked on COI-40) |
| First real-money deployment uses very small notional + strict limits | ❌ | gate | Define "very small" — recommend ≤ 1% of intended live capital |
| Post-launch monitoring cadence (daily quick · weekly deep · monthly strategy) | ❌ | P1.5 | Define before going live |

---

## Gap summary — what's actually blocking real-capital go-live

**Blocking now (must close before validation can finish):**

1. COI-40 — DO Singapore droplet provisioning (frees Telegram bot, full stack, validation timer)
2. Tradefeeds wiring — confirm it replaces Crypto News API in main, or back-fill the swap
3. Internal model coverage — `FearGreedSnapshot` and `SymbolSentiment` likely missing from `app/models/`
4. Per-provider health checks — `/health` is engine-level, not provider-level

**Blocking before any real capital (P1.5 hardening pass):**

5. Observability stack — logs, metrics, alerts wired (Sentry / Grafana / uptime)
6. Sanity-check filters — price-jump, OI/funding/F&G bounds
7. Per-vendor circuit-breaker triggers (data-health → auto-pause)
8. Incident runbooks (vendor / exchange / volatility / LLM failure)
9. Per-symbol + per-sector notional caps (currently only global)
10. Trade-journal completeness audit — does the journal row carry every field listed in §6?

**Blocking before "institutional" claims (P2 dependencies):**

11. Tardis.dev for backtest fuel
12. CFGI.io F&G + sentiment confluence
13. TradingView charts + webhooks
14. Backtest dashboard + `get_backtest_summary` tool
15. Multi-regime test sweep + dumb baseline comparisons

**Strict invariants (do not break):**

- All orders → Binance Testnet during validation. No real capital.
- ADR-004 — no LLM call on the order path.
- Engine API is the only public surface.
- A halted Risk Gate stops every downstream step.
- Operator sync is one-way; never sources state for trading.

---

## Recommended next moves

1. **Unblock COI-40** — provision the DO droplet (60 seconds; gates 4+ items above).
2. **Audit `app/models/`** — confirm all 10 internal models exist; add the missing ones.
3. **Confirm news wiring** — Tradefeeds vs. Crypto News API; if Tradefeeds isn't wired, write the swap as a P1 lock task.
4. **Stand up observability** — Sentry + simple Grafana board for `/health` + per-provider counters. Smallest credible scope.
5. **Author the four incident runbooks** — copy-paste templates from the deploy guide; fill in.
6. **Define "small notional"** — write the dollar / leverage / position cap that will gate the first real-money trade.

This checklist is the gate; the architecture doc (`/CoinScopeAI/architecture/architecture.md`) is the map. Use them together.

---

## File location

- This checklist: `/CoinScopeAI/mvp-readiness-checklist.md`
- Companion: `/CoinScopeAI/architecture/architecture.md` (v3.1 canonical)
- Related Linear: COI-40 (VPS), COI-41 (validation phase), COI-53 (deps), COI-57 (ADR-004 enforcement)

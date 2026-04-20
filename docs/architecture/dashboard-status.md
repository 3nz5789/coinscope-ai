# Dashboard page status (2026-04-20)

Every page is accessible in the sidebar. Here's what each one actually shows,
whether it's **live** on the engine today, or still **mock**, and what it's
good for.

## CORE

| Page | Status | Source | What it's for |
|---|---|---|---|
| **Overview** | ✅ Live | `/account`, `/exposure`, `/circuit-breaker`, `/performance`, `/performance/equity`, `/account/positions` | One-glance account + risk + equity. The first page you open. Wallet, Margin, uPnL, exposure, risk-gate status, equity chart, open positions. |
| **Live Scanner** | ✅ Live | `/signals` (auto-refresh every 3 s), `POST /scan`, `POST /orders` via Execute button | The decision engine in real-time. Score, direction, scanners voted, reasons. "Execute" button for manual entry when score passes 65. |
| **Positions** | ✅ Live | `/account`, `/account/positions`, `/orders/algo/open` | Real Binance-Demo positions with entry, mark, uPnL, liquidation price, **live SL and TP from the attached Algo bracket**, and Close button (reduce-only MARKET). |
| **Trade Journal** | ✅ Live | `/journal` (OPEN + CLOSED rows, leverage, source badge, reasons in expanded row) | Audit trail. Click a row to see regime, score and the scanner reasons that fired the trade. |

## ANALYTICS

| Page | Status | Source | What it's for |
|---|---|---|---|
| **Performance** | ✅ Live | `/performance`, `/performance/daily` | Win rate, profit factor, Sharpe, max DD, avg win/loss, monthly breakdown (rolled up from the daily series). Will populate as real trades close. |
| **Equity Curve** | ✅ Live | `/performance/equity` | Equity + drawdown chart with 7D/30D/90D/ALL switcher. |
| **Risk Gate** | ✅ Live | `/circuit-breaker`, `/exposure`, `/config`, `POST /circuit-breaker/{trip,reset}` | Kill switch. Shows daily loss, open position count, exposure, max-leverage / max-positions thresholds. **The Power button physically halts autotrade.** |
| **Regime Detection** | ⚠️ MOCK | uses `REGIMES` from `mockData.ts` | Shows a regime timeline per symbol. Engine exposes `/regime` (point-in-time HMM) but no historical series yet — Phase 4 item. |

## TOOLS

| Page | Status | Source | What it's for |
|---|---|---|---|
| **Position Sizer** | ✅ Live | `GET /position-size` | Pre-compute qty + margin for a hypothetical trade. Used by the Execute dialog under the hood. |
| **Alpha Signals** | ⚠️ MOCK | funding / liquidation / orderbook / composite scores in `mockData.ts` | Would show per-exchange funding-rate table, liq cascades, order-book imbalance, and a composite alpha score. Engine has **some** of this data (funding inside `FundingRateScanner`, book imbalance inside `OrderBookScanner`) but no public endpoints that expose it cleanly — Phase 4. |
| **Market Data** | ⚠️ MOCK | per-exchange price grid, OI, funding, recent liquidations | Requires Bybit / OKX / Hyperliquid adapters which aren't built. Current engine is Binance-only. Phase 5 if/when multi-exchange is on the roadmap. |
| **Backtest Results** | ⚠️ MOCK | walk-forward quarters, strategy comparison, ML config performance | `signals/backtester.py` exists in the codebase but is not wired to any endpoint. Phase 3f planned: `POST /backtest/run` + `GET /backtest/jobs/{id}` + dashboard wiring. |

## SYSTEM

| Page | Status | Source | What it's for |
|---|---|---|---|
| **Settings** | ✅ Live | `/autotrade/*` | **The real control panel.** Autotrade ON/OFF, min-score slider, risk-per-trade, default leverage, cooldown, attach-bracket toggle, decision log of every autotrade event. |
| **Pricing** | ✅ Live | `/billing/plans`, `POST /billing/checkout` | Stripe test-mode plans pulled from the engine. Clicking a tier starts a real Stripe checkout session. |
| **System Status** | ⚠️ MOCK | WS state per exchange, recording daemon, Telegram counters | Engine has partial data (`/health`, `/prices.feed`, account sync age, scan loop status) but no unified `/system` roll-up yet. Phase 3e item — small work. |
| **Alerts** | ⚠️ MOCK | alert history list | Engine **sends** Telegram alerts (now working) but doesn't persist them. Would need an alerts log table + `/alerts?since=&limit=`. Phase 3e. |

## Summary of remaining work

| Work | Pages affected | Estimated effort |
|---|---|---|
| Persist regime history; expose `/regime/history` | Regime Detection | 1 h |
| Surface funding, liq, orderbook, alpha scores via public endpoints | Alpha Signals | 3 h (needs new endpoints, scanners already compute data) |
| Multi-exchange adapters | Market Data | 1–3 days per exchange; out of scope for demo-only |
| Wire `signals/backtester.py` + dashboard job runner | Backtest Results | 3 h |
| `/system` roll-up (WS state, scan loop, account sync age, Telegram stats) | System Status | 1 h |
| Alert log persistence + `/alerts` endpoint | Alerts | 1 h |

## Recommended next steps

1. **Backtest integration (Phase 3f)** — highest-value next, because it tells you whether the current scanner mix is profitable on recent history before you scale risk.
2. **`/system` + Alerts log (Phase 3e)** — quick win, makes the dashboard feel complete and gives ops confidence.
3. **Alpha Signals endpoints** — the scanner internals are valuable on their own page (funding skew and liq cascades are popular alpha views).
4. **Regime history** — small, nice-to-have, unblocks Regime Detection page.

Everything else (multi-exchange, ML model training UI) is a larger sprint
that depends on product direction.

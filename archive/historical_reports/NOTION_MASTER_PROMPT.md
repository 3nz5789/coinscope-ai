# CoinScopeAI — Notion Workspace Master Setup Prompt

> **How to use:** Paste this entire prompt to Claude (with Notion MCP connected) to build the full CoinScopeAI workspace automatically. Run it once. It is idempotent-safe — re-running only fills gaps.

---

## PROMPT START

You are setting up the **CoinScopeAI** trading intelligence workspace in Notion. Build the complete structure below exactly as specified — databases with all properties, views, and starter pages. Do not summarize or skip steps.

---

## 1. WORKSPACE STRUCTURE

Create the following top-level pages under a root page called **"🤖 CoinScopeAI"**:

```
🤖 CoinScopeAI
├── 🎯 Mission Control          ← Hub page with live embeds + quick-links
├── 📡 Signal Log               ← Database: every scan signal (auto-logged)
├── 📈 Trade Journal            ← Database: manually logged trades
├── 🔍 Scan History             ← Database: per-scan metadata snapshots
├── 🏥 Engine Status            ← Page: health check results + testnet log
├── 📊 Performance Dashboard    ← Page: weekly P&L, win rate, drawdown
├── ⚙️ Config Vault             ← Page: settings reference, .env template, API docs
└── 📚 Strategy Library         ← Page: scoring logic docs, regime guide, rules
```

---

## 2. DATABASE: 📡 Signal Log

**Purpose:** Records every actionable signal produced by the market scanner. One row per signal per scan.

### Properties

| Property Name        | Type          | Options / Notes                                                                      |
|----------------------|---------------|--------------------------------------------------------------------------------------|
| Signal               | Title         | Auto-named: `{PAIR} {DIRECTION} {DATE}` e.g. "BTC/USDT LONG 2026-04-04"            |
| Pair                 | Select        | BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT, TAO/USDT                        |
| Direction            | Select        | LONG 🟢, SHORT 🔴, NEUTRAL ⚪                                                        |
| Score (0–12)         | Number        | Format: Number, 1 decimal place                                                     |
| Strength Label       | Select        | 💎 Very Strong (9–12), 🟢 Strong (7.5–8.9), 🟠 Good (6–7.4), 🟡 Moderate (5–5.9), ⚫ Weak (<5) |
| Regime               | Select        | 🟢 Bull, 🔴 Bear, 🟡 Chop                                                            |
| MTF Confirmed        | Select        | ✅ Confirmed, ⚠️ Unconfirmed, ❌ Conflicting                                          |
| RSI                  | Number        | Format: Number, 1 decimal place                                                     |
| Funding Rate %       | Number        | Format: Percent, 3 decimal places. Flag if abs > 0.08%                             |
| OI Change 1h %       | Number        | Format: Percent, 1 decimal place. Positive = new longs, Negative = closing          |
| Timeframe            | Select        | 1m, 5m, 15m, 1h, 4h, 1d                                                            |
| Price at Signal      | Number        | Format: Number, 2 decimal places                                                    |
| Scan Timestamp       | Date          | Include time. UTC timezone.                                                          |
| Status               | Select        | 🟡 Active, ✅ Taken, ⏭ Skipped, 💀 Expired, 🔄 Watching                             |
| Notes                | Text          | Free text observations                                                              |
| Linked Trade         | Relation      | → Trade Journal (1:1 or 1:many)                                                    |
| Linked Scan          | Relation      | → Scan History                                                                      |
| Sub-scores           | Text          | JSON or formatted string: `RSI:1.5 | EMA:2 | ATR:1 | VOL:2 | CVD:1 | ENTRY:1`    |
| Engine Mode          | Select        | ENGINE, STANDALONE                                                                  |
| Funding Warning ⚠️   | Checkbox      | True if abs(funding rate) > 0.08%                                                   |

### Views

1. **📡 Live Feed** (Default Table) — Sort by Scan Timestamp DESC. Filter: Status = Active OR Watching. Show: Pair, Direction, Score, Strength, Regime, MTF, Funding Rate, OI Change, Status.

2. **💎 High Conviction** (Filtered Table) — Filter: Score ≥ 7.5 AND Direction ≠ NEUTRAL AND MTF Confirmed ≠ ❌ Conflicting. Sort: Score DESC.

3. **📅 Today's Signals** (Filtered Table) — Filter: Scan Timestamp = Today. All columns.

4. **🟢 Longs Only** (Filtered Table) — Filter: Direction = LONG.

5. **🔴 Shorts Only** (Filtered Table) — Filter: Direction = SHORT.

6. **🏆 Score Board** (Gallery) — Sort: Score DESC. Card preview: Score, Pair, Direction, Regime, MTF. Group by: Strength Label.

7. **📆 Signal Calendar** (Calendar) — Date property: Scan Timestamp.

---

## 3. DATABASE: 📈 Trade Journal

**Purpose:** Manual log of every trade actually taken. Connected to Signal Log via Relation.

### Properties

| Property Name       | Type          | Notes                                                                                 |
|---------------------|---------------|---------------------------------------------------------------------------------------|
| Trade               | Title         | e.g. "BTC LONG 2026-04-04 #001"                                                      |
| Pair                | Select        | BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT, TAO/USDT                         |
| Direction           | Select        | LONG 🟢, SHORT 🔴                                                                     |
| Entry Price         | Number        | Format: Number, 2 decimal places                                                     |
| Exit Price          | Number        | Format: Number, 2 decimal places                                                     |
| Size (USDT)         | Number        | Position size in USDT                                                                |
| Leverage            | Number        | Integer (e.g. 5)                                                                     |
| Stop Loss           | Number        | Stop price                                                                           |
| Take Profit 1       | Number        | First TP level                                                                       |
| Take Profit 2       | Number        | Second TP level (optional)                                                           |
| Entry Time          | Date          | Include time. UTC.                                                                   |
| Exit Time           | Date          | Include time. UTC. Empty if still open.                                              |
| Status              | Select        | 🟢 Open, ✅ Win, ❌ Loss, 🔄 Breakeven, 🛑 Stopped Out, 🏃 Partial                   |
| P&L (USDT)          | Number        | Realized P&L in USDT                                                                |
| P&L %               | Number        | Format: Percent, 2 decimal places                                                   |
| R:R Actual          | Number        | Format: Number, 2 decimal places (e.g. 2.3)                                        |
| R:R Planned         | Number        | Pre-trade planned risk:reward                                                       |
| Signal Score        | Number        | Score from Signal Log at time of entry                                              |
| Regime at Entry     | Select        | 🟢 Bull, 🔴 Bear, 🟡 Chop                                                            |
| MTF at Entry        | Select        | ✅ Confirmed, ⚠️ Unconfirmed, ❌ Conflicting                                          |
| Conviction          | Select        | 💎 Max, 🟢 High, 🟡 Medium, ⚫ Low                                                   |
| Kelly % Used        | Number        | Format: Percent, 1 decimal place                                                    |
| Mistakes            | Multi-select  | Chased Entry, Ignored MTF, Oversized, Wrong Regime, Moved Stop, FOMO, Early Exit   |
| Lessons             | Text          | Post-trade notes                                                                    |
| Source Signal       | Relation      | → Signal Log                                                                        |
| Screenshot          | Files & Media | Entry/exit chart screenshot                                                         |

### Views

1. **📖 All Trades** (Table) — Sort by Entry Time DESC. All columns.

2. **🟢 Open Trades** (Table) — Filter: Status = Open OR Partial. Visible: Pair, Direction, Entry Price, Stop Loss, Size, Entry Time.

3. **✅ Closed Trades** (Table) — Filter: Status = Win OR Loss OR Breakeven OR Stopped Out. Sort: Exit Time DESC.

4. **💰 P&L Tracker** (Table) — Show: Trade, Pair, Direction, P&L (USDT), P&L %, R:R Actual, Status, Mistakes. Sort: Entry Time DESC.

5. **📊 Win/Loss Board** (Board) — Group by: Status. Cards show P&L %.

6. **⚠️ Mistake Analyzer** (Table) — Filter: Mistakes is not empty. Show: Trade, Mistakes, Lessons, P&L %.

---

## 4. DATABASE: 🔍 Scan History

**Purpose:** Logs metadata for every market scan run, giving a high-level view of market conditions over time.

### Properties

| Property Name       | Type          | Notes                                                    |
|---------------------|---------------|----------------------------------------------------------|
| Scan Name           | Title         | Auto: `SCAN {TIMESTAMP}` e.g. "SCAN 2026-04-04 16:04"  |
| Timestamp           | Date          | UTC. Include time.                                       |
| Timeframe           | Select        | 1h, 4h, 1d                                              |
| Pairs Scanned       | Number        | Count of pairs checked                                   |
| Signals Found       | Number        | Count of signals above threshold                        |
| Avg Score           | Number        | Average score of all scanned pairs                      |
| Top Signal Pair     | Select        | Best-scoring pair                                       |
| Top Signal Score    | Number        | Score of the best pair                                  |
| Top Direction       | Select        | LONG 🟢, SHORT 🔴, NEUTRAL ⚪                           |
| Market Regime       | Select        | 🟢 Bull, 🔴 Bear, 🟡 Chop, ⚪ Mixed                    |
| Engine Mode         | Select        | ENGINE, STANDALONE                                      |
| BTC Regime          | Select        | 🟢 Bull, 🔴 Bear, 🟡 Chop                              |
| BTC Price           | Number        | BTC price at time of scan                               |
| Notes               | Text          | Manual observations                                     |
| Linked Signals      | Relation      | → Signal Log (1:many)                                   |

### Views

1. **📅 Scan Timeline** (Table) — Sort: Timestamp DESC. All columns.
2. **📈 Regime History** (Table) — Show: Timestamp, Market Regime, BTC Regime, Avg Score, Signals Found, Top Signal Pair.
3. **🗓 Scan Calendar** (Calendar) — Date: Timestamp.

---

## 5. PAGE: 🎯 Mission Control

Create this as a rich **hub page** with the following sections. Use headings, callout blocks, and database embeds.

```
# 🤖 CoinScopeAI — Mission Control

---

> ⚡ **Engine Status:** [MANUAL UPDATE DAILY — or connect via API]
> Mode: TESTNET | Last scan: [auto-link to latest Scan History entry]

---

## 🔴 Active Signals Right Now
[Embed: Signal Log → "📡 Live Feed" view]

---

## 💎 High Conviction Setups
[Embed: Signal Log → "💎 High Conviction" view]

---

## 📖 Open Trades
[Embed: Trade Journal → "🟢 Open Trades" view]

---

## 📅 Today at a Glance
[Embed: Signal Log → "📅 Today's Signals" view]

---

## ⚙️ Quick Actions
- 🔁 [Run New Scan → prompt Claude]
- 📐 [Size a Position → Kelly Calculator]
- 📋 [Log a Trade → Trade Journal]
- 🏥 [Check Engine Health → Engine Status page]
```

---

## 6. PAGE: 🏥 Engine Status

```
# 🏥 Engine Status & Testnet Log

## Current Mode
- **Mode:** TESTNET (set TESTNET_MODE=true in .env)
- **Engine URL:** http://localhost:8001
- **Binance Testnet REST:** https://testnet.binancefuture.com
- **Binance Testnet WS:** wss://stream.binancefuture.com

---

## Health Check Results

| Check | Status | Last Tested | Notes |
|-------|--------|-------------|-------|
| Env vars loaded | ✅ / ❌ | [date] | |
| Testnet REST ping | ✅ / ❌ | [date] | |
| Account balance | ✅ / ❌ | [date] | USDT balance |
| Klines fetch | ✅ / ❌ | [date] | BTCUSDT 4h |
| WebSocket stream | ✅ / ❌ | [date] | Non-fatal |
| Signal generation | ✅ / ❌ | [date] | Score output |
| Telegram bot | ✅ / ❌ | [date] | Non-fatal |

---

## Testnet Run Log

[Date] — testnet_check.py output:
```
[Paste full terminal output here]
```

---

## Issues & TODOs
- [ ] Add TELEGRAM_BOT_TOKEN to .env (non-fatal but recommended)
- [ ] Validate HMM regime detector on testnet data
- [ ] Run main.py --testnet --dry-run and verify signal pipeline
```

---

## 7. PAGE: 📊 Performance Dashboard

```
# 📊 Performance Dashboard

## Summary Metrics (update weekly)

| Metric              | Value  |
|---------------------|--------|
| Total Trades        |        |
| Win Rate            |        |
| Avg Win (USDT)      |        |
| Avg Loss (USDT)     |        |
| Profit Factor       |        |
| Avg R:R (Actual)    |        |
| Max Drawdown        |        |
| Net P&L (USDT)      |        |
| Best Trade          |        |
| Worst Trade         |        |

---

## Equity Curve
[Embed Trade Journal sorted by date — P&L cumulative]

---

## By Pair
[Embed Trade Journal grouped by Pair — show avg P&L %]

---

## By Signal Score Range
| Score Range | Trades | Win Rate | Avg P&L |
|-------------|--------|----------|---------|
| 9–12 (Very Strong) | | | |
| 7.5–8.9 (Strong)   | | | |
| 6–7.4 (Good)       | | | |
| 5–5.9 (Moderate)   | | | |

---

## Common Mistakes (Last 30 days)
[Embed Trade Journal → Mistake Analyzer view]
```

---

## 8. PAGE: ⚙️ Config Vault

```
# ⚙️ Config Vault — Settings & Reference

> ⚠️ Store actual API keys in .env only — never paste them here.

---

## .env Template

```env
# ─── Binance ───────────────────────────────────
BINANCE_TESTNET_API_KEY=your_testnet_key_here
BINANCE_TESTNET_API_SECRET=your_testnet_secret_here
BINANCE_API_KEY=               # Leave blank until live
BINANCE_API_SECRET=            # Leave blank until live

# ─── Mode ──────────────────────────────────────
TESTNET_MODE=true              # Set to false when going live
ENV=development                # development | production

# ─── FastAPI Engine ────────────────────────────
PORT=8001
SECRET_KEY=your_secret_key_here

# ─── Telegram (optional) ───────────────────────
TELEGRAM_BOT_TOKEN=            # Optional: signal alerts
TELEGRAM_CHAT_ID=              # Your chat or group ID

# ─── Redis / Celery ────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ─── Scoring ───────────────────────────────────
MIN_SCORE_THRESHOLD=5.5
MAX_PAIRS=6
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Engine health check |
| /scan | GET | Run market scan (params: pairs, timeframe) |
| /signal/{symbol} | GET | Single pair signal |
| /regime | GET | Current market regime |
| /position-size | POST | Kelly position sizer |
| /alerts | GET/POST | Telegram alert management |

---

## Scoring Reference (FixedScorer 0–12)

| Component     | Max | LONG Condition (score 2) | SHORT Condition (score 2) |
|---------------|-----|--------------------------|---------------------------|
| RSI Momentum  | 2   | RSI 55–65                | RSI 35–45                 |
| EMA Trend     | 2   | EMA9 > EMA21 + slope ↑   | EMA9 < EMA21 + slope ↓    |
| ATR Vol       | 2   | ATR 0.5–2.0% of price    | ATR 0.5–2.0% of price     |
| Volume        | 2   | Vol ≥ 1.5× 20-bar MA     | Vol ≥ 1.5× 20-bar MA      |
| CVD Slope     | 2   | Positive (last 10 bars)  | Negative (last 10 bars)   |
| Entry Timing  | 2   | 0.1–1.5 ATR above EMA21  | 0.1–1.5 ATR below EMA21   |

---

## Regime Guide

| Regime | Conditions | Signal Adjustment |
|--------|------------|-------------------|
| 🟢 Bull | EMA9 > EMA21, positive slope, ATR% ≥ 0.3% | Full score weight |
| 🔴 Bear | EMA9 < EMA21, negative slope, ATR% ≥ 0.3% | Full score weight |
| 🟡 Chop | ATR% < 0.3% OR EMA9 ≈ EMA21 | Demote 1 tier in ranking |

---

## Startup Commands

```bash
# Start the engine (testnet)
cd coinscope_trading_engine
uvicorn api:app --reload --port 8001

# Run smoke test
python testnet_check.py

# Run dry-run (no orders placed)
python main.py --testnet --dry-run

# Market scanner (standalone)
python /path/to/market_scanner.py --pairs BTC/USDT,ETH/USDT,SOL/USDT --top 5 --tf 4h
```
```

---

## 9. PAGE: 📚 Strategy Library

```
# 📚 Strategy Library

## Core Trading Rules

1. **Never trade signals below Score 5.5** — skip anything labeled ⚫ Weak
2. **Chop regime = half size or skip** — ATR% < 0.3% means no trending conditions
3. **MTF conflict = no trade** — if ❌ Conflicting, pass regardless of score
4. **Funding > 0.08% long** — beware longs; crowd is already long (mean-reversion risk)
5. **Funding < -0.08% short** — beware shorts; crowd is already short
6. **OI falling + signal = caution** — positions are closing, not opening
7. **Max 3 concurrent trades** — diversification within limit
8. **Kelly sizing** — never exceed 2× Kelly; use half-Kelly as default
9. **Stop loss mandatory** — set before entry, never move against position
10. **Score ≥ 9 (Very Strong)** — can size up to 1.5× normal; still respect Kelly ceiling

## Signal Strength → Position Size Matrix

| Score | Label | Default Size | Max Size |
|-------|-------|-------------|---------|
| 9–12  | 💎 Very Strong | 1.0× Kelly | 1.5× Kelly |
| 7.5–8.9 | 🟢 Strong | 0.75× Kelly | 1.0× Kelly |
| 6–7.4 | 🟠 Good | 0.5× Kelly | 0.75× Kelly |
| 5–5.9 | 🟡 Moderate | 0.25× Kelly | Watch only |
| < 5   | ⚫ Weak | No trade | No trade |

## Chop Regime Adjustments
- Treat any score as 1 tier lower
- Reduce size by 50%
- Tighten stops to 0.5× normal ATR distance
- Avoid TAO/USDT in chop (thin liquidity)
```

---

## EXECUTION INSTRUCTIONS FOR CLAUDE (Notion MCP)

When executing this prompt with Notion MCP access, follow this sequence:

1. **Create root page** "🤖 CoinScopeAI" at the workspace root (or inside a specified parent page)
2. **Create all 8 sub-pages/databases** as children of the root page
3. For each **database**, create all properties in the exact order listed, using the correct property types
4. For each **database**, create all **views** as specified (table, board, calendar, gallery)
5. **Populate Mission Control** with the section structure and database embeds
6. **Populate all template pages** (Engine Status, Performance Dashboard, Config Vault, Strategy Library) with the content shown
7. After completing each item, **confirm** with a ✅ status line
8. At the end, output a **completion summary** listing all created items with Notion page links

Do not ask for clarification — build the full workspace now.

---

## PROMPT END

# Runbook: Daily Market Scan
**Owner:** Mohammed (Scoopy / @ScoopyAI_bot) | **Frequency:** Daily (4× per day + EOD summary)
**Last Updated:** 2026-04-16 | **Environment:** Binance Testnet only

---

## Purpose

Run the CoinScopeAI market scanner to identify high-probability LONG/SHORT setups across 6 USDT-perpetual futures pairs, validate each signal through the risk gate, size approved positions, and log results to Notion. Used every morning, midday, afternoon, and evening during the 30-day testnet validation phase.

**Primary goal: Capital preservation first. No trade without risk gate clearance.**

---

## Prerequisites

- [ ] VPS is online (DigitalOcean SGP1) and the CoinScopeAI Docker stack is running
- [ ] Engine API responding at `http://localhost:8001` (or SSH tunnel to VPS)
- [ ] `.env` is populated: `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_API_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NOTION_TOKEN`
- [ ] Python venv active with `ccxt>=4.0.0`, `numpy>=1.24.0`, `pandas>=2.0.0`, `requests>=2.28.0`
- [ ] Testnet account balance confirmed: baseline ~4,955.54 USDT
- [ ] Notion workspace accessible: https://www.notion.so/33a29aaf938e81efa983e47b83e15775

---

## Scan Schedule

| UTC Time | Local (UTC+3) | Scan Type |
|----------|--------------|-----------|
| 05:00 | 08:00 | **Morning Full Scan** — start of day, primary setup window |
| 09:00 | 12:00 | Midday Quick Scan |
| 13:00 | 16:00 | **Afternoon Full Scan** — second primary window |
| 17:00 | 20:00 | Evening Full Scan |
| 21:00 | 00:00 | Daily Summary + Notion sync |

---

## Procedure

### Step 1 — Health Check

Run the bundled health check script to confirm all 6 engine endpoints are UP before scanning:

```bash
bash scripts/health_check.sh http://localhost:8001
```

**Expected result:** All 6 endpoints report `UP`. Output shows green for `/scan`, `/performance`, `/journal`, `/risk-gate`, `/position-size`, `/regime/{symbol}`.

**If it fails:** Engine is offline. Start (or restart) the engine:
```bash
cd coinscope_trading_engine
uvicorn api:app --reload --port 8001
```
If the VPS is the deployment target, SSH in and run:
```bash
docker compose up -d redis api
```
If engine still won't start, the scanner will automatically fall back to **Standalone Mode** (ccxt-direct computation). Proceed to Step 2 — results will still be valid, just without HMM regime detection.

---

### Step 2 — Risk Gate Check

**Always check the risk gate before running the scanner.** If the gate is blocked, there is nothing to scan for today.

```bash
python3 scripts/risk_check.py http://localhost:8001
```

Or directly via curl:
```bash
curl -s http://localhost:8001/risk-gate | python3 -m json.tool
```

**Expected result:**
```json
{
  "status": "success",
  "data": {
    "daily_loss_limit_hit": false,
    "drawdown_limit_hit": false,
    "kill_switch_armed": false
  }
}
```

**If `daily_loss_limit_hit: true`:** Daily loss has reached 5% of account. **Stop — no new trades today.** Log this in Notion (Monitoring & Incidents page). Reset tomorrow morning.

**If `drawdown_limit_hit: true`:** Drawdown from peak has reached 10%. **Kill switch protocol — see Escalation section.**

**If `kill_switch_armed: true`:** System has halted all entries. Review open positions, confirm no exposure, then investigate root cause before disarming.

---

### Step 3 — Run the Full Market Scan

```bash
python market_scanner_skill/market_scanner.py \
  --pairs BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,TAO/USDT \
  --top 5 \
  --min-score 5.5 \
  --filter ALL \
  --tf 4h
```

For a LONG-only morning session (e.g. macro bull trend):
```bash
python market_scanner_skill/market_scanner.py --filter LONG --min-score 6.0 --tf 4h
```

For a quick midday re-scan (top 3 only):
```bash
python market_scanner_skill/market_scanner.py --top 3 --min-score 6.0
```

**Expected result:** A ranked signal table in this format:

```
📡  MARKET SCAN — 2026-04-16 05:02 UTC  [ENGINE]
Scanned: 6 pairs  |  Active Signals: 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RANK  PAIR         SIG    SCORE   TF    RSI     REGIME         MTF   FUND%    OI Δ%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1     BTC/USDT     LONG   8.5     4h    61.2    🟢 Bull        ✅    -0.010%  +3.2%
2     ETH/USDT     LONG   7.8     4h    58.4    🟢 Bull        ✅    +0.010%  +1.8%
3     SOL/USDT     SHORT  6.2     4h    38.1    🔴 Bear        ⚠️    +0.030%  -2.1%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If no signals appear above min_score:** Market may be in chop. Lower threshold to 5.0 and recheck in 15–30 min or switch to 1H timeframe. Do not force trades.

**If mode shows `[STANDALONE]`:** Engine is offline but scan is still valid (ccxt-based). Note in Notion log.

---

### Step 4 — Interpret Signal Quality

Use this decision tree for each signal returned:

```
Signal received
│
├─ Score < 5.5 → SKIP
│
├─ Regime = Chop?
│   ├─ Score < 8.0 → SKIP
│   └─ Score ≥ 8.0 → PROCEED at 50% normal size
│
├─ MTF = ❌ Conflicting → SKIP or reduce size significantly
│
├─ Funding rate > +0.08% on LONG signal → ⚠️ Mean-reversion risk — skip or wait
├─ Funding rate < -0.08% on SHORT signal → ⚠️ Mean-reversion risk — skip or wait
│
├─ OI Δ% decreasing while signal is active → lower confidence, flag ⚠️
│
└─ Score ≥ 5.5, Gate CLEAR, Regime ≠ Chop, MTF ≠ ❌
    ├─ Score 5.5–6.9 → Reduced size only, confirm entry manually
    ├─ Score 7.0–8.9 → Standard size — proceed
    └─ Score ≥ 9.0   → Full size — high priority
```

**Score reference:**

| Score | Label | Action |
|-------|-------|--------|
| 0.0–4.9 | ⚫ Weak | Skip |
| 5.0–5.9 | 🟡 Moderate | Watch only |
| 6.0–7.4 | 🟠 Good | Valid — confirm MTF + regime |
| 7.5–8.9 | 🟢 Strong | Proceed normally |
| 9.0–12.0 | 💎 Very Strong | Maximum priority |

---

### Step 5 — Check Regime Confidence for Top Signals

For each signal you intend to act on, verify regime confidence:

```bash
curl -s http://localhost:8001/regime/BTCUSDT | python3 -m json.tool
```

Replace `BTCUSDT` with the relevant symbol (no slash — engine format).

**Expected result:**
```json
{
  "status": "success",
  "data": {
    "symbol": "BTCUSDT",
    "regime": "trending",
    "confidence": 0.92
  }
}
```

Regime labels (v3 ML): `Trending`, `Mean-Reverting`, `Volatile`, `Quiet`.

**If confidence < 0.70:** Treat as Chop — reduce size or skip. Do not apply full sizing rules.

---

### Step 6 — Size the Position

For each approved signal, query the position sizer:

```bash
curl -s "http://localhost:8001/position-size?symbol=BTCUSDT" | python3 -m json.tool
```

**Expected result:**
```json
{
  "status": "success",
  "data": {
    "symbol": "BTCUSDT",
    "recommended_size_usdt": 500.00,
    "leverage": 5
  }
}
```

**Hard limits — never exceed regardless of signal strength:**

| Limit | Threshold |
|-------|-----------|
| Daily loss | 5% of account |
| Max drawdown | 10% from peak |
| Position heat (total deployed) | 80% of available capital |
| Max leverage | 20× |
| Max open positions | 3 simultaneously |

**If the recommended size exceeds your risk tolerance at current drawdown level:** Scale down manually. The sizer is advisory — position heat cap is a hard rule.

---

### Step 7 — Log Signals to Notion

All scan results must be logged to the Scan History database regardless of whether a trade is taken.

Notion Scan History DB ID: `c008175e-cfc0-4553-ab37-c47c3825f2e3`
Notion workspace: https://www.notion.so/33a29aaf938e81efa983e47b83e15775

Log the following for each scan:
- Timestamp (UTC)
- Pairs scanned
- Top signal(s) returned (pair, direction, score, regime)
- Risk gate status at time of scan
- Action taken (Trade logged / Skipped / No signals)
- Scanner mode (Engine / Standalone)

If a trade entry is taken, also log to the Trade Journal (`1430e3fb-d21b-49e7-b260-9dfa4adcb5f0`):
- Symbol, Side (LONG/SHORT)
- Entry price, Stop loss, Target
- Signal score
- Position size (USDT), leverage

---

### Step 8 — Telegram Alert Verification

After a scan that produces signals with score ≥ 8.0, confirm the Telegram alert was sent to @ScoopyAI_bot (Chat ID: `7296767446`).

If no alert arrived within 60 seconds of scan completion:

1. Check `.env` for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID=7296767446`
2. Test manually:
```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=7296767446&text=Scoopy+alert+test"
```
3. If that works but automated alerts don't: check `alerts/telegram_alerts.py` for threshold configuration

---

### Step 9 — End-of-Day Summary

Run once per day (21:00 UTC / 00:00 local):

```bash
curl -s http://localhost:8001/performance | python3 -m json.tool
curl -s http://localhost:8001/journal | python3 -m json.tool
```

Review:
- `win_rate` — target ≥ 55% over rolling 30 days
- `current_drawdown` — flag if approaching 7% (alert zone before 10% hard stop)
- `profit_factor` — target ≥ 1.5
- Open trades — confirm all have stop-loss set on testnet

Log the summary to Notion → Executive Dashboard page (01):
https://www.notion.so/33a29aaf938e8192af9deaada6a36a0a

---

## Verification Checklist

After completing the full scan procedure, confirm:

- [ ] Health check passed (or standalone fallback noted)
- [ ] Risk gate is GREEN (not blocked)
- [ ] Scan output shows timestamp + mode label `[ENGINE]` or `[STANDALONE]`
- [ ] All signals below 5.5 discarded
- [ ] Chop regime signals treated at reduced size or skipped
- [ ] Funding rate extremes (>±0.08%) flagged
- [ ] Position size within hard limits (heat < 80%, leverage ≤ 20×, positions ≤ 3)
- [ ] Scan result logged to Notion Scan History
- [ ] Trade entry (if taken) logged to Notion Trade Journal
- [ ] Telegram alert received for any signal ≥ 8.0

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Connection refused` on engine check | Engine not running | `cd coinscope_trading_engine && uvicorn api:app --reload --port 8001` (local) or `docker compose up -d redis api` (VPS) |
| Scanner output shows `[STANDALONE]` | Engine offline | Engine fell back to ccxt mode — results still valid. Restart engine when possible |
| `No signals above min_score` | Market in chop / flat | Lower min_score to 5.0, check back in 15–30 min or switch to `--tf 1h` |
| `Notion sync failed — 401` | Notion token expired | Update `NOTION_TOKEN` in `.env`, restart engine |
| `Notion sync failed — 403` | Integration not shared | Open Notion DB → Share → Invite CoinScopeAI integration |
| Telegram alert not arriving | Bot config wrong | Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID=7296767446` in `.env`; test with manual curl |
| RSI/EMA values look wrong | Insufficient candle data | Check ccxt connection to Binance testnet; ensure ≥120 OHLCV bars available |
| Regime stuck on `Chop` for all pairs | HMM model stale | Run `python coinscope_trading_engine/alerts/retrain_scheduler.py` — **only after validation phase ends** (code freeze active) |
| Score always < 5.5 across all pairs | Data feed degraded | Check Binance Testnet connectivity; try ccxt direct: `python -c "import ccxt; e=ccxt.binance({'options':{'defaultType':'future'}}); print(e.fetch_ticker('BTC/USDT'))"` |
| Dashboard shows amber `MOCK DATA` badge | Engine API unreachable from dashboard host | Confirm VPS IP is set correctly in dashboard config; engine health check passes on VPS itself |
| Kill switch armed unexpectedly | Risk threshold breach triggered auto-halt | Review `/risk-gate` response; check today's P&L vs 5% daily limit; do NOT disarm without understanding root cause |

---

## Rollback

The market scanner is read-only — it does not place orders and cannot be "rolled back." However, if a logging error caused incorrect entries in Notion:

1. Open Notion → Scan History DB → filter by today's date
2. Delete or correct the erroneous records manually
3. Re-run the scan to generate a clean entry

If the engine API returns unexpected data (mock data bleed, stale cache):
```bash
# Restart the API container (VPS)
docker compose restart api

# Or locally, Ctrl+C then:
uvicorn api:app --reload --port 8001
```

---

## Escalation

| Situation | Action | Contact |
|-----------|--------|---------|
| Drawdown hits 7% (alert zone) | Reduce all position sizes by 50%, increase min_score to 8.0, notify Mohammed | @ScoopyAI_bot Telegram |
| Drawdown hits 10% (hard stop) | Kill switch triggers — halt ALL trading, close all open positions, do not resume without manual review | Mohammed — review session required before reset |
| Engine down > 30 min | Scanner continues in Standalone Mode; escalate VPS issue to DigitalOcean support if infrastructure related | DigitalOcean SGP1 support; dashboard: https://cloud.digitalocean.com |
| Binance Testnet API returning errors | Check https://testnet.binancefuture.com status; rotate testnet API keys if 401/403 | Binance Testnet key regeneration |
| 3 consecutive losing days | Pause trading, run weekly review early, review regime accuracy and signal thresholds | Mohammed manual review |

---

## History

| Date | Run By | Notes |
|------|--------|-------|
| 2026-04-16 | Scoopy | Runbook created. VPS not yet provisioned — scanner operates in Standalone Mode until DigitalOcean Droplet is live. |

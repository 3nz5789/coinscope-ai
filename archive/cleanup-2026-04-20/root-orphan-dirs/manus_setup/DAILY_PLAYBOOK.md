# CoinScopeAI — Daily Operations Playbook
> How to run and manage the scanner every day for maximum value

---

## Morning Routine (5 minutes)

### 1. Start the engine
```bash
cd coinscope_trading_engine
uvicorn api:app --reload --port 8001
```
Leave this terminal running. The engine must be live for all Manus skills to work.

### 2. Open Manus → CoinScopeAI project

### 3. Say: **"Run full scan"**

Manus will automatically:
- Check engine health
- Scan all 8 pairs
- Get regime for top 3 signals
- Validate top signal against Risk Gate
- Size the position if gate clears
- Log all signals to Notion
- Send Telegram alert if any signal ≥ 8.0

**Total time: ~30 seconds.**

---

## During the Day — Key Phrases

| What you want | Say to Manus |
|--------------|-------------|
| Quick re-scan | "Scan the market" |
| Check if BTC is still bullish | "What regime is BTCUSDT in?" |
| Size up a trade | "Size my position on ETHUSDT LONG, score 8.2" |
| Check if you can trade | "Check risk gate" |
| Log a trade entry | "Log this trade: BTCUSDT LONG, entry 83500, stop 82173, target 86152, score 9.2" |
| Mark a trade closed | "Close my BTC trade at 86100, TP hit" |
| Check today's P&L | "How am I doing today?" |
| Get current stats | "Show my performance this week" |

---

## End of Day Routine (5 minutes)

### 1. Say: **"Weekly review"** (on Fridays) or **"Daily summary"**
Manus will compile win rate, P&L, best/worst trade, and regime breakdown.

### 2. Fill in the Weekly Performance Report template
Download from Google Drive → `02 - Trading Operations/04_Weekly_Performance_Report_Template.docx`

### 3. Stop the engine
In Terminal: `Ctrl + C`

---

## Signal Decision Framework

When Manus returns a scan, use this decision tree:

```
Signal received
│
├─ Score < 5.5? → SKIP (below threshold)
│
├─ Regime = Chop?
│   ├─ Score < 8.0 → SKIP
│   └─ Score ≥ 8.0 → PROCEED with 50% size
│
├─ Risk Gate BLOCKED? → STOP — no trade today
│
└─ Score ≥ 5.5, Gate CLEAR, Regime ≠ Chop
    ├─ Score 5.5–6.9 → Reduced size, confirm manually
    ├─ Score 7.0–8.9 → Standard size, proceed
    └─ Score ≥ 9.0   → Full size, high priority
```

---

## Weekly Review Checklist

Run every Friday or Sunday:

- [ ] Say "weekly review" to Manus — review full stats
- [ ] Win rate ≥ 55%? If not → raise min_score threshold
- [ ] Chop regime trades dragging down win rate? → Set Chop filter to require ≥ 8.0
- [ ] Any Risk Gate breakers triggered? → Review and reset if appropriate
- [ ] Notion Trade Journal up to date? → Check for any unclosed trades
- [ ] Performance Report filled in Google Drive?
- [ ] HMM regime accuracy acceptable? → Review regime vs outcome alignment

---

## Tuning the Scanner

If results aren't meeting targets, adjust these settings in your Manus conversation:

| Problem | Fix |
|---------|-----|
| Too many low-quality signals | "Set min score to 7.0" |
| Not enough signals | "Set min score to 5.0" |
| Too many Chop regime trades | "Only show signals in Bull or Bear regime" |
| Missing overnight moves | "Scan BTC and ETH on the 1H timeframe" |
| Win rate < 50% | Raise min_score, avoid Chop regime entirely |
| Drawdown approaching limit | "Check risk gate status" — reduce position sizes |

---

## Automation Schedule (Advanced)

If you configure Manus scheduled tasks, use these times (UTC):

| UTC Time | Local (UTC+3) | Action |
|----------|--------------|--------|
| 05:00 | 08:00 | Morning full scan + Telegram |
| 09:00 | 12:00 | Midday quick scan |
| 13:00 | 16:00 | Afternoon full scan + Telegram |
| 17:00 | 20:00 | Evening full scan + Telegram |
| 21:00 | 00:00 | Daily summary + Notion sync |

To set this up in Manus: **Project → Automations → Add Schedule → Paste trigger phrase**

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| "Engine offline" | Run `uvicorn api:app --reload --port 8001` in terminal |
| "No signals found" | Market may be choppy. Lower min_score to 5.0, check back in 15 min |
| "Notion sync failed — 401" | NOTION_TOKEN expired. Update in .env and restart engine |
| "Notion sync failed — 403" | Integration not invited to database. Open Notion → Share → Invite integration |
| Telegram alerts not arriving | Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env |
| Score always below 5.5 | Check engine data feed — CCXT connection to Binance testnet may be slow |
| HMM regime stuck on Chop | Regime model may need retraining. Run `retrain_scheduler.py` |

---

## What Good Performance Looks Like

After 30+ days of paper trading, target these benchmarks before considering live capital:

| Metric | Target |
|--------|--------|
| Win Rate | ≥ 55% |
| Average R:R | ≥ 1.5:1 |
| Max Drawdown | < 8% |
| Sharpe Ratio | ≥ 1.0 |
| Consecutive losses never triggering gate | Consistent risk management |
| Regime accuracy | Bull/Bear calls correct ≥ 65% of time |

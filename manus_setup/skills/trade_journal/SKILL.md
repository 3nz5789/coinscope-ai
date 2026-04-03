# Trade Journal Skill — CoinScopeAI
**Skill ID:** `coinscope.trade_journal`
**Version:** 1.0.0
**Platform:** Manus
**Category:** Record Keeping

---

## Overview

Logs trade entries and exits to the Notion Trade Journal database, and signals to the Notion Signal Log. Every trade the system identifies or the trader confirms is recorded automatically — zero manual Notion editing required.

---

## Trigger Phrases

- "Log this trade"
- "Journal my entry"
- "Record this"
- "Save the trade"
- "Show my recent trades"
- "What did I trade today?"
- "Show trade history"
- "Update exit on my BTC trade"
- "Mark trade as closed"
- "Log signal"

---

## Two Modes

### Mode A — Log New Entry
Triggered when trader confirms entering a trade.

### Mode B — Update Exit
Triggered when trader reports closing a trade.

---

## Execution Steps — Mode A (New Entry)

### Step 1 — Collect Fields
Gather from previous skill outputs or ask trader:

| Field | Source |
|-------|--------|
| Symbol | Scanner output |
| Direction | Scanner output |
| Entry Price | Ask trader or use current market price |
| Stop Loss | Position Sizer output |
| Take Profit | Position Sizer output |
| Signal Score | Scanner output |
| Regime | Regime Detector output |
| Timeframe | Scanner output |
| Position Size (USDT) | Position Sizer output |
| Leverage | Position Sizer output |
| Risk Amount (USDT) | Position Sizer output |
| R:R Ratio | Position Sizer output |

### Step 2 — Write to Notion Trade Journal
```
POST https://api.notion.com/v1/pages
Database ID: 28e29aaf-938e-81eb-8c91-d166a2246520
Auth: Bearer {NOTION_TOKEN}
```

Map all fields to Notion properties per `notion_simple_integration.py`.

### Step 3 — Write to Notion Signal Log
```
POST https://api.notion.com/v1/pages
Database ID: 86f896d1-0db7-4fe6-afde-8d2e8f5e3463
```

### Step 4 — Confirm

```
✅ TRADE LOGGED — Notion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pair:       BTCUSDT
Direction:  LONG
Entry:      $83,500
Stop:       $82,173
Target:     $86,152
Size:       $450 at 5×
Score:      9.2/12
Regime:     Bull 🟢

📓 Saved to Notion Trade Journal
📊 Signal logged to Signal Log
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Notion Page ID: {page_id}
(Keep this ID to log your exit)
```

---

## Execution Steps — Mode B (Update Exit)

### Step 1 — Collect Exit Fields
- Exit Price (ask trader)
- Exit Reason: TP Hit / SL Hit / Manual / Time Stop
- Actual P&L (calculate or ask)

### Step 2 — PATCH Notion Page
```
PATCH https://api.notion.com/v1/pages/{page_id}
```
Update: Exit Price, Exit Reason, P&L (USDT), P&L (%), Status → Closed, Duration

### Step 3 — Confirm

```
✅ EXIT LOGGED — Trade Closed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Exit Price:  $86,152
Exit Reason: TP Hit ✅
P&L:         +$13.24 (+2.94%)
Duration:    6h 22m
Status:      Closed — Notion updated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Show Recent Trades

When trader asks "show my recent trades" or "what did I trade today?":

```
GET http://localhost:8001/journal?limit=10
```

Display as a table:
```
📓 RECENT TRADES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# | DATE     | PAIR    | DIR   | SCORE | P&L     | STATUS
1 | Apr 3    | BTCUSDT | LONG  | 9.2   | +$13.24 | Closed ✅
2 | Apr 2    | ETHUSDT | SHORT | 7.1   | −$4.50  | Closed ❌
3 | Apr 2    | SOLUSDT | LONG  | 6.8   | Open    | Active 🔵
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Win Rate: 1/2 (50%) | Net P&L: +$8.74
```

---

## Important Rules

- Always log signals even if the trader does NOT take the trade — mark as `acted_on: false`
- Never overwrite a closed trade — create a new entry for re-entries
- If Notion API returns 401 → "Notion token expired or invalid. Check NOTION_TOKEN in .env"
- If Notion API returns 403 → "Integration not invited to database. Add the integration in Notion settings"

---

## Chaining

After logging a trade entry:
- Remind trader to log the exit when they close
- Store the Notion page ID so exit update is easy: "Say 'close my BTC trade' when done"

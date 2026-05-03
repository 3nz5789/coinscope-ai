---
name: daily-status
description: Pull a one-screen morning brief from the local Engine API. Combines /performance (24h PnL, win rate, sharpe), /risk-gate (current gate state, pass/halt), /journal (recent decisions and rejections), and /regime/{symbol} for the top tracked symbols. Use when the user says "daily status", "morning brief", "what's the engine doing", "PnL update", "how did we do overnight", or at the start of any operational session. Validation phase only — calls localhost:8001, no real-capital surfaces.
---

# Daily Status

Single skill that summarizes overnight engine activity into a 1-screen brief. The thing Scoopy should run every morning and any time the user asks "how's the engine doing?"

## Trigger phrases

- "daily status"
- "morning brief"
- "what's the engine doing"
- "PnL update"
- "how did we do overnight"
- "engine status"
- "give me the morning"

## What it does

Calls these Engine API endpoints (all on `http://localhost:8001`):

1. **`GET /performance`** — 24h PnL, win rate, average trade, Sharpe, drawdown
2. **`GET /risk-gate`** — current gate state (PASS / WARN / HALT), reason, last-flip timestamp
3. **`GET /journal?limit=20`** — last 20 journal entries (signals, gate decisions, fills, rejections)
4. **`GET /regime/BTCUSDT`** + **`GET /regime/ETHUSDT`** — current regime label + confidence for the top 2 symbols

Then synthesizes them into this brief format:

```
DAILY STATUS — <YYYY-MM-DD HH:MM> Asia/Amman
Validation phase active. Testnet only. No real capital.

━━ Performance (24h) ━━
PnL:           <%>
Win rate:      <%> over <N> trades
Avg trade:     <%>
Sharpe:        <value>
Drawdown:      <%>  / 10% ceiling

━━ Risk Gate ━━
State:         <PASS | WARN | HALT>
Last flip:     <UTC iso>
Reason:        <one line>

━━ Top symbols — current regime ━━
BTCUSDT:       <Trending | Mean-Reverting | Volatile | Quiet>  (conf <0.0-1.0>)
ETHUSDT:       <regime>  (conf <0.0-1.0>)

━━ Journal — last 20 ━━
<HH:MM>  <signal | gate | fill | reject>  <symbol>  <one-line>
... (compressed to 5 most-recent + summary of older)

━━ Heat ━━
Open positions: <N>/3
Total exposure: <%> / 80% cap

━━ Anything to flag ━━
- <inferences from above; e.g., "regime flipped to Volatile mid-session", "3 rejections in last 60min — trending toward kill-switch", "drawdown at 6% — close to daily-loss watch", "all green, nothing notable">
```

## When the engine is unreachable

If `curl http://localhost:8001/performance` errors or times out, **don't fabricate**. Report:

```
DAILY STATUS — <timestamp>
Engine API at localhost:8001 unreachable.
Cannot synthesize live metrics.

Possible causes:
- Engine not running on this machine
- Validation cohort paused
- localhost:8001 in use by another process
- Network / firewall

Suggested next step: check engine process with `ps aux | grep coinscope` or
inspect docker compose status.
```

This honors the anti-overclaim rule (never fabricate metrics).

## Implementation

A bash one-liner that hits each endpoint and pipes through `jq`. Save under `scripts/daily_status.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ENGINE="${ENGINE:-http://localhost:8001}"

echo "DAILY STATUS — $(date -Iseconds)"
echo "Validation phase active. Testnet only. No real capital."
echo ""

if ! curl -s --max-time 3 "$ENGINE/performance" >/dev/null; then
    echo "Engine API at $ENGINE unreachable. Cannot synthesize live metrics."
    exit 0
fi

echo "━━ Performance (24h) ━━"
curl -s "$ENGINE/performance" | jq -r '
    "PnL:        \(.pnl_24h_pct // "n/a")%",
    "Win rate:   \(.win_rate_pct // "n/a")% over \(.trade_count // "n/a") trades",
    "Avg trade:  \(.avg_trade_pct // "n/a")%",
    "Sharpe:     \(.sharpe // "n/a")",
    "Drawdown:   \(.drawdown_pct // "n/a")%  / 10% ceiling"
'

echo ""
echo "━━ Risk Gate ━━"
curl -s "$ENGINE/risk-gate" | jq -r '
    "State:      \(.state // "n/a")",
    "Last flip:  \(.last_flip_iso // "n/a")",
    "Reason:     \(.reason // "n/a")"
'

echo ""
echo "━━ Top symbols — current regime ━━"
for sym in BTCUSDT ETHUSDT; do
    curl -s "$ENGINE/regime/$sym" | jq -r --arg s "$sym" '"\($s):    \(.regime // "n/a")  (conf \(.confidence // "n/a"))"'
done

echo ""
echo "━━ Journal — last 20 ━━"
curl -s "$ENGINE/journal?limit=20" | jq -r '.entries[]? | "\(.ts // "?")  \(.kind // "?")  \(.symbol // "")  \(.summary // "")"' | head -10

echo ""
echo "━━ Heat ━━"
curl -s "$ENGINE/risk-gate" | jq -r '
    "Open positions: \(.open_positions // "n/a")/3",
    "Total exposure: \(.total_exposure_pct // "n/a")% / 80% cap"
'
```

(Save as `scripts/daily_status.sh`, `chmod +x`, run with `./scripts/daily_status.sh`.)

## Format expectations from the Engine API

The skill assumes these response shapes — adjust if the API evolves:

```json
// GET /performance
{
  "pnl_24h_pct": 0.42,
  "win_rate_pct": 64,
  "trade_count": 11,
  "avg_trade_pct": 0.04,
  "sharpe": 1.7,
  "drawdown_pct": 2.1
}

// GET /risk-gate
{
  "state": "PASS",
  "last_flip_iso": "2026-05-02T08:14:00Z",
  "reason": "...",
  "open_positions": 1,
  "total_exposure_pct": 22
}

// GET /journal
{
  "entries": [
    {"ts": "2026-05-02T08:14Z", "kind": "signal", "symbol": "BTCUSDT", "summary": "..."}
  ]
}

// GET /regime/BTCUSDT
{
  "regime": "Trending",
  "confidence": 0.72,
  "since": "2026-05-02T07:30Z"
}
```

If a key is missing, `jq` falls back to "n/a" — never inferred.

## Hard rules

1. **No fabrication.** If an endpoint returns nothing, say "n/a" — never guess.
2. **No real-capital surfaces.** Validation phase only. If any field would imply real capital (e.g., "USD balance"), skip it.
3. **Always include the disclaimer** ("Testnet only…") in the header.
4. **Pair every PnL number with the drawdown context.** A green PnL + climbing drawdown is still risky.

## See also

- `skills_src/kill-switch-protocol/SKILL.md` — when daily status reveals a halt-worthy condition, that's the next protocol.
- `skills_src/drift-detector/SKILL.md` — separate concern (doc consistency, not engine state).
- `docs/runbooks/daily-ops.md` — operational SOP companion.

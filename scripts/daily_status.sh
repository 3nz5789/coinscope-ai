#!/usr/bin/env bash
# Daily Status — pulls Engine API state into a 1-screen brief.
# Usage:
#   ./scripts/daily_status.sh
#   ENGINE=http://localhost:8002 ./scripts/daily_status.sh   # alt engine

set -euo pipefail
ENGINE="${ENGINE:-http://localhost:8001}"

echo "DAILY STATUS — $(date -Iseconds 2>/dev/null || date +%FT%T%z)"
echo "Validation phase active. Testnet only. No real capital."
echo ""

if ! curl -s --max-time 3 "$ENGINE/performance" >/dev/null 2>&1; then
    echo "Engine API at $ENGINE unreachable. Cannot synthesize live metrics."
    echo ""
    echo "Possible causes:"
    echo "  - Engine not running on this machine"
    echo "  - Validation cohort paused"
    echo "  - localhost:8001 in use by another process"
    echo "  - Network / firewall"
    echo ""
    echo "Try: pgrep -f coinscope_trading_engine  /  docker compose ps"
    exit 0
fi

echo "━━ Performance (24h) ━━"
curl -s "$ENGINE/performance" | jq -r '
    "PnL:        \(.pnl_24h_pct // "n/a")%",
    "Win rate:   \(.win_rate_pct // "n/a")% over \(.trade_count // "n/a") trades",
    "Avg trade:  \(.avg_trade_pct // "n/a")%",
    "Sharpe:     \(.sharpe // "n/a")",
    "Drawdown:   \(.drawdown_pct // "n/a")%  / 10% ceiling"
' 2>/dev/null || echo "  (response not JSON or jq missing)"

echo ""
echo "━━ Risk Gate ━━"
curl -s "$ENGINE/risk-gate" | jq -r '
    "State:      \(.state // "n/a")",
    "Last flip:  \(.last_flip_iso // "n/a")",
    "Reason:     \(.reason // "n/a")"
' 2>/dev/null || echo "  (response not JSON or jq missing)"

echo ""
echo "━━ Top symbols — current regime ━━"
for sym in BTCUSDT ETHUSDT; do
    curl -s "$ENGINE/regime/$sym" | jq -r --arg s "$sym" \
        '"\($s):    \(.regime // "n/a")  (conf \(.confidence // "n/a"))"' 2>/dev/null \
        || echo "  $sym: (unavailable)"
done

echo ""
echo "━━ Journal — last 10 ━━"
curl -s "$ENGINE/journal?limit=20" | jq -r '
    .entries[]? | "\(.ts // "?")  \(.kind // "?")  \(.symbol // "")  \(.summary // "")"
' 2>/dev/null | head -10 || echo "  (no entries or response not JSON)"

echo ""
echo "━━ Heat ━━"
curl -s "$ENGINE/risk-gate" | jq -r '
    "Open positions: \(.open_positions // "n/a")/3",
    "Total exposure: \(.total_exposure_pct // "n/a")% / 80% cap"
' 2>/dev/null || echo "  (response not JSON or jq missing)"

#!/bin/bash
# CoinScopeAI — Push WebSocket reconnect fix
# Double-click this file to run it in Terminal

set -e
cd "$(dirname "$0")"

REPO="$HOME/Documents/Claude/Projects/CoinScopeAI"
cd "$REPO"

echo "=== CoinScopeAI WS Fix Push ==="

# Remove stale git lock files (left over from a prior session)
rm -f .git/index.lock .git/HEAD.lock
echo "✓ Lock files cleared"

# Stage only the fixed file
git add coinscope_trading_engine/binance_websocket_client.py
echo "✓ Staged binance_websocket_client.py"

# Commit
git commit -m "[FIX] BINANCE — Missed Reconnect After WS Drop

Bugs fixed:
- No reconnect loop: connect() attempted only once; any WS drop killed the client silently.
- Ghost connected=True: flag never cleared after drop, causing all subsequent
  _send_raw_request calls to hang until timeout.
- No keepalive: websockets.connect() called without ping_interval; Binance drops
  connections silently after a missed pong (~10 min).
- Pending futures leaked: on disconnect, callers blocked forever waiting on
  futures that would never resolve.

Changes:
- Added start()/stop() with exponential-backoff reconnect loop (1s→60s, 50 attempts max).
- Added async context-manager (__aenter__/__aexit__) for one-shot usage.
- websockets.connect() now uses ping_interval=20, ping_timeout=10.
- _mark_disconnected() clears connected/authenticated flags and drains all
  pending_requests futures with ConnectionError so callers fail fast.
- Removed dead _message_handler/_ping_handler tasks; message dispatch now
  happens inline in _single_connect() via async-for loop."

echo "✓ Committed"

# Push
git push origin main
echo ""
echo "✅ Fix pushed to GitHub successfully!"
echo ""
read -p "Press Enter to close..."

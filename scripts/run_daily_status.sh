#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CoinScopeAI Daily Status Check — Cron Wrapper
# Runs at 05:00 UTC (08:00 UTC+3) every day.
# Loads environment from /home/ubuntu/coinscope.env, then executes the
# Python status check script with --log and --telegram flags.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/coinscope.env"
LOG_DIR="$PROJECT_DIR/logs"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Load environment variables from coinscope.env
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -v '^#' "$ENV_FILE" | grep -v '^$')
    set +a
else
    echo "[ERROR] Environment file not found: $ENV_FILE" >&2
    exit 1
fi

# Run the status check
exec python3 "$SCRIPT_DIR/daily_status_check.py" --log --telegram

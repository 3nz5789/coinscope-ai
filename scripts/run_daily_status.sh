#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CoinScopeAI Daily Status Check — Cron Wrapper
# Runs at 05:00 UTC (08:00 UTC+3) every day.
#
# Environment resolution (dual-source approach):
#   1. First checks if TELEGRAM_BOT_TOKEN is already set in the environment
#      (e.g., via Manus project secrets) and is not a placeholder.
#   2. If not set or is a placeholder, falls back to coinscope.env file.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/coinscope.env"
LOG_DIR="$PROJECT_DIR/logs"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Check if critical env vars are already set and valid (not placeholders)
_needs_env_file=false
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] || [[ "$TELEGRAM_BOT_TOKEN" == "your-telegram-bot-token-here" ]]; then
    _needs_env_file=true
fi
if [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
    _needs_env_file=true
fi

# Load from coinscope.env only if env vars are missing or placeholders
if [[ "$_needs_env_file" == "true" ]]; then
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source <(grep -v '^#' "$ENV_FILE" | grep -v '^$')
        set +a
        echo "[INFO] Loaded environment from $ENV_FILE"
    else
        echo "[ERROR] Environment file not found: $ENV_FILE" >&2
        echo "[ERROR] And TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in environment." >&2
        exit 1
    fi
else
    echo "[INFO] Using environment variables (Manus secrets)"
fi

# Run the status check
exec python3 "$SCRIPT_DIR/daily_status_check.py" --log --telegram

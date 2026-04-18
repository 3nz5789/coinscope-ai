"""
CoinScopeAI — Notion Sync Configuration
=========================================
Central config for all Notion database IDs and integration settings.
Import this wherever you need Notion IDs — do not hardcode them elsewhere.

Setup Instructions
------------------
1. Go to https://www.notion.so/my-integrations
2. Click "New integration" → name it "CoinScopeAI"
3. Copy the Integration Token (starts with "ntn_" or "secret_")
4. In your Notion workspace:
     - Open the Trade Journal database page → Share → Invite → CoinScopeAI
     - Open the Signal Log database page   → Share → Invite → CoinScopeAI
5. Set the environment variable:
     export NOTION_TOKEN="ntn_your_token_here"
   Or add to your .env file (never commit this file to git).

Environment Variables
---------------------
  NOTION_TOKEN          Required. Your Notion integration token.
  NOTION_EXPORT_INTERVAL  Optional. Seconds between auto-exports (default: 3600).
  NOTION_DRY_RUN        Optional. Set to "1" to log without writing to Notion.
"""

import os

# ── Database IDs ──────────────────────────────────────────────────────────────
# These match your live Notion workspace (CoinScopeAI teamspace).

TRADE_JOURNAL_DB_ID = "1430e3fb-d21b-49e7-b260-9dfa4adcb5f0"
"""
Trade Journal database (rebuilt 2026-04-04).
Fields: Trade (title), Pair, Direction, Status, Signal Score, Conviction,
        Regime at Entry, MTF at Entry, Entry Price, Entry Time, Stop Loss,
        Take Profit 1, Take Profit 2, Exit Price, Exit Time, Size USDT,
        Leverage, Kelly Pct Used, RR Planned, RR Actual, PnL USDT, PnL Pct,
        Mistakes (multi-select), Lessons
"""

SIGNAL_LOG_DB_ID = "ed9457ff-78f7-4008-bc28-ef3046506039"
"""
Signal Log database (rebuilt 2026-04-04).
Fields: Signal (title), Pair, Direction, Score (0-12), Strength Label,
        Regime, MTF Confirmed, RSI, Timeframe, Price at Signal,
        Scan Timestamp, Status, Funding Rate, Funding Warning,
        OI Change 1h, Sub-scores, Engine Mode, Notes
"""

SCAN_HISTORY_DB_ID = "c008175e-cfc0-4553-ab37-c47c3825f2e3"
"""
Scan History database (new 2026-04-04).
Fields: Scan ID (title), Scan Timestamp, Pairs Scanned, Signals Found,
        Min Score Used, Avg Score, Top Signal, Top Score, BTC Regime,
        BTC Price, Market Regime, Engine Mode, Notes
"""

PAIR_INTELLIGENCE_DB_ID = "21108fd0-1471-4184-bf86-1e64c662548b"
"""
Pair Intelligence database.
Read-only reference table for pair profiles.
Updated manually or via pair_monitor.py stats.
"""

# ── Page IDs ──────────────────────────────────────────────────────────────────

WORKSPACE_ROOT_PAGE_ID = "33829aaf-938e-8178-8a41-c00d3cac2d41"
"""Root 🤖 CoinScopeAI hub page (rebuilt 2026-04-04)."""

ENGINE_STATUS_PAGE_ID = "33829aaf-938e-81fb-b2ca-ec7e62587680"
"""🏥 Engine Status page — health check log and testnet run log."""

ENGINE_CONFIG_PAGE_ID = "33829aaf-938e-816b-9a82-fb5c221559cb"
"""Legacy Engine Config page (archived). Kept for backward compatibility."""

WORKSPACE_HUB_PAGE_ID = "33829aaf-938e-8178-8a41-c00d3cac2d41"
"""Alias for WORKSPACE_ROOT_PAGE_ID."""

# ── Runtime Settings ──────────────────────────────────────────────────────────

NOTION_TOKEN: str = os.environ.get("NOTION_TOKEN", "")

EXPORT_INTERVAL: int = int(os.environ.get("NOTION_EXPORT_INTERVAL", "3600"))
"""Seconds between automatic Notion exports in run_loop_with_notion(). Default: 1 hour."""

DRY_RUN: bool = os.environ.get("NOTION_DRY_RUN", "0") == "1"
"""If True, log what would be written but do not make any API calls."""

# ── Notion API ────────────────────────────────────────────────────────────────

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL    = "https://api.notion.com/v1"

# ── Field Mapping Reference ───────────────────────────────────────────────────
# Maps engine field names → Notion property names.
# Used by notion_simple_integration.py for documentation and validation.

TRADE_FIELD_MAP = {
    # engine field          : Notion property name (Trade Journal v2 — 2026-04-04)
    "symbol"                : "Pair",
    "side"                  : "Direction",
    "status"                : "Status",
    "signal_score"          : "Signal Score",
    "conviction"            : "Conviction",
    "regime"                : "Regime at Entry",
    "mtf_confirmed"         : "MTF at Entry",
    "entry_price"           : "Entry Price",
    "opened_at"             : "Entry Time",
    "stop_loss"             : "Stop Loss",
    "take_profit"           : "Take Profit 1",
    "take_profit_2"         : "Take Profit 2",
    "exit_price"            : "Exit Price",
    "closed_at"             : "Exit Time",
    "quantity"              : "Size USDT",
    "leverage"              : "Leverage",
    "kelly_pct"             : "Kelly Pct Used",
    "rr_planned"            : "RR Planned",
    "rr_actual"             : "RR Actual",
    "pnl_usdt"              : "PnL USDT",
    "pnl_pct"               : "PnL Pct",
    "mistakes"              : "Mistakes",
    "notes"                 : "Lessons",
}

SIGNAL_FIELD_MAP = {
    # engine field          : Notion property name (Signal Log v2 — 2026-04-04)
    "symbol"                : "Pair",
    "signal"                : "Direction",
    "score"                 : "Score (0-12)",
    "strength_label"        : "Strength Label",
    "regime"                : "Regime",
    "mtf_confirmed"         : "MTF Confirmed",
    "rsi"                   : "RSI",
    "timeframe"             : "Timeframe",
    "price"                 : "Price at Signal",
    "timestamp"             : "Scan Timestamp",
    "status"                : "Status",
    "funding_rate"          : "Funding Rate",
    "funding_warning"       : "Funding Warning",
    "oi_change_1h"          : "OI Change 1h",
    "sub_scores"            : "Sub-scores",
    "engine_mode"           : "Engine Mode",
    "notes"                 : "Notes",
}

SCAN_HISTORY_FIELD_MAP = {
    # engine field          : Notion property name (Scan History v1 — 2026-04-04)
    "scan_id"               : "Scan ID",
    "timestamp"             : "Scan Timestamp",
    "pairs_scanned"         : "Pairs Scanned",
    "signals_found"         : "Signals Found",
    "min_score"             : "Min Score Used",
    "avg_score"             : "Avg Score",
    "top_signal"            : "Top Signal",
    "top_score"             : "Top Score",
    "btc_regime"            : "BTC Regime",
    "btc_price"             : "BTC Price",
    "market_regime"         : "Market Regime",
    "engine_mode"           : "Engine Mode",
    "notes"                 : "Notes",
}

# ── Select Option Values (for validation) ─────────────────────────────────────

DIRECTION_OPTIONS   = {"LONG", "SHORT"}
REGIME_OPTIONS      = {"Bull", "Bear", "Chop"}
TIMEFRAME_OPTIONS   = {"1m", "5m", "15m", "1h", "4h", "1d"}
SIGNAL_OPTIONS      = {"LONG", "SHORT", "NEUTRAL"}
EXIT_REASON_OPTIONS = {"TP Hit", "SL Hit", "Manual Close", "Time Stop", "Regime Change"}
ACTED_ON_OPTIONS    = {"Yes — Entered", "No — Skipped", "Watching"}
SOURCE_OPTIONS      = {"Scanner", "Manual", "Whale Alert", "Funding Rate"}
SKIP_OPTIONS        = {"Score Too Low", "Chop Regime", "Risk Gate Blocked", "Manual Decision"}


def validate_config() -> bool:
    """Check that required env vars are set and print a status report."""
    ok = True
    print("\n── CoinScopeAI Notion Sync Config ──────────────────────────")
    print(f"  NOTION_TOKEN        : {'✅ set' if NOTION_TOKEN else '❌ NOT SET'}")
    print(f"  EXPORT_INTERVAL     : {EXPORT_INTERVAL}s ({EXPORT_INTERVAL // 60} min)")
    print(f"  DRY_RUN             : {'⚠️  YES — no writes' if DRY_RUN else 'No'}")
    print(f"  Trade Journal DB    : {TRADE_JOURNAL_DB_ID}")
    print(f"  Signal Log DB       : {SIGNAL_LOG_DB_ID}")
    print(f"  Pair Intelligence DB: {PAIR_INTELLIGENCE_DB_ID}")
    print("────────────────────────────────────────────────────────────\n")
    if not NOTION_TOKEN:
        print("  ⚠️  Set NOTION_TOKEN to enable Notion sync:")
        print("      export NOTION_TOKEN='ntn_your_token_here'\n")
        ok = False
    return ok


if __name__ == "__main__":
    validate_config()

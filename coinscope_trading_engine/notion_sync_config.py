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

TRADE_JOURNAL_DB_ID = "28e29aaf-938e-81eb-8c91-d166a2246520"
"""
Crypto Trading Journal database.
Fields: Crypto Pair, Date of Trade, Direction, Entry/Exit Prices,
        Quantity, Signal Score, Regime, Stop Loss, Take Profit,
        R:R Ratio, Signal Source, Exit Reason, Funding Rate %,
        Leverage, Trade Notes, Mistakes/Notes, Profit/Loss (formula)
"""

SIGNAL_LOG_DB_ID = "86f896d1-0db7-4fe6-afde-8d2e8f5e3463"
"""
Signal Log database.
Fields: Signal ID (auto), Pair, Signal, Total Score,
        Momentum/Trend/Volatility/Volume/Entry/Liquidity scores,
        RSI, ATR %, Regime, Regime Confidence %, Timeframe,
        Funding Rate %, Scanned At, Acted On, Skip Reason, Notes
"""

PAIR_INTELLIGENCE_DB_ID = "21108fd0-1471-4184-bf86-1e64c662548b"
"""
Pair Intelligence database.
Read-only reference table for pair profiles.
Updated manually or via pair_monitor.py stats.
"""

# ── Page IDs ──────────────────────────────────────────────────────────────────

ENGINE_CONFIG_PAGE_ID = "33629aaf-938e-816b-9a82-fb5c221559cb"
"""
Engine Config & Knowledge Base page.
Used as anchor for performance snapshot comments.
"""

WORKSPACE_HUB_PAGE_ID = "ec28f4e4-214b-49b3-831f-5f63925d62d2"
"""
CoinScopeAI workspace databases hub page.
"""

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
    # engine field          : Notion property name
    "symbol"                : "Crypto Pair",
    "opened_at"             : "Date of Trade",
    "side"                  : "Direction",
    "entry_price"           : "Entry Prices",
    "exit_price"            : "Exit Prices",
    "quantity"              : "Quantity",
    "signal_score"          : "Signal Score",
    "regime"                : "Regime",
    "timeframe"             : "Timeframe",
    "stop_loss"             : "Stop Loss",
    "take_profit"           : "Take Profit",
    "leverage"              : "Leverage",
    "rr_ratio"              : "R:R Ratio",
    "funding_rate"          : "Funding Rate %",
    "signal_source"         : "Signal Source",
    "status"                : "Exit Reason",
    "trade_notes"           : "Trade Notes",
    "mistakes"              : "Mistakes / Notes",
}

SIGNAL_FIELD_MAP = {
    # engine field          : Notion property name
    "symbol"                : "Pair",
    "signal"                : "Signal",
    "score"                 : "Total Score",
    "sub_scores.momentum"   : "Momentum Score",
    "sub_scores.trend"      : "Trend Score",
    "sub_scores.volatility" : "Volatility Score",
    "sub_scores.volume"     : "Volume Score",
    "sub_scores.entry"      : "Entry Score",
    "sub_scores.liquidity"  : "Liquidity Score",
    "rsi"                   : "RSI",
    "atr_pct"               : "ATR %",
    "regime"                : "Regime",
    "confidence"            : "Regime Confidence %",
    "timeframe"             : "Timeframe",
    "funding_rate"          : "Funding Rate %",
    "timestamp"             : "Scanned At",
    "acted_on"              : "Acted On",
    "skip_reason"           : "Skip Reason",
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

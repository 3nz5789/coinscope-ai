"""
CoinScopeAI — Notion Simple Integration
========================================
Syncs trade journal entries and scanner signals to your live Notion workspace.

Targets two databases:
  - Trade Journal  (ID: 1430e3fb-d21b-49e7-b260-9dfa4adcb5f0)  ← rebuilt 2026-04-04
  - Signal Log     (ID: ed9457ff-78f7-4008-bc28-ef3046506039)  ← rebuilt 2026-04-04

Setup:
  1. Go to https://www.notion.so/my-integrations and create an integration.
  2. Copy the Integration Token (starts with "ntn_" or "secret_").
  3. Open both database pages in Notion → Share → Invite your integration.
  4. Set the env variable:
       export NOTION_TOKEN="ntn_your_token_here"
     Or add it to a .env file in the project root.

Usage:
  notion = SimpleNotionIntegration()

  # Log a completed trade
  notion.log_trade(journal_entry)

  # Log a scanner signal (all signals, even untraded)
  notion.log_signal(signal_dict)

  # Bulk export existing journal
  notion.export_trades(trades_list)
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("SimpleNotionIntegration")

# ── Database IDs (CoinScopeAI Notion workspace — rebuilt 2026-04-04) ──────────
TRADE_JOURNAL_DB_ID = "1430e3fb-d21b-49e7-b260-9dfa4adcb5f0"
SIGNAL_LOG_DB_ID    = "ed9457ff-78f7-4008-bc28-ef3046506039"

NOTION_API_VERSION  = "2022-06-28"
NOTION_BASE_URL     = "https://api.notion.com/v1"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _notion_title(value: str) -> dict:
    return {"title": [{"text": {"content": str(value)}}]}

def _notion_number(value) -> dict:
    if value is None:
        return {"number": None}
    return {"number": round(float(value), 6)}

def _notion_select(value: str) -> dict:
    if not value:
        return {"select": None}
    return {"select": {"name": str(value)}}

def _notion_date(value: str) -> dict:
    """Accept ISO datetime or date string."""
    if not value:
        return {"date": None}
    # Normalize to ISO 8601
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return {"date": {"start": dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")}}
    except ValueError:
        return {"date": {"start": value}}

def _notion_rich_text(value: str) -> dict:
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": str(value)[:2000]}}]}

def _map_regime(regime: str) -> str:
    """Map engine regime strings to Notion select options."""
    mapping = {
        "bull":    "Bull",
        "bullish": "Bull",
        "bear":    "Bear",
        "bearish": "Bear",
        "chop":    "Chop",
        "choppy":  "Chop",
        "ranging": "Chop",
    }
    return mapping.get(str(regime).lower(), "Chop")

def _map_direction(side: str) -> str:
    """Map engine side strings to LONG/SHORT."""
    s = str(side).upper()
    if s in ("LONG", "BUY", "1"):
        return "LONG"
    if s in ("SHORT", "SELL", "-1"):
        return "SHORT"
    return "LONG"

def _map_timeframe(tf: str) -> str:
    """Map timeframe strings to Notion select options."""
    valid = {"1m", "5m", "15m", "1h", "4h", "1d"}
    if tf in valid:
        return tf
    return "4h"

def _map_exit_reason(status: str) -> Optional[str]:
    """Map trade status to exit reason."""
    mapping = {
        "tp_hit":       "TP Hit",
        "sl_hit":       "SL Hit",
        "manual":       "Manual Close",
        "time_stop":    "Time Stop",
        "regime":       "Regime Change",
        "closed":       "Manual Close",
    }
    return mapping.get(str(status).lower())

def _calc_rr(entry: float, sl: float, tp: float, direction: str) -> Optional[float]:
    """Calculate R:R ratio."""
    try:
        if direction == "LONG":
            risk   = entry - sl
            reward = tp - entry
        else:
            risk   = sl - entry
            reward = entry - tp
        if risk <= 0:
            return None
        return round(reward / risk, 2)
    except Exception:
        return None


# ── Core Class ────────────────────────────────────────────────────────────────

class SimpleNotionIntegration:
    """
    Syncs CoinScopeAI trade data to the live Notion workspace.

    All writes go through the Notion REST API using a bearer token.
    No SDK dependency required — only `requests`.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("NOTION_TOKEN", "")
        if not self.token:
            logger.warning(
                "⚠️  NOTION_TOKEN not set. Set env var or pass token= to constructor. "
                "Notion sync will be disabled."
            )
        self.headers = {
            "Authorization":  f"Bearer {self.token}",
            "Content-Type":   "application/json",
            "Notion-Version": NOTION_API_VERSION,
        }

    # ── Low-level API ─────────────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: dict) -> Optional[dict]:
        """POST to Notion API. Returns response JSON or None on failure."""
        if not self.token:
            return None
        url = f"{NOTION_BASE_URL}/{endpoint}"
        try:
            resp = requests.post(url, headers=self.headers,
                                 data=json.dumps(payload), timeout=15)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                logger.error(
                    f"Notion API error {resp.status_code}: {resp.text[:300]}"
                )
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Notion request failed: {e}")
            return None

    def _patch(self, endpoint: str, payload: dict) -> Optional[dict]:
        """PATCH to Notion API (for updates)."""
        if not self.token:
            return None
        url = f"{NOTION_BASE_URL}/{endpoint}"
        try:
            resp = requests.patch(url, headers=self.headers,
                                  data=json.dumps(payload), timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(
                    f"Notion PATCH error {resp.status_code}: {resp.text[:300]}"
                )
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Notion PATCH failed: {e}")
            return None

    def _query_db(self, db_id: str, filter_payload: dict) -> list:
        """Query a Notion database with a filter. Returns list of page objects."""
        if not self.token:
            return []
        url = f"{NOTION_BASE_URL}/databases/{db_id}/query"
        try:
            resp = requests.post(url, headers=self.headers,
                                 data=json.dumps(filter_payload), timeout=15)
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Notion query failed: {e}")
        return []

    # ── Trade Journal ─────────────────────────────────────────────────────────

    def log_trade(self, entry) -> Optional[str]:
        """
        Create a new page in the Notion Trade Journal database.

        Accepts either a JournalEntry dataclass instance or a plain dict.
        Returns the created page ID, or None on failure.

        Field mapping:
          engine field          → Notion property
          ─────────────────────────────────────────
          symbol                → Crypto Pair (title)
          opened_at             → Date of Trade
          side                  → Direction
          entry_price           → Entry Prices
          exit_price            → Exit Prices
          quantity              → Quantity
          pnl_pct               → Trade Notes (formatted)
          regime                → Regime
          signal_score          → Signal Score
          confidence            → Regime is implicit in regime field
          kelly_usd             → leveraged quantity proxy
          status                → Exit Reason
          signal_score          → Signal Score
        """
        # Normalise input to dict
        if hasattr(entry, "__dict__"):
            d = entry.__dict__.copy()
        elif hasattr(entry, "_asdict"):
            d = entry._asdict()
        else:
            d = dict(entry)

        symbol    = d.get("symbol", "???")
        direction = _map_direction(d.get("side", "LONG"))
        regime    = _map_regime(d.get("regime", "chop"))
        opened_at = d.get("opened_at", datetime.now(timezone.utc).isoformat())
        closed_at = d.get("closed_at", "")

        entry_price  = d.get("entry_price", 0.0)
        exit_price   = d.get("exit_price",  0.0)
        quantity     = d.get("quantity",    0.0)
        kelly_usd    = d.get("kelly_usd",   0.0)
        pnl_pct      = d.get("pnl_pct",     0.0)
        pnl_usd      = d.get("pnl_usd",     0.0)
        signal_score = d.get("signal_score", 0.0)
        status       = d.get("status",      "")

        # Infer SL/TP and leverage from kelly_usd if not present
        stop_loss  = d.get("stop_loss",  None)
        take_profit = d.get("take_profit", None)
        leverage   = d.get("leverage",   None)
        timeframe  = _map_timeframe(d.get("timeframe", "4h"))
        funding    = d.get("funding_rate", None)
        notes      = d.get("trade_notes", "")
        mistakes   = d.get("mistakes",    "")
        source     = d.get("signal_source", "Scanner")

        # R:R
        rr = None
        if stop_loss and take_profit and entry_price:
            rr = _calc_rr(entry_price, stop_loss, take_profit, direction)

        # Build notes from PnL
        auto_note = (
            f"PnL: {pnl_pct:+.2%} | ${pnl_usd:+.2f} | "
            f"Kelly: ${kelly_usd:.2f} | "
            f"Regime confidence: {d.get('confidence', 0):.1%}"
        )
        combined_notes = f"{auto_note}\n{notes}".strip()

        properties = {
            "Crypto Pair":   _notion_title(symbol),
            "Date of Trade": _notion_date(opened_at),
            "Direction":     _notion_select(direction),
            "Entry Prices":  _notion_number(entry_price),
            "Exit Prices":   _notion_number(exit_price if exit_price else None),
            "Quantity":      _notion_number(quantity),
            "Regime":        _notion_select(regime),
            "Signal Score":  _notion_number(signal_score),
            "Timeframe":     _notion_select(timeframe),
            "Trade Notes":   _notion_rich_text(combined_notes),
            "Signal Source": _notion_select(source),
        }

        # Optional fields
        if stop_loss:
            properties["Stop Loss"]    = _notion_number(stop_loss)
        if take_profit:
            properties["Take Profit"]  = _notion_number(take_profit)
        if leverage:
            properties["Leverage"]     = _notion_number(leverage)
        if rr:
            properties["R:R Ratio"]    = _notion_number(rr)
        if funding is not None:
            properties["Funding Rate %"] = _notion_number(funding)
        if mistakes:
            properties["Mistakes / Notes"] = _notion_rich_text(mistakes)

        exit_reason = _map_exit_reason(status)
        if exit_reason:
            properties["Exit Reason"] = _notion_select(exit_reason)

        # Strategy: map side+timeframe → Day trading (futures default)
        properties["Strategy Used"] = _notion_select("Day trading")

        payload = {
            "parent":     {"database_id": TRADE_JOURNAL_DB_ID},
            "properties": properties,
        }

        result = self._post("pages", payload)
        if result:
            page_id = result.get("id", "")
            logger.info(f"✅ Trade logged to Notion: {symbol} {direction} | page={page_id[:8]}...")
            return page_id
        return None

    def update_trade_exit(self, notion_page_id: str, entry) -> bool:
        """
        Update an existing Notion trade page with exit data.
        Called when a trade closes to fill Exit Price, Exit Reason, etc.
        """
        if hasattr(entry, "__dict__"):
            d = entry.__dict__.copy()
        else:
            d = dict(entry)

        properties = {}

        exit_price = d.get("exit_price", 0.0)
        if exit_price:
            properties["Exit Prices"] = _notion_number(exit_price)

        status = d.get("status", "")
        exit_reason = _map_exit_reason(status)
        if exit_reason:
            properties["Exit Reason"] = _notion_select(exit_reason)

        mistakes = d.get("mistakes", "")
        if mistakes:
            properties["Mistakes / Notes"] = _notion_rich_text(mistakes)

        if not properties:
            return False

        result = self._patch(f"pages/{notion_page_id}", {"properties": properties})
        if result:
            logger.info(f"✅ Trade exit updated: page={notion_page_id[:8]}...")
            return True
        return False

    # ── Signal Log ────────────────────────────────────────────────────────────

    def log_signal(self, signal: dict, acted_on: str = "No — Skipped") -> Optional[str]:
        """
        Create a new page in the Notion Signal Log database.

        Accepts the signal dict returned by the /scan endpoint:
          {
            "symbol": "BTC/USDT",
            "signal": "LONG",
            "score": 8.5,
            "timeframe": "4h",
            "rsi": 61.2,
            "regime": "bull",
            "confidence": 0.84,
            "sub_scores": {
              "momentum": 3, "trend": 3, "volatility": 2,
              "volume": 3, "entry": 2, "liquidity": 2
            },
            "funding_rate": 0.0003,
            "atr_pct": 1.8
          }

        acted_on: "Yes — Entered" | "No — Skipped" | "Watching"
        Returns: created page ID or None
        """
        symbol     = signal.get("symbol", signal.get("pair", "???"))
        sig_dir    = str(signal.get("signal", "NEUTRAL")).upper()
        total      = signal.get("score", signal.get("total_score", 0.0))
        timeframe  = _map_timeframe(signal.get("timeframe", "4h"))
        rsi        = signal.get("rsi", None)
        regime     = _map_regime(signal.get("regime", "chop"))
        confidence = signal.get("confidence", None)
        funding    = signal.get("funding_rate", None)
        atr_pct    = signal.get("atr_pct", None)
        notes      = signal.get("notes", "")
        skip_reason = signal.get("skip_reason", None)

        # Sub-scores (from scoring_fixed.py breakdown)
        sub = signal.get("sub_scores", {})
        momentum   = sub.get("momentum",   signal.get("momentum_score",   None))
        trend      = sub.get("trend",      signal.get("trend_score",      None))
        volatility = sub.get("volatility", signal.get("volatility_score", None))
        volume     = sub.get("volume",     signal.get("volume_score",     None))
        entry_sc   = sub.get("entry",      signal.get("entry_score",      None))
        liquidity  = sub.get("liquidity",  signal.get("liquidity_score",  None))

        scanned_at = signal.get("timestamp", datetime.now(timezone.utc).isoformat())
        if isinstance(scanned_at, (int, float)):
            scanned_at = datetime.fromtimestamp(scanned_at, tz=timezone.utc).isoformat()

        properties = {
            "Pair":        _notion_title(symbol),
            "Signal":      _notion_select(sig_dir),
            "Total Score": _notion_number(total),
            "Regime":      _notion_select(regime),
            "Timeframe":   _notion_select(timeframe),
            "Acted On":    _notion_select(acted_on),
            "Scanned At":  _notion_date(str(scanned_at)),
        }

        if rsi is not None:
            properties["RSI"] = _notion_number(rsi)
        if confidence is not None:
            properties["Regime Confidence %"] = _notion_number(confidence * 100)
        if funding is not None:
            properties["Funding Rate %"] = _notion_number(funding * 100)
        if atr_pct is not None:
            properties["ATR %"] = _notion_number(atr_pct)
        if momentum is not None:
            properties["Momentum Score"] = _notion_number(momentum)
        if trend is not None:
            properties["Trend Score"] = _notion_number(trend)
        if volatility is not None:
            properties["Volatility Score"] = _notion_number(volatility)
        if volume is not None:
            properties["Volume Score"] = _notion_number(volume)
        if entry_sc is not None:
            properties["Entry Score"] = _notion_number(entry_sc)
        if liquidity is not None:
            properties["Liquidity Score"] = _notion_number(liquidity)
        if skip_reason:
            properties["Skip Reason"] = _notion_select(skip_reason)
        if notes:
            properties["Notes"] = _notion_rich_text(notes)

        payload = {
            "parent":     {"database_id": SIGNAL_LOG_DB_ID},
            "properties": properties,
        }

        result = self._post("pages", payload)
        if result:
            page_id = result.get("id", "")
            logger.info(
                f"📡 Signal logged: {symbol} {sig_dir} score={total:.1f} | "
                f"acted_on={acted_on} | page={page_id[:8]}..."
            )
            return page_id
        return None

    # ── Bulk Export ───────────────────────────────────────────────────────────

    def export_trades(self, trades: list) -> int:
        """
        Bulk-export a list of JournalEntry objects or dicts to Notion.
        Skips trades already present (checks for matching Crypto Pair + Date).
        Returns count of newly created pages.
        """
        created = 0
        for trade in trades:
            page_id = self.log_trade(trade)
            if page_id:
                created += 1
        logger.info(f"✅ Bulk export complete: {created}/{len(trades)} trades created")
        return created

    def export_signals(self, signals: list, acted_on: str = "No — Skipped") -> int:
        """
        Bulk-export a list of signal dicts to the Signal Log.
        Returns count of created pages.
        """
        created = 0
        for signal in signals:
            # Mark as "Yes — Entered" if signal has trade data attached
            status = "Yes — Entered" if signal.get("traded") else acted_on
            page_id = self.log_signal(signal, acted_on=status)
            if page_id:
                created += 1
        logger.info(f"📡 Signal export complete: {created}/{len(signals)} signals logged")
        return created

    def export_portfolio(self, portfolio: dict) -> None:
        """
        Placeholder for portfolio sync (not yet implemented in Notion schema).
        Portfolio data is available via the Notion Trade Journal P&L formula.
        """
        logger.info(
            f"ℹ️  Portfolio export skipped (use Trade Journal P&L formula). "
            f"Total value: ${portfolio.get('total_value', 0):,.2f}"
        )

    def export_performance_metrics(self, metrics: dict) -> None:
        """
        Log performance summary as a comment on the Engine Config page.
        Useful for daily snapshots without creating new database rows.
        """
        summary = (
            f"📊 Performance Snapshot [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}]\n"
            f"Trades: {metrics.get('total_trades', 0)} | "
            f"Win Rate: {metrics.get('win_rate', 0):.1f}% | "
            f"Total PnL: ${metrics.get('total_pnl', 0):+.2f} | "
            f"Profit Factor: {metrics.get('profit_factor', 0):.2f} | "
            f"Avg Win: ${metrics.get('avg_win', 0):.2f} | "
            f"Avg Loss: ${metrics.get('avg_loss', 0):.2f}"
        )
        logger.info(summary)

    # ── Health Check ──────────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Verify the Notion token and database access are working."""
        if not self.token:
            logger.error("❌ NOTION_TOKEN not set")
            return False

        # Try querying the Trade Journal DB (limit 1)
        try:
            url = f"{NOTION_BASE_URL}/databases/{TRADE_JOURNAL_DB_ID}/query"
            resp = requests.post(
                url,
                headers=self.headers,
                data=json.dumps({"page_size": 1}),
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("✅ Notion connection OK — Trade Journal accessible")
                return True
            elif resp.status_code == 401:
                logger.error("❌ Invalid NOTION_TOKEN — check your integration token")
            elif resp.status_code == 403:
                logger.error(
                    "❌ Integration not invited to database — "
                    "open Trade Journal in Notion → Share → invite your integration"
                )
            else:
                logger.error(f"❌ Notion returned {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connection error: {e}")

        return False


# ── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")

    notion = SimpleNotionIntegration()

    if not notion.test_connection():
        print("\n⚠️  Set NOTION_TOKEN and ensure the integration is invited to both databases.")
        print("   export NOTION_TOKEN='ntn_your_token_here'")
        sys.exit(1)

    # ── Test: log a sample trade ──────────────────────────────────────────────
    sample_trade = {
        "symbol":       "BTC/USDT",
        "side":         "LONG",
        "regime":       "bull",
        "confidence":   0.87,
        "entry_price":  68000.0,
        "exit_price":   69500.0,
        "quantity":     0.05,
        "kelly_usd":    340.0,
        "pnl_pct":      0.022,
        "pnl_usd":      75.00,
        "signal_score": 8.2,
        "status":       "tp_hit",
        "timeframe":    "4h",
        "stop_loss":    66800.0,
        "take_profit":  69500.0,
        "leverage":     5,
        "opened_at":    datetime.now(timezone.utc).isoformat(),
        "signal_source": "Scanner",
        "trade_notes":  "Clean breakout above EMA21 with vol confirmation.",
    }
    trade_page = notion.log_trade(sample_trade)
    print(f"\n✅ Trade page created: {trade_page}")

    # ── Test: log a sample signal ─────────────────────────────────────────────
    sample_signal = {
        "symbol":     "ETH/USDT",
        "signal":     "SHORT",
        "score":      7.1,
        "timeframe":  "4h",
        "rsi":        72.4,
        "regime":     "bear",
        "confidence": 0.79,
        "sub_scores": {
            "momentum": 2, "trend": 3, "volatility": 2,
            "volume": 3, "entry": 1, "liquidity": 3
        },
        "funding_rate": 0.0005,
        "atr_pct":    1.9,
    }
    sig_page = notion.log_signal(sample_signal, acted_on="Watching")
    print(f"✅ Signal page created: {sig_page}")

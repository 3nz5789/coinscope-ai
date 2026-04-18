"""
main.py — CoinScopeAI Funding Rate Ingestion Pipeline — Entry Point

Run:
    cd /path/to/CoinScopeAI
    python -m data.funding_rates.main

    # Or standalone:
    python data/funding_rates/main.py

What it does:
  1. Loads config from .env (testnet guard active by default)
  2. Initialises SQLite DB (creates tables if missing)
  3. Starts WebSocket stream for all perpetual futures mark prices
  4. REST-bootstraps on startup and re-syncs every 5 min
  5. Persists live rates + hourly snapshots to SQLite
  6. Fires Telegram alerts on extreme funding rates
  7. Logs a summary table every 10 minutes

Press Ctrl+C to stop cleanly.
"""

import asyncio
import logging
import signal
import sys
import time
from pathlib import Path

# ── Add project root to path (handles both `python main.py` and module invocation) ──
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from data.funding_rates.config import load_config
from data.funding_rates.storage import FundingRateDB
from data.funding_rates.collector import FundingRateCollector
from data.funding_rates.alerts import FundingRateAlertManager, format_funding_table

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("coinscope.funding")

# Quieten noisy libs
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


# ── Summary Printer ───────────────────────────────────────────────────────────

SUMMARY_INTERVAL = 600  # Print funding rate summary every 10 minutes


async def _summary_loop(db: FundingRateDB, collector: FundingRateCollector) -> None:
    """Periodic console digest showing the market's funding rate landscape."""
    await asyncio.sleep(30)  # Wait for initial data to arrive
    while True:
        try:
            records = db.get_all_live()
            if records:
                stats = db.summary()
                table = format_funding_table(records, top_n=10)

                log.info(
                    "[Summary] %d symbols tracked | WS reconnects: %d | "
                    "Max: %.4f%% | Min: %.4f%% | Avg: %.4f%%",
                    stats["live_symbols"],
                    collector.ws_reconnect_count,
                    (stats["max_funding_rate"] or 0) * 100,
                    (stats["min_funding_rate"] or 0) * 100,
                    (stats["avg_funding_rate"] or 0) * 100,
                )

                # Print a clean table to stdout (stripped of HTML tags for terminal)
                clean = table.replace("<b>", "").replace("</b>", "") \
                             .replace("<code>", "").replace("</code>", "")
                print(f"\n{clean}\n")

        except Exception as e:
            log.error("[Summary] Error: %s", e)

        await asyncio.sleep(SUMMARY_INTERVAL)


# ── Startup Guard ─────────────────────────────────────────────────────────────

def _startup_check(is_testnet: bool) -> None:
    """
    Safety check: warn loudly if connecting to mainnet.
    Require explicit confirmation to proceed on live data.
    """
    if not is_testnet:
        print("\n" + "!" * 60)
        print("  ⚠️  WARNING: MAINNET MODE ACTIVE")
        print("  This pipeline reads live Binance data.")
        print("  It does NOT place orders, but ensure you understand")
        print("  your API key permissions before proceeding.")
        print("!" * 60)
        confirm = input("\nType 'MAINNET' to confirm: ").strip()
        if confirm != "MAINNET":
            print("Aborted.")
            sys.exit(0)
    else:
        log.info("[Startup] Testnet mode — no real funds at risk ✅")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    # 1. Load config (reads .env, prints banner)
    cfg = load_config()

    # 2. Safety check
    _startup_check(cfg.is_testnet)

    # 3. Init DB
    db = FundingRateDB(cfg.db_path)
    db.init()
    log.info("[DB] Ready at %s", cfg.db_path)

    # 4. Init alert manager
    alert_manager = FundingRateAlertManager(cfg)

    def on_extreme(record):
        """Called by the collector when a symbol hits the alert threshold."""
        alert_manager.check(record)

    # 5. Init collector
    collector = FundingRateCollector(
        config           = cfg,
        db               = db,
        on_extreme       = on_extreme,
        extreme_threshold = 0.001,  # 0.1% — triggers alert manager check
    )

    # 6. Graceful shutdown on Ctrl+C
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig_name: str):
        log.info("[Main] Received %s — shutting down...", sig_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig.name: _shutdown(s))

    log.info("[Main] Pipeline starting. Press Ctrl+C to stop.")

    # 7. Run collector + summary loop concurrently
    try:
        await asyncio.gather(
            collector.start(),
            _summary_loop(db, collector),
            _watch_stop(stop_event, collector),
        )
    except asyncio.CancelledError:
        pass
    finally:
        db.close()
        log.info("[Main] Pipeline stopped. DB closed.")


async def _watch_stop(stop_event: asyncio.Event, collector: FundingRateCollector) -> None:
    """Wait for the stop event, then signal the collector to stop."""
    await stop_event.wait()
    await collector.stop()
    # Cancel all remaining tasks
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C (already handled by signal handler)

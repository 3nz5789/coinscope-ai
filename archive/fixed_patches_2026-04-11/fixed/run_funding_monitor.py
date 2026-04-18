"""
run_funding_monitor.py — Funding Rate Ingestion Pipeline Entry Point
CoinScopeAI | Phase: Data Pipeline

Usage:
    python run_funding_monitor.py

Environment variables (copy .env.template → .env and fill in values):
    TESTNET_MODE=true               # REQUIRED — must be true during validation phase
    TELEGRAM_BOT_TOKEN=...          # optional — alerts sent to console if absent
    TELEGRAM_CHAT_ID=...            # optional
    REST_POLL_INTERVAL_S=60         # optional — how often to supplement WS with REST
    WRITER_BATCH_SIZE=50            # optional — batch size for DB writes
    WRITER_FLUSH_INTERVAL_S=5       # optional — max seconds between DB flushes
    FUNDING_DB_PATH=funding_rates.db # optional — SQLite file path

Validation-phase policy:
    - TESTNET_MODE must be 'true'. The script will refuse to start on mainnet
      unless you explicitly confirm — protecting real funds during the 30-day
      validation window.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

# ── Load .env before importing project modules ──────────────────────────────
try:
    from dotenv import load_dotenv
    # Walk up to find the project root .env
    _here = Path(__file__).resolve().parent
    _env_path = _here.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
        print(f"[Startup] Loaded env from {_env_path}")
    else:
        load_dotenv()  # try cwd
except ImportError:
    pass  # python-dotenv not installed — rely on shell-exported vars

# ── Project imports ──────────────────────────────────────────────────────────
from funding_rate_store import FundingRateStore
from funding_rate_ingestion import FundingRatePipeline, IngestionConfig
from funding_rate_alert import FundingRateAlerter

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("FundingMonitor")

# ---------------------------------------------------------------------------
# Safety check — enforce testnet during validation phase
# ---------------------------------------------------------------------------

def startup_safety_check(is_testnet: bool) -> None:
    """
    Confirm environment before starting the pipeline.

    During the 30-day validation phase (Apr 10–30 2026), the monitor MUST
    run on testnet.  If mainnet is detected we prompt for explicit consent.
    """
    if is_testnet:
        logger.info("[Startup] ✅ Testnet mode confirmed — no real funds at risk.")
        return

    print("\n" + "!" * 60)
    print("  WARNING: TESTNET_MODE is not 'true'.")
    print("  This pipeline would connect to MAINNET Binance.")
    print("  During the 30-day validation phase, only testnet is permitted.")
    print("!" * 60)

    confirm = input("\nType 'MAINNET' to override and connect live: ").strip()
    if confirm != "MAINNET":
        print("[Startup] Aborted. Set TESTNET_MODE=true or type MAINNET to override.")
        sys.exit(0)

    logger.warning("[Startup] MAINNET mode confirmed by operator. Proceeding.")


# ---------------------------------------------------------------------------
# Stats reporter (runs every 5 minutes)
# ---------------------------------------------------------------------------

async def stats_reporter(pipeline: FundingRatePipeline, interval: int = 300) -> None:
    """Log a pipeline health snapshot every `interval` seconds."""
    while True:
        try:
            await asyncio.sleep(interval)
            s = pipeline.stats
            ws = s.get("ws", {})
            wr = s.get("writer", {})
            db = s.get("store", {})
            logger.info(
                f"[Stats] ws_ticks={ws.get('ticks_received', '?')} "
                f"last_tick_age={ws.get('last_tick_age_s', '?')}s | "
                f"written={wr.get('total_written', '?')} "
                f"dup_dropped={wr.get('total_dropped_dup', '?')} | "
                f"db_rows={db.get('total_rows', '?')} "
                f"symbols={db.get('unique_symbols', '?')} "
                f"db_size={db.get('db_size_kb', '?')}KB | "
                f"queue={s.get('queue_size', '?')}"
            )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug(f"[Stats] Reporter error: {exc!r}")


# ---------------------------------------------------------------------------
# Graceful shutdown handler
# ---------------------------------------------------------------------------

def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """Register SIGINT / SIGTERM to cancel all running tasks cleanly."""
    def _shutdown(*_):
        logger.info("[Shutdown] Signal received — cancelling tasks…")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    loop.add_signal_handler(signal.SIGINT, _shutdown)
    loop.add_signal_handler(signal.SIGTERM, _shutdown)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    # 1. Resolve config from env
    cfg = IngestionConfig()
    startup_safety_check(cfg.is_testnet)

    # 2. Open the SQLite store
    db_path = os.getenv("FUNDING_DB_PATH", "funding_rates.db")
    store = FundingRateStore(db_path=db_path)

    # 3. Build the alerter
    alerter = FundingRateAlerter(store=store)

    # 4. Build the pipeline (wires WS + REST → writer, with alerter callback)
    pipeline = FundingRatePipeline(
        store=store,
        config=cfg,
        on_new_record=alerter.check,
    )

    logger.info("=" * 60)
    logger.info("  CoinScopeAI — Funding Rate Monitor")
    logger.info(f"  DB path  : {Path(db_path).resolve()}")
    logger.info(f"  Env      : {'TESTNET' if cfg.is_testnet else 'MAINNET'}")
    logger.info("=" * 60)

    # 5. Start all async tasks
    tasks = [
        asyncio.create_task(pipeline.run(), name="pipeline"),
        asyncio.create_task(alerter.run_heartbeat_loop(), name="heartbeat"),
        asyncio.create_task(stats_reporter(pipeline), name="stats"),
    ]

    # 6. Prune old data once at startup (keep 30 days)
    deleted = await asyncio.get_event_loop().run_in_executor(
        None, store.prune_old, 30
    )
    if deleted:
        logger.info(f"[Startup] Pruned {deleted} rows > 30 days old.")

    # 7. Block until all tasks complete / are cancelled
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("[Main] Shutting down cleanly.")
    finally:
        # Cancel any remaining tasks
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final stats
        try:
            s = store.get_stats()
            logger.info(
                f"[Final] DB rows={s['total_rows']} "
                f"symbols={s['unique_symbols']} "
                f"alerts_fired={alerter.stats['alerts_fired']}"
            )
        except Exception:
            pass

        logger.info("[Main] Exit.")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

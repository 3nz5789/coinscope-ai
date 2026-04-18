"""
Funding Rate Store — SQLite Persistence Layer
CoinScopeAI | Phase: Data Pipeline

Stores Binance perpetual funding rate ticks with strict dedup logic.

Table schema:
    funding_rates(
        id                 INTEGER PK AUTOINCREMENT,
        symbol             TEXT NOT NULL,        -- BTCUSDT (no slash)
        funding_rate       REAL NOT NULL,        -- e.g. 0.0001 = 0.01 %
        mark_price         REAL NOT NULL,
        index_price        REAL,                 -- NULL if WS omits it
        next_funding_time  INTEGER NOT NULL,     -- Unix ms (Binance epoch)
        ingested_at        INTEGER NOT NULL,     -- Unix ms (local receipt)
        source             TEXT NOT NULL         -- 'ws' | 'rest'
    )

Dedup constraint: UNIQUE(symbol, next_funding_time)
  - Funding epochs settle at 00:00, 08:00, 16:00 UTC (every 8 h).
  - The WS !markPrice@arr stream re-broadcasts the same rate many times
    per second until the epoch rolls over.  We INSERT OR IGNORE so only
    the *first* received record per epoch survives.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FundingRateRecord:
    """A single funding-rate tick from the Binance stream."""
    symbol: str                  # BTCUSDT
    funding_rate: float          # 0.0001
    mark_price: float
    index_price: Optional[float]
    next_funding_time: int       # Unix ms
    ingested_at: int             # Unix ms (time.time_ns() // 1_000_000)
    source: str = "ws"           # 'ws' | 'rest'

    @property
    def funding_rate_pct(self) -> str:
        return f"{self.funding_rate:+.4%}"

    @property
    def is_extreme(self) -> bool:
        """Extreme: |rate| > 0.05 % per 8 h (≈ 54 % annualised)."""
        return abs(self.funding_rate) > 0.0005

    @property
    def is_high(self) -> bool:
        """High: |rate| > 0.02 % per 8 h (≈ 22 % annualised)."""
        return abs(self.funding_rate) > 0.0002


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class FundingRateStore:
    """
    SQLite-backed store for funding rate ticks.

    Thread-safe for single-writer/multi-reader use (WAL mode).
    Designed to be opened once per process and kept alive for the session.
    """

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS funding_rates (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol            TEXT    NOT NULL,
            funding_rate      REAL    NOT NULL,
            mark_price        REAL    NOT NULL,
            index_price       REAL,
            next_funding_time INTEGER NOT NULL,
            ingested_at       INTEGER NOT NULL,
            source            TEXT    NOT NULL DEFAULT 'ws',
            UNIQUE(symbol, next_funding_time)
        );
    """

    _CREATE_INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_fr_symbol ON funding_rates(symbol);",
        "CREATE INDEX IF NOT EXISTS idx_fr_ingested ON funding_rates(ingested_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_fr_sym_time ON funding_rates(symbol, ingested_at DESC);",
    ]

    def __init__(self, db_path: str = "funding_rates.db"):
        self.db_path = Path(db_path)
        self._init_db()
        logger.info(f"[FundingRateStore] Opened DB: {self.db_path.resolve()}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a new connection with WAL mode and sensible pragmas."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")   # safe enough with WAL
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Yield a cursor and auto-commit/rollback."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._cursor() as cur:
            cur.execute(self._CREATE_TABLE)
            for idx in self._CREATE_INDEXES:
                cur.execute(idx)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert(self, rec: FundingRateRecord) -> bool:
        """
        INSERT OR IGNORE a single record.

        Returns True if a new row was written, False if it was a duplicate
        (same symbol + next_funding_time already stored).
        """
        sql = """
            INSERT OR IGNORE INTO funding_rates
                (symbol, funding_rate, mark_price, index_price,
                 next_funding_time, ingested_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self._cursor() as cur:
            cur.execute(sql, (
                rec.symbol,
                rec.funding_rate,
                rec.mark_price,
                rec.index_price,
                rec.next_funding_time,
                rec.ingested_at,
                rec.source,
            ))
            written = cur.rowcount > 0
        if written:
            logger.debug(
                f"[Store] +{rec.symbol} {rec.funding_rate_pct} "
                f"nft={rec.next_funding_time} src={rec.source}"
            )
        return written

    def insert_batch(self, records: List[FundingRateRecord]) -> int:
        """
        INSERT OR IGNORE a batch of records.

        Returns the count of newly inserted rows (duplicates are silently
        dropped by the UNIQUE constraint).
        """
        if not records:
            return 0
        sql = """
            INSERT OR IGNORE INTO funding_rates
                (symbol, funding_rate, mark_price, index_price,
                 next_funding_time, ingested_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        rows = [
            (r.symbol, r.funding_rate, r.mark_price, r.index_price,
             r.next_funding_time, r.ingested_at, r.source)
            for r in records
        ]
        with self._cursor() as cur:
            cur.executemany(sql, rows)
            written = cur.rowcount  # rowcount from executemany = total affected
        logger.debug(f"[Store] batch {len(records)} → {written} new rows")
        return written

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_latest(self, symbol: str) -> Optional[FundingRateRecord]:
        """Return the most recently ingested record for a symbol."""
        sql = """
            SELECT symbol, funding_rate, mark_price, index_price,
                   next_funding_time, ingested_at, source
            FROM funding_rates
            WHERE symbol = ?
            ORDER BY ingested_at DESC
            LIMIT 1;
        """
        conn = self._connect()
        try:
            row = conn.execute(sql, (symbol.upper(),)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return FundingRateRecord(**dict(row))

    def get_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> List[FundingRateRecord]:
        """
        Return the last `limit` distinct funding epochs for a symbol,
        newest first.
        """
        sql = """
            SELECT symbol, funding_rate, mark_price, index_price,
                   next_funding_time, ingested_at, source
            FROM funding_rates
            WHERE symbol = ?
            ORDER BY next_funding_time DESC
            LIMIT ?;
        """
        conn = self._connect()
        try:
            rows = conn.execute(sql, (symbol.upper(), limit)).fetchall()
        finally:
            conn.close()
        return [FundingRateRecord(**dict(r)) for r in rows]

    def get_market_snapshot(self) -> List[FundingRateRecord]:
        """
        Return the single most-recent record for every symbol in the DB.
        Fast — scans the symbol index, not the full table.
        """
        sql = """
            SELECT fr.symbol, fr.funding_rate, fr.mark_price, fr.index_price,
                   fr.next_funding_time, fr.ingested_at, fr.source
            FROM funding_rates fr
            INNER JOIN (
                SELECT symbol, MAX(ingested_at) AS max_ts
                FROM funding_rates
                GROUP BY symbol
            ) latest ON fr.symbol = latest.symbol AND fr.ingested_at = latest.max_ts
            ORDER BY ABS(fr.funding_rate) DESC;
        """
        conn = self._connect()
        try:
            rows = conn.execute(sql).fetchall()
        finally:
            conn.close()
        return [FundingRateRecord(**dict(r)) for r in rows]

    def get_extremes(
        self,
        threshold: float = 0.0005,
        limit: int = 20,
    ) -> List[FundingRateRecord]:
        """
        Return the most recently ingested records where |funding_rate| exceeds
        `threshold`.  Useful for alerting scans.
        """
        sql = """
            SELECT fr.symbol, fr.funding_rate, fr.mark_price, fr.index_price,
                   fr.next_funding_time, fr.ingested_at, fr.source
            FROM funding_rates fr
            INNER JOIN (
                SELECT symbol, MAX(ingested_at) AS max_ts
                FROM funding_rates
                GROUP BY symbol
            ) latest ON fr.symbol = latest.symbol AND fr.ingested_at = latest.max_ts
            WHERE ABS(fr.funding_rate) > ?
            ORDER BY ABS(fr.funding_rate) DESC
            LIMIT ?;
        """
        conn = self._connect()
        try:
            rows = conn.execute(sql, (threshold, limit)).fetchall()
        finally:
            conn.close()
        return [FundingRateRecord(**dict(r)) for r in rows]

    def get_stats(self) -> dict:
        """Return row counts and DB size for monitoring."""
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM funding_rates;").fetchone()[0]
            symbols = conn.execute(
                "SELECT COUNT(DISTINCT symbol) FROM funding_rates;"
            ).fetchone()[0]
        finally:
            conn.close()
        size_kb = self.db_path.stat().st_size / 1024 if self.db_path.exists() else 0
        return {
            "total_rows": total,
            "unique_symbols": symbols,
            "db_size_kb": round(size_kb, 1),
        }

    def prune_old(self, keep_days: int = 30) -> int:
        """
        Delete records older than `keep_days` days.
        Returns the number of rows deleted.
        """
        cutoff_ms = int((time.time() - keep_days * 86400) * 1000)
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM funding_rates WHERE ingested_at < ?;",
                (cutoff_ms,),
            )
            deleted = cur.rowcount
        if deleted:
            logger.info(f"[Store] Pruned {deleted} rows older than {keep_days}d")
        return deleted

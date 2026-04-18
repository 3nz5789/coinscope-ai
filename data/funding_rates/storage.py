"""
storage.py — SQLite persistence layer for the Funding Rate Pipeline.

Schema:
  funding_rates_live    — one row per symbol, always the latest known rate (upsert)
  funding_rates_history — time-series snapshots for all symbols (written every hour)

All rates are stored as floats (e.g. 0.001 = 0.1%).
All timestamps are Unix epoch milliseconds (as stored by Binance).
"""

import sqlite3
import time
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional, Dict

log = logging.getLogger(__name__)


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class FundingRateRecord:
    symbol:           str
    funding_rate:     float   # e.g. 0.001 = 0.1% per 8h
    next_funding_time: int    # Unix ms when the next funding settlement occurs
    mark_price:       float
    index_price:      float
    collected_at:     int     # Unix ms when we received this data point


# ── Database ──────────────────────────────────────────────────────────────────

class FundingRateDB:
    """
    Thread-safe SQLite storage for funding rate data.

    Usage:
        db = FundingRateDB("funding_rates.db")
        db.init()
        db.upsert_live(record)
        top = db.get_top_positive(n=10)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def init(self) -> None:
        """Create tables if they don't exist. Safe to call multiple times."""
        with self._cursor() as cur:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS funding_rates_live (
                    symbol            TEXT PRIMARY KEY,
                    funding_rate      REAL NOT NULL,
                    next_funding_time INTEGER NOT NULL,
                    mark_price        REAL NOT NULL,
                    index_price       REAL NOT NULL,
                    collected_at      INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS funding_rates_history (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol            TEXT NOT NULL,
                    funding_rate      REAL NOT NULL,
                    next_funding_time INTEGER NOT NULL,
                    mark_price        REAL NOT NULL,
                    index_price       REAL NOT NULL,
                    collected_at      INTEGER NOT NULL
                );

                -- Index for time-range queries on history
                CREATE INDEX IF NOT EXISTS idx_history_symbol_time
                    ON funding_rates_history (symbol, collected_at);

                -- Index for finding extreme rates quickly
                CREATE INDEX IF NOT EXISTS idx_live_funding_rate
                    ON funding_rates_live (funding_rate);
            """)
        log.info("[DB] Tables initialised at %s", self.db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Write Operations ──────────────────────────────────────────────────────

    def upsert_live(self, record: FundingRateRecord) -> None:
        """
        Insert or replace the latest funding rate for a symbol.
        This is called on every WebSocket update — must be fast.
        """
        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO funding_rates_live
                    (symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    funding_rate      = excluded.funding_rate,
                    next_funding_time = excluded.next_funding_time,
                    mark_price        = excluded.mark_price,
                    index_price       = excluded.index_price,
                    collected_at      = excluded.collected_at
            """, (
                record.symbol,
                record.funding_rate,
                record.next_funding_time,
                record.mark_price,
                record.index_price,
                record.collected_at,
            ))

    def save_snapshot(self, records: List[FundingRateRecord]) -> None:
        """
        Bulk-insert a full snapshot of all symbols into the history table.
        Called once per hour (or around each funding settlement).
        """
        if not records:
            return
        with self._cursor() as cur:
            cur.executemany("""
                INSERT INTO funding_rates_history
                    (symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                (r.symbol, r.funding_rate, r.next_funding_time,
                 r.mark_price, r.index_price, r.collected_at)
                for r in records
            ])
        log.info("[DB] Saved history snapshot: %d symbols", len(records))

    # ── Read Operations ───────────────────────────────────────────────────────

    def get_symbol(self, symbol: str) -> Optional[FundingRateRecord]:
        """Get the latest funding rate for a single symbol."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at
                FROM funding_rates_live
                WHERE symbol = ?
            """, (symbol.upper(),))
            row = cur.fetchone()
        return _row_to_record(row) if row else None

    def get_all_live(self) -> List[FundingRateRecord]:
        """Get the latest funding rate for all tracked symbols."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at
                FROM funding_rates_live
                ORDER BY ABS(funding_rate) DESC
            """)
            rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def get_top_positive(self, n: int = 10) -> List[FundingRateRecord]:
        """Get top N symbols with highest (most positive) funding rates. Longs pay shorts."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at
                FROM funding_rates_live
                WHERE funding_rate > 0
                ORDER BY funding_rate DESC
                LIMIT ?
            """, (n,))
            rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def get_top_negative(self, n: int = 10) -> List[FundingRateRecord]:
        """Get top N symbols with most negative funding rates. Shorts pay longs."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at
                FROM funding_rates_live
                WHERE funding_rate < 0
                ORDER BY funding_rate ASC
                LIMIT ?
            """, (n,))
            rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def get_extreme(self, threshold: float = 0.001) -> List[FundingRateRecord]:
        """
        Get all symbols where |funding_rate| exceeds the threshold.
        Default threshold 0.001 = 0.1%.
        """
        with self._cursor() as cur:
            cur.execute("""
                SELECT symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at
                FROM funding_rates_live
                WHERE ABS(funding_rate) >= ?
                ORDER BY ABS(funding_rate) DESC
            """, (threshold,))
            rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def get_history(
        self,
        symbol: str,
        since_ms: int = None,
        limit: int = 200,
    ) -> List[FundingRateRecord]:
        """Get historical funding rate records for a symbol."""
        since_ms = since_ms or (int(time.time() * 1000) - 7 * 24 * 3600 * 1000)  # default: last 7 days
        with self._cursor() as cur:
            cur.execute("""
                SELECT symbol, funding_rate, next_funding_time, mark_price, index_price, collected_at
                FROM funding_rates_history
                WHERE symbol = ? AND collected_at >= ?
                ORDER BY collected_at DESC
                LIMIT ?
            """, (symbol.upper(), since_ms, limit))
            rows = cur.fetchall()
        return [_row_to_record(r) for r in rows]

    def symbol_count(self) -> int:
        """Number of symbols currently tracked in the live table."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM funding_rates_live")
            return cur.fetchone()[0]

    def summary(self) -> Dict:
        """Quick stats for logging / health checks."""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM funding_rates_live")
            live_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM funding_rates_history")
            history_count = cur.fetchone()[0]

            cur.execute("""
                SELECT MAX(funding_rate), MIN(funding_rate), AVG(funding_rate)
                FROM funding_rates_live
            """)
            max_r, min_r, avg_r = cur.fetchone()

        return {
            "live_symbols": live_count,
            "history_rows": history_count,
            "max_funding_rate": max_r,
            "min_funding_rate": min_r,
            "avg_funding_rate": avg_r,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    @contextmanager
    def _cursor(self):
        """Get a cursor with auto-commit. Creates connection lazily."""
        if self._conn is None:
            # check_same_thread=False: safe because we use one connection per process
            # and writes are serialized through the async event loop
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")   # concurrent reads while writing
            self._conn.execute("PRAGMA synchronous=NORMAL") # good balance of safety vs speed
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_record(row: tuple) -> FundingRateRecord:
    return FundingRateRecord(
        symbol            = row[0],
        funding_rate      = row[1],
        next_funding_time = row[2],
        mark_price        = row[3],
        index_price       = row[4],
        collected_at      = row[5],
    )

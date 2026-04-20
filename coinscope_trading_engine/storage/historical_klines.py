"""
historical_klines.py — 90-day rolling klines store
===================================================

Backfills OHLCV history from Binance Futures and keeps a rolling 90-day
window in a local SQLite file. Free tier: no API key needed, public
`/fapi/v1/klines` endpoint, 1200 req/min rate-limit per IP.

Design
------
- SQLite single-file DB at `logs/klines.sqlite`
- Table `klines(symbol, interval, open_time INTEGER PK, open, high, low, close, volume, close_time, num_trades)`
- Composite uniqueness on `(symbol, interval, open_time)` via PK
- Backfill: for each `(symbol, interval)`, request oldest-first in 1000-bar
  chunks from `now - lookback_days` up to `now`. Upsert (ignore on conflict).
- Refresh: find max open_time per `(symbol, interval)`, fetch from there
  forward, upsert.
- Prune: delete rows where `open_time < now - lookback_days`.
- Thread-safe via per-connection lock (SQLite handles this natively but we
  serialize writes to keep simple).

Usage
-----
    store = HistoricalKlinesStore()
    await store.backfill(symbols, intervals, lookback_days=90, rest=rest)
    await store.refresh(symbols, intervals, rest=rest)
    rows = store.query("BTCUSDT", "1h", since_ms=..., until_ms=..., limit=500)
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    symbol     TEXT NOT NULL,
    interval   TEXT NOT NULL,
    open_time  INTEGER NOT NULL,
    open       REAL NOT NULL,
    high       REAL NOT NULL,
    low        REAL NOT NULL,
    close      REAL NOT NULL,
    volume     REAL NOT NULL,
    close_time INTEGER NOT NULL,
    num_trades INTEGER,
    PRIMARY KEY (symbol, interval, open_time)
);
CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval_time
    ON klines (symbol, interval, open_time DESC);
"""


class HistoricalKlinesStore:
    def __init__(self, path: str = "logs/klines.sqlite") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._state: dict = {
            "last_backfill_at":  0.0,
            "last_refresh_at":   0.0,
            "last_refresh_err":  None,
            "total_rows":        0,
            "by_stream":         {},   # "BTCUSDT:1h" -> {rows, first_ts, last_ts, last_refresh_at}
        }
        self._init_schema()

    # ── Schema ────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path, timeout=10, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.executescript(SCHEMA)

    # ── Write path ────────────────────────────────────────────────────

    def _upsert_rows(self, symbol: str, interval: str, rows: list) -> int:
        """Insert klines, ignore duplicates. Returns count inserted."""
        if not rows:
            return 0
        with self._lock, self._conn() as c:
            before = c.execute("SELECT COUNT(*) FROM klines").fetchone()[0]
            c.executemany(
                """INSERT OR IGNORE INTO klines
                   (symbol, interval, open_time, open, high, low, close, volume, close_time, num_trades)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        symbol, interval,
                        int(r[0]),               # open_time
                        float(r[1]), float(r[2]), float(r[3]), float(r[4]),  # OHLC
                        float(r[5]),             # volume
                        int(r[6]),               # close_time
                        int(r[8]) if len(r) > 8 else None,  # num_trades
                    )
                    for r in rows
                ],
            )
            after = c.execute("SELECT COUNT(*) FROM klines").fetchone()[0]
        return after - before

    def prune(self, lookback_days: int) -> int:
        """Delete rows older than `lookback_days`. Returns rows deleted."""
        cutoff_ms = int(time.time() * 1000) - lookback_days * 86400 * 1000
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM klines WHERE open_time < ?", (cutoff_ms,))
            return cur.rowcount

    # ── Read path ─────────────────────────────────────────────────────

    def query(
        self,
        symbol: str,
        interval: str,
        since_ms: Optional[int] = None,
        until_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> list[dict]:
        q = "SELECT open_time, open, high, low, close, volume, close_time, num_trades FROM klines WHERE symbol=? AND interval=?"
        args: list = [symbol, interval]
        if since_ms is not None:
            q += " AND open_time >= ?"; args.append(since_ms)
        if until_ms is not None:
            q += " AND open_time <= ?"; args.append(until_ms)
        q += " ORDER BY open_time ASC LIMIT ?"
        args.append(limit)
        with self._lock, self._conn() as c:
            rows = c.execute(q, args).fetchall()
        cols = ["open_time", "open", "high", "low", "close", "volume", "close_time", "num_trades"]
        return [dict(zip(cols, r)) for r in rows]

    def latest_open_time(self, symbol: str, interval: str) -> Optional[int]:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?",
                (symbol, interval),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def stream_stats(self, symbol: str, interval: str) -> dict:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*), MIN(open_time), MAX(open_time) FROM klines WHERE symbol=? AND interval=?",
                (symbol, interval),
            ).fetchone()
        return {
            "symbol":   symbol,
            "interval": interval,
            "rows":     int(row[0] or 0),
            "first_ts": int(row[1]) if row and row[1] else None,
            "last_ts":  int(row[2]) if row and row[2] else None,
        }

    def global_stats(self) -> dict:
        with self._lock, self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM klines").fetchone()[0]
            db_size_bytes = self._path.stat().st_size if self._path.exists() else 0
            by_stream = c.execute(
                "SELECT symbol, interval, COUNT(*), MIN(open_time), MAX(open_time) FROM klines GROUP BY symbol, interval ORDER BY symbol, interval"
            ).fetchall()
        return {
            **self._state,
            "total_rows":    int(total),
            "db_size_bytes": db_size_bytes,
            "streams": [
                {"symbol": s, "interval": i, "rows": int(n), "first_ts": int(a) if a else None, "last_ts": int(b) if b else None}
                for s, i, n, a, b in by_stream
            ],
        }

    # ── Binance fetch ─────────────────────────────────────────────────

    async def _fetch_chunk(
        self,
        session,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> list:
        """One page from Binance Futures public klines. Public → no auth."""
        params = {
            "symbol":    symbol,
            "interval":  interval,
            "startTime": start_ms,
            "limit":     limit,
        }
        if end_ms is not None:
            params["endTime"] = end_ms
        url = "https://fapi.binance.com/fapi/v1/klines"
        async with session.get(url, params=params, timeout=20) as r:
            r.raise_for_status()
            return await r.json()

    # ── Public async entry points ────────────────────────────────────

    async def backfill(
        self,
        symbols: list[str],
        intervals: list[str],
        lookback_days: int = 90,
        concurrent: int = 2,
    ) -> dict:
        """Backfill every (symbol, interval) stream from (now - lookback_days)."""
        import aiohttp
        now_ms   = int(time.time() * 1000)
        start_ms = now_ms - lookback_days * 86400 * 1000
        inserted = 0

        async def one_stream(sess, sym: str, tf: str) -> int:
            nonlocal inserted
            cursor = start_ms
            count  = 0
            loops  = 0
            while cursor < now_ms and loops < 200:     # safety cap
                rows = await self._fetch_chunk(sess, sym, tf, cursor, limit=1000)
                if not rows:
                    break
                n = self._upsert_rows(sym, tf, rows)
                count += n
                inserted += n
                # Advance past the last returned bar
                last_open = int(rows[-1][0])
                # +1ms so we don't re-request the same bar
                cursor = last_open + 1
                loops += 1
                # Binance is 10 req/s friendly; 100ms gap ≈ 10rps
                await asyncio.sleep(0.1)
            return count

        async with aiohttp.ClientSession() as sess:
            sem = asyncio.Semaphore(concurrent)
            async def guarded(sym, tf):
                async with sem:
                    return await one_stream(sess, sym, tf)
            results = await asyncio.gather(
                *(guarded(s, i) for s in symbols for i in intervals),
                return_exceptions=True,
            )

        # Prune anything outside the rolling window
        pruned = self.prune(lookback_days)
        self._state["last_backfill_at"] = time.time()
        return {"inserted": inserted, "pruned": pruned, "errors": [str(e) for e in results if isinstance(e, Exception)]}

    async def refresh(
        self,
        symbols: list[str],
        intervals: list[str],
        lookback_days: int = 90,
    ) -> dict:
        """Fetch only the new bars since last refresh for each stream."""
        import aiohttp
        now_ms = int(time.time() * 1000)
        inserted = 0
        errors   = []

        async with aiohttp.ClientSession() as sess:
            for sym in symbols:
                for tf in intervals:
                    try:
                        last = self.latest_open_time(sym, tf)
                        if last is None:
                            start = now_ms - lookback_days * 86400 * 1000
                        else:
                            start = last + 1
                        # Single chunk is enough for interval < 1000 bars lag
                        rows = await self._fetch_chunk(sess, sym, tf, start, limit=1000)
                        n = self._upsert_rows(sym, tf, rows) if rows else 0
                        inserted += n
                        self._state["by_stream"][f"{sym}:{tf}"] = {
                            "last_refresh_at": time.time(),
                            "last_inserted":   n,
                        }
                        await asyncio.sleep(0.1)
                    except Exception as exc:
                        errors.append(f"{sym}:{tf}: {exc}")
                        self._state["last_refresh_err"] = str(exc)

        pruned = self.prune(lookback_days)
        self._state["last_refresh_at"] = time.time()
        if not errors:
            self._state["last_refresh_err"] = None
        return {"inserted": inserted, "pruned": pruned, "errors": errors}

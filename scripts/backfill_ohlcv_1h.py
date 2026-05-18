#!/usr/bin/env python3
"""
COI-101 — Backfill 12 months of 1h OHLCV from Binance USD-M Futures into
Postgres table `ohlcv_1h`, then validate the dataset and emit a gap report.

Endpoint:  GET https://fapi.binance.com/fapi/v1/klines  (public, no auth)
Interval:  1h
Pairs:     BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT
Window:    last 12 months ending at the most recent CLOSED 1h bar (UTC).

Out of scope (explicit, per task): no HMM retrain, no commit of the report,
no writes to Notion / signal_log / trade_journal. Read-only on Binance,
idempotent on Postgres via ON CONFLICT (symbol, open_time) DO NOTHING.

Usage:
  DATABASE_URL=postgresql://coinscopeai:devpassword@localhost:5432/coinscopeai_dev \
      python3 scripts/backfill_ohlcv_1h.py
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence, Tuple

import psycopg2
import psycopg2.extras
import requests

SYMBOLS: Sequence[str] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")
INTERVAL = "1h"
INTERVAL_MS = 60 * 60 * 1000
INTERVAL_S = 60 * 60
LOOKBACK_DAYS = 365
KLINE_LIMIT = 1500          # Binance max per request
PRICE_SPIKE_THRESHOLD = Decimal("0.20")  # 20% close-to-close
BASE_URL = "https://fapi.binance.com"
REQUEST_PACING_S = 0.25     # ~4 req/s — well under the 2400 weight/min cap
MAX_RETRIES = 6
USER_AGENT = "CoinScopeAI-backfill/1.0 (COI-101)"

LOG = logging.getLogger("backfill_ohlcv_1h")


# ─── Kline fetch ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Kline:
    symbol: str
    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int


def _request_klines(
    session: requests.Session,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> list:
    """One request, with bounded retries on 418/429/5xx and connection errors."""
    params = {
        "symbol": symbol,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": KLINE_LIMIT,
    }
    url = f"{BASE_URL}/fapi/v1/klines"
    backoff = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=20)
        except requests.RequestException as exc:
            LOG.warning("[%s] network error on attempt %d: %s", symbol, attempt, exc)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (418, 429):
            retry_after = float(resp.headers.get("Retry-After", backoff))
            LOG.warning(
                "[%s] %d rate-limited on attempt %d; sleeping %.1fs",
                symbol, resp.status_code, attempt, retry_after,
            )
            time.sleep(retry_after)
            backoff = min(backoff * 2, 60.0)
            continue
        if 500 <= resp.status_code < 600:
            LOG.warning(
                "[%s] %d server error on attempt %d; sleeping %.1fs",
                symbol, resp.status_code, attempt, backoff,
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue
        # Other 4xx — surface the body and raise.
        raise RuntimeError(
            f"Binance klines request failed: {resp.status_code} {resp.text[:200]}"
        )
    raise RuntimeError(f"Binance klines exhausted retries for {symbol} start={start_ms}")


def fetch_klines(
    symbol: str,
    start_ms: int,
    end_ms: int,
    session: Optional[requests.Session] = None,
) -> List[Kline]:
    """Paginate Binance klines for [start_ms, end_ms] (inclusive on start, exclusive on end)."""
    own_session = session is None
    if own_session:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

    out: List[Kline] = []
    cursor = start_ms
    try:
        while cursor < end_ms:
            raw = _request_klines(session, symbol, cursor, end_ms)
            if not raw:
                break
            for row in raw:
                # Binance kline fields (index → meaning):
                # 0 open_time(ms), 1 open, 2 high, 3 low, 4 close,
                # 5 volume, 6 close_time(ms), 7 quote_volume, 8 number_of_trades,
                # 9 taker_buy_base, 10 taker_buy_quote, 11 ignore
                out.append(
                    Kline(
                        symbol=symbol,
                        open_time_ms=int(row[0]),
                        open=Decimal(str(row[1])),
                        high=Decimal(str(row[2])),
                        low=Decimal(str(row[3])),
                        close=Decimal(str(row[4])),
                        volume=Decimal(str(row[5])),
                        trades=int(row[8]),
                    )
                )
            last_open = int(raw[-1][0])
            next_cursor = last_open + INTERVAL_MS
            if next_cursor <= cursor:
                # Defensive: server returned no progress — bail out to avoid an infinite loop.
                LOG.warning("[%s] no progress at cursor=%d; stopping", symbol, cursor)
                break
            cursor = next_cursor
            if len(raw) < KLINE_LIMIT:
                # No more data in the window.
                break
            time.sleep(REQUEST_PACING_S)
    finally:
        if own_session:
            session.close()
    return out


# ─── Load ───────────────────────────────────────────────────────────────────

INSERT_SQL = """
INSERT INTO ohlcv_1h (symbol, open_time, open, high, low, close, volume, trades)
VALUES %s
ON CONFLICT (symbol, open_time) DO NOTHING
"""


def load_klines(conn, klines: Sequence[Kline]) -> int:
    """Bulk insert; returns number of rows actually inserted (excludes ON CONFLICT skips)."""
    if not klines:
        return 0
    values = [
        (
            k.symbol,
            datetime.fromtimestamp(k.open_time_ms / 1000, tz=timezone.utc),
            k.open, k.high, k.low, k.close, k.volume, k.trades,
        )
        for k in klines
    ]
    with conn.cursor() as cur:
        before = _row_count(cur)
        psycopg2.extras.execute_values(cur, INSERT_SQL, values, page_size=1000)
        after = _row_count(cur)
    conn.commit()
    return after - before


def _row_count(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM ohlcv_1h")
    return cur.fetchone()[0]


# ─── Validate ───────────────────────────────────────────────────────────────

@dataclass
class SymbolReport:
    symbol: str
    bars: int
    expected_bars: int
    duplicates: int
    gaps: int                       # consecutive open_time delta > 1h
    gap_total_hours: int            # sum of missing hours across all gaps
    zero_volume_bars: int
    high_lt_low: int
    close_out_of_range: int
    open_out_of_range: int
    price_spikes: int
    first_open_time: Optional[datetime]
    last_open_time: Optional[datetime]
    gap_examples: List[Tuple[datetime, datetime, int]]   # (prev, next, missing_hours)
    spike_examples: List[Tuple[datetime, Decimal, Decimal, Decimal]]  # (open_time, prev_close, close, pct)

    def is_clean(self) -> bool:
        return (
            self.duplicates == 0
            and self.gaps == 0
            and self.zero_volume_bars == 0
            and self.high_lt_low == 0
            and self.close_out_of_range == 0
            and self.open_out_of_range == 0
            and self.price_spikes == 0
        )


def validate_symbol(conn, symbol: str, expected_bars: int) -> SymbolReport:
    """All validation runs against Postgres, not the in-memory fetch result.

    Rationale: the DB is the artifact the next step (HMM retrain) consumes, so
    that's what we validate. Duplicates against the raw fetch are still caught
    because the PK rejects them — they'd show up as ON CONFLICT misses, but
    we don't need a second count for that.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT open_time, open, high, low, close, volume "
            "FROM ohlcv_1h WHERE symbol = %s ORDER BY open_time",
            (symbol,),
        )
        rows = cur.fetchall()

    if not rows:
        return SymbolReport(
            symbol=symbol, bars=0, expected_bars=expected_bars,
            duplicates=0, gaps=0, gap_total_hours=0, zero_volume_bars=0,
            high_lt_low=0, close_out_of_range=0, open_out_of_range=0, price_spikes=0,
            first_open_time=None, last_open_time=None,
            gap_examples=[], spike_examples=[],
        )

    duplicates = 0  # PK guarantees zero; kept explicit for the report contract.
    gaps = 0
    gap_total_hours = 0
    zero_volume_bars = 0
    high_lt_low = 0
    close_out_of_range = 0
    open_out_of_range = 0
    price_spikes = 0
    gap_examples: List[Tuple[datetime, datetime, int]] = []
    spike_examples: List[Tuple[datetime, Decimal, Decimal, Decimal]] = []

    prev_time: Optional[datetime] = None
    prev_close: Optional[Decimal] = None

    for open_time, op, hi, lo, cl, vol in rows:
        if vol == 0:
            zero_volume_bars += 1
        if hi < lo:
            high_lt_low += 1
        if cl < lo or cl > hi:
            close_out_of_range += 1
        if op < lo or op > hi:
            open_out_of_range += 1

        if prev_time is not None:
            delta_s = int((open_time - prev_time).total_seconds())
            if delta_s > INTERVAL_S:
                missing = (delta_s // INTERVAL_S) - 1
                gaps += 1
                gap_total_hours += missing
                if len(gap_examples) < 10:
                    gap_examples.append((prev_time, open_time, missing))

        if prev_close is not None and prev_close != 0:
            pct = (cl - prev_close) / prev_close
            if abs(pct) > PRICE_SPIKE_THRESHOLD:
                price_spikes += 1
                if len(spike_examples) < 10:
                    spike_examples.append((open_time, prev_close, cl, pct))

        prev_time = open_time
        prev_close = cl

    return SymbolReport(
        symbol=symbol,
        bars=len(rows),
        expected_bars=expected_bars,
        duplicates=duplicates,
        gaps=gaps,
        gap_total_hours=gap_total_hours,
        zero_volume_bars=zero_volume_bars,
        high_lt_low=high_lt_low,
        close_out_of_range=close_out_of_range,
        open_out_of_range=open_out_of_range,
        price_spikes=price_spikes,
        first_open_time=rows[0][0],
        last_open_time=rows[-1][0],
        gap_examples=gap_examples,
        spike_examples=spike_examples,
    )


def render_report(reports: Sequence[SymbolReport]) -> str:
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("COI-101 — OHLCV 1h Gap Report")
    lines.append("=" * 78)

    header = (
        f"{'symbol':<10} {'bars':>6} {'exp':>6} {'dup':>4} "
        f"{'gaps':>5} {'gap_h':>6} {'zero_v':>7} {'h<l':>4} "
        f"{'c_oor':>6} {'o_oor':>6} {'spikes':>7} {'status':>7}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for r in reports:
        lines.append(
            f"{r.symbol:<10} {r.bars:>6} {r.expected_bars:>6} {r.duplicates:>4} "
            f"{r.gaps:>5} {r.gap_total_hours:>6} {r.zero_volume_bars:>7} "
            f"{r.high_lt_low:>4} {r.close_out_of_range:>6} {r.open_out_of_range:>6} "
            f"{r.price_spikes:>7} {'CLEAN' if r.is_clean() else 'FLAGS':>7}"
        )
    lines.append("")

    for r in reports:
        if r.first_open_time and r.last_open_time:
            lines.append(
                f"  {r.symbol}: range "
                f"{r.first_open_time.astimezone(timezone.utc).isoformat()} → "
                f"{r.last_open_time.astimezone(timezone.utc).isoformat()}"
            )
    lines.append("")

    flagged = [r for r in reports if not r.is_clean()]
    if not flagged:
        lines.append("All symbols clean. No gaps, no anomalies, no zero-volume bars.")
    else:
        lines.append("Detail on flagged symbols:")
        for r in flagged:
            lines.append(f"  [{r.symbol}]")
            if r.gap_examples:
                lines.append(f"    gap examples (up to 10 of {r.gaps}):")
                for prev_t, next_t, missing in r.gap_examples:
                    lines.append(
                        f"      {prev_t.astimezone(timezone.utc).isoformat()} → "
                        f"{next_t.astimezone(timezone.utc).isoformat()}  "
                        f"missing {missing}h"
                    )
            if r.spike_examples:
                lines.append(f"    spike examples (up to 10 of {r.price_spikes}):")
                for ot, pc, cc, pct in r.spike_examples:
                    lines.append(
                        f"      {ot.astimezone(timezone.utc).isoformat()}  "
                        f"{pc} → {cc}  ({pct:+.2%})"
                    )
    lines.append("=" * 78)
    return "\n".join(lines)


# ─── Driver ─────────────────────────────────────────────────────────────────

def _floor_to_hour_utc(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def compute_window(now: Optional[datetime] = None) -> Tuple[int, int, int]:
    """Returns (start_ms, end_ms, expected_bars).

    end_ms is the open_time of the most recent CLOSED 1h bar + 1ms, so Binance
    returns inclusive of that bar. start_ms = end - 365 days.
    """
    now = now or datetime.now(tz=timezone.utc)
    last_closed_open = _floor_to_hour_utc(now) - timedelta(hours=1)
    end_ms = int(last_closed_open.timestamp() * 1000) + INTERVAL_MS  # exclusive upper
    start_ms = end_ms - LOOKBACK_DAYS * 24 * INTERVAL_MS
    expected_bars = LOOKBACK_DAYS * 24
    return start_ms, end_ms, expected_bars


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://coinscopeai:devpassword@localhost:5432/coinscopeai_dev",
        ),
        help="Postgres DSN (env: DATABASE_URL).",
    )
    parser.add_argument(
        "--symbols", nargs="+", default=list(SYMBOLS),
        help="Symbol whitelist (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-fetch", action="store_true",
        help="Skip the Binance fetch and validate whatever is already in Postgres.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    start_ms, end_ms, expected = compute_window()
    LOG.info(
        "window: %s → %s (expected %d bars/symbol)",
        datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat(),
        datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).isoformat(),
        expected,
    )

    conn = psycopg2.connect(args.dsn)
    try:
        if not args.skip_fetch:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            try:
                for sym in args.symbols:
                    t0 = time.monotonic()
                    klines = fetch_klines(sym, start_ms, end_ms, session=session)
                    inserted = load_klines(conn, klines)
                    LOG.info(
                        "[%s] fetched=%d inserted=%d in %.1fs",
                        sym, len(klines), inserted, time.monotonic() - t0,
                    )
            finally:
                session.close()

        reports = [validate_symbol(conn, sym, expected) for sym in args.symbols]
    finally:
        conn.close()

    print(render_report(reports))
    any_flagged = any(not r.is_clean() for r in reports)
    return 1 if any_flagged else 0


if __name__ == "__main__":
    sys.exit(main())

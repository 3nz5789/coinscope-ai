"""
Bulk Historical Data Downloader for CoinScopeAI.

Sources:
  1. Bybit History-Data Portal (PRIMARY for order book backfill)
     - URL: https://quote-saver.bycsi.com/orderbook/linear/{SYMBOL}/{DATE}_{SYMBOL}_ob500.data.zip
     - Format: ZIP → NDJSON, each line = Bybit WebSocket orderbook.500 message (snapshot + delta)
     - Depth: 500 levels, ~200-350 MB/day compressed
     - Coverage: 2023-01-01 → yesterday
     - No auth required; direct CDN access
     - Also provides public trading history (trades) via public.bybit.com

  2. Binance REST (trades, depth snapshots, funding rates)
     - GET /fapi/v1/aggTrades  — paginated historical trades
     - GET /fapi/v1/depth      — depth snapshots
     - GET /fapi/v1/fundingRate — historical funding rates

  3. Bybit REST (trades, funding rates)
     - GET /v5/market/recent-trade — recent trades
     - GET /v5/market/funding/history — funding history

  4. public.bybit.com (bulk trade CSVs)
     - https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{DATE}.csv.gz
     - Columns: timestamp, symbol, side, size, price, tickDirection, trdMatchID, ...

All downloaded data is saved as JSONL.gz in the same format as the recorder,
making it directly replayable by the ReplayEngine.
"""

from __future__ import annotations

import asyncio
import gzip
import io
import json
import logging
import os
import struct
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import aiohttp
import orjson

from .base import (
    Exchange,
    EventType,
    FundingRate,
    Liquidation,
    OrderBookLevel,
    OrderBookUpdate,
    Trade,
    normalize_symbol,
    now_ms,
    to_bybit_symbol,
)

logger = logging.getLogger("coinscopeai.streams.downloader")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_range(start: date, end: date) -> List[date]:
    """Generate list of dates from start to end inclusive."""
    result = []
    current = start
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def _ms_to_date(ts_ms: int) -> date:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()


def _date_to_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _write_jsonl_gz(records: List[dict], path: Path) -> int:
    """Write records as JSONL.gz, returns bytes written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with gzip.open(str(path), "ab", compresslevel=6) as f:
        for rec in records:
            line = orjson.dumps(rec) + b"\n"
            f.write(line)
            total += len(line)
    return total


def _envelope(event_type: EventType, data_dict: dict) -> dict:
    return {
        "event_type": event_type.value,
        "timestamp_ms": data_dict.get("timestamp_ms", now_ms()),
        "data": data_dict,
    }


# ---------------------------------------------------------------------------
# Bybit History-Data Portal — Order Book (PRIMARY backfill source)
# ---------------------------------------------------------------------------

class BybitPortalDownloader:
    """
    Downloads historical order book data from Bybit's history-data portal.

    The portal provides 500-level order book snapshots + deltas in the exact
    same format as the live WebSocket feed. Each daily file is a ZIP archive
    containing a single NDJSON file with all book updates for that day.

    Direct CDN URL (no authentication required):
        https://quote-saver.bycsi.com/orderbook/linear/{SYMBOL}/{DATE}_{SYMBOL}_ob500.data.zip

    Coverage: 2023-01-01 → yesterday (approximately)
    Depth: 500 price levels per side
    Update frequency: ~100ms (same as live feed)
    """

    BASE_URL = "https://quote-saver.bycsi.com/orderbook"
    PORTAL_API = "https://www.bybit.com/x-api/quote/public/support/download/list-files"

    # Market type → CDN path segment
    MARKET_PATHS = {
        "linear": "linear",    # USDT perpetuals (BTCUSDT, ETHUSDT, etc.)
        "inverse": "inverse",  # Coin-margined (BTCUSD, ETHUSD, etc.)
    }

    def __init__(
        self,
        output_dir: str = "./data/bybit_portal",
        market_type: str = "linear",
        max_concurrent: int = 3,
        retry_attempts: int = 3,
    ):
        self.output_dir = Path(output_dir)
        self.market_type = market_type
        self.max_concurrent = max_concurrent
        self.retry_attempts = retry_attempts
        self._semaphore: Optional[asyncio.Semaphore] = None

    def _cdn_url(self, symbol: str, d: date) -> str:
        """Construct the direct CDN download URL for a given symbol and date."""
        date_str = d.strftime("%Y-%m-%d")
        sym = to_bybit_symbol(symbol)
        path_seg = self.MARKET_PATHS.get(self.market_type, "linear")
        filename = f"{date_str}_{sym}_ob500.data.zip"
        return f"{self.BASE_URL}/{path_seg}/{sym}/{filename}"

    def _output_path(self, symbol: str, d: date) -> Path:
        """Output path for the converted JSONL.gz file."""
        date_str = d.strftime("%Y-%m-%d")
        sym = to_bybit_symbol(symbol)
        return self.output_dir / sym / f"{date_str}_{sym}_ob500.jsonl.gz"

    async def download_range(
        self,
        symbol: str,
        start: date,
        end: date,
        session: aiohttp.ClientSession,
        skip_existing: bool = True,
    ) -> Dict[str, int]:
        """
        Download and convert order book data for a date range.

        Returns stats: {"downloaded": N, "skipped": N, "failed": N, "records": N}
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

        dates = _date_range(start, end)
        stats = {"downloaded": 0, "skipped": 0, "failed": 0, "records": 0}

        tasks = []
        for d in dates:
            out_path = self._output_path(symbol, d)
            if skip_existing and out_path.exists() and out_path.stat().st_size > 0:
                stats["skipped"] += 1
                continue
            tasks.append(d)

        logger.info(
            "BybitPortal: %s — %d dates to download, %d skipped",
            symbol, len(tasks), stats["skipped"],
        )

        async def _download_one(d: date) -> Tuple[bool, int]:
            async with self._semaphore:
                return await self._download_day(symbol, d, session)

        results = await asyncio.gather(*[_download_one(d) for d in tasks], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                stats["failed"] += 1
                logger.error("Download task failed: %s", r)
            else:
                ok, n_records = r
                if ok:
                    stats["downloaded"] += 1
                    stats["records"] += n_records
                else:
                    stats["failed"] += 1

        return stats

    async def _download_day(
        self, symbol: str, d: date, session: aiohttp.ClientSession,
    ) -> Tuple[bool, int]:
        """Download and convert a single day's order book data."""
        url = self._cdn_url(symbol, d)
        out_path = self._output_path(symbol, d)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        date_str = d.strftime("%Y-%m-%d")
        sym = to_bybit_symbol(symbol)

        for attempt in range(self.retry_attempts):
            try:
                logger.info("Downloading %s %s (attempt %d)", sym, date_str, attempt + 1)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status == 404:
                        logger.debug("Not found: %s %s", sym, date_str)
                        return False, 0
                    resp.raise_for_status()
                    zip_data = await resp.read()

                n_records = await asyncio.get_event_loop().run_in_executor(
                    None, self._convert_zip_to_jsonl_gz, zip_data, out_path, symbol, d,
                )
                logger.info(
                    "Converted %s %s → %d records → %s",
                    sym, date_str, n_records, out_path,
                )
                return True, n_records

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Download failed %s %s attempt %d: %s",
                    sym, date_str, attempt + 1, exc,
                )
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)

        return False, 0

    @staticmethod
    def _convert_zip_to_jsonl_gz(
        zip_data: bytes, out_path: Path, symbol: str, d: date,
    ) -> int:
        """
        Convert Bybit portal ZIP → JSONL.gz in CoinScopeAI recorder format.

        The ZIP contains a single NDJSON file where each line is a Bybit
        WebSocket orderbook.500 message (snapshot or delta).

        Each line is converted to an OrderBookUpdate envelope and written
        to the output JSONL.gz file.
        """
        sym = normalize_symbol(symbol)
        n_records = 0

        # Parse ZIP using streaming deflate (the file is too large for zipfile.ZipFile
        # when we only have partial data, so we parse the local file header manually)
        try:
            zip_buf = io.BytesIO(zip_data)
            with zipfile.ZipFile(zip_buf) as zf:
                names = zf.namelist()
                if not names:
                    return 0
                inner_name = names[0]
                raw_ndjson = zf.read(inner_name)
        except zipfile.BadZipFile:
            # Fallback: parse ZIP local file header manually (for partial downloads)
            raw_ndjson = BybitPortalDownloader._deflate_zip_stream(zip_data)
            if raw_ndjson is None:
                return 0

        with gzip.open(str(out_path), "wb", compresslevel=6) as out_f:
            for line in raw_ndjson.split(b"\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = orjson.loads(line)
                except Exception:
                    continue

                record = BybitPortalDownloader._convert_ob_message(msg, sym)
                if record is None:
                    continue

                out_f.write(orjson.dumps(record) + b"\n")
                n_records += 1

        return n_records

    @staticmethod
    def _deflate_zip_stream(data: bytes) -> Optional[bytes]:
        """Parse ZIP local file header and decompress deflate stream."""
        if data[:4] != b"PK\x03\x04":
            return None
        try:
            fname_len = struct.unpack("<H", data[26:28])[0]
            extra_len = struct.unpack("<H", data[28:30])[0]
            data_start = 30 + fname_len + extra_len
            decomp = zlib.decompressobj(-15)
            return decomp.decompress(data[data_start:])
        except Exception:
            return None

    @staticmethod
    def _convert_ob_message(msg: dict, symbol: str) -> Optional[dict]:
        """
        Convert a Bybit orderbook.500 WebSocket message to CoinScopeAI format.

        Input format:
            {
              "topic": "orderbook.500.BTCUSDT",
              "type": "snapshot" | "delta",
              "ts": 1735689601085,
              "data": {
                "s": "BTCUSDT",
                "b": [["93529.90", "0.587"], ...],  # bids [price, qty]
                "a": [["93530.00", "1.518"], ...],  # asks [price, qty]
                "u": 47289356                        # update_id / sequence
              }
            }

        Output: CoinScopeAI recorder envelope wrapping an OrderBookUpdate dict.
        """
        msg_type = msg.get("type", "")
        ts = int(msg.get("ts", 0))
        data = msg.get("data", {})

        if not data or msg_type not in ("snapshot", "delta"):
            return None

        bids = [[float(p), float(q)] for p, q in data.get("b", [])]
        asks = [[float(p), float(q)] for p, q in data.get("a", [])]
        seq = data.get("u")

        ob_dict = {
            "exchange": Exchange.BYBIT.value,
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "timestamp_ms": ts,
            "received_ms": ts,  # historical: use exchange ts
            "is_snapshot": msg_type == "snapshot",
            "sequence": seq,
        }

        event_type = (
            EventType.ORDERBOOK_SNAPSHOT if msg_type == "snapshot"
            else EventType.ORDERBOOK_UPDATE
        )

        return {
            "event_type": event_type.value,
            "timestamp_ms": ts,
            "data": ob_dict,
        }

    async def list_available_dates(
        self, symbol: str, session: aiohttp.ClientSession,
        start: date, end: date,
    ) -> List[date]:
        """
        Probe the CDN to find which dates actually have data available.
        Uses HEAD requests for efficiency.
        """
        available = []
        sym = to_bybit_symbol(symbol)
        sem = asyncio.Semaphore(10)

        async def check_date(d: date) -> Optional[date]:
            async with sem:
                url = self._cdn_url(symbol, d)
                try:
                    async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            return d
                except Exception:
                    pass
                return None

        results = await asyncio.gather(*[check_date(d) for d in _date_range(start, end)])
        return [d for d in results if d is not None]


# ---------------------------------------------------------------------------
# Binance REST Historical Downloaders
# ---------------------------------------------------------------------------

class BinanceHistoricalDownloader:
    """
    Downloads historical data from Binance FAPI (futures) REST endpoints.

    Sources:
    - Trades: GET /fapi/v1/aggTrades (paginated, up to 1000/request)
    - Depth:  GET /fapi/v1/depth (snapshot at a point in time)
    - Funding: GET /fapi/v1/fundingRate (historical funding rates)
    """

    FAPI_BASE = "https://fapi.binance.com"

    def __init__(self, output_dir: str = "./data/binance_historical"):
        self.output_dir = Path(output_dir)

    async def download_trades(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        session: aiohttp.ClientSession,
    ) -> Dict[str, int]:
        """Download historical aggregated trades via REST pagination."""
        sym = normalize_symbol(symbol)
        out_path = self.output_dir / sym / f"trades_{sym}_{start_ms}_{end_ms}.jsonl.gz"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        stats = {"records": 0, "requests": 0}
        current_start = start_ms

        with gzip.open(str(out_path), "wb", compresslevel=6) as out_f:
            while current_start < end_ms:
                params = {
                    "symbol": sym,
                    "startTime": str(current_start),
                    "endTime": str(min(current_start + 3_600_000, end_ms)),
                    "limit": "1000",
                }
                try:
                    async with session.get(
                        f"{self.FAPI_BASE}/fapi/v1/aggTrades",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                except Exception as exc:
                    logger.warning("Binance aggTrades error: %s", exc)
                    await asyncio.sleep(2)
                    continue

                stats["requests"] += 1
                if not data:
                    current_start += 3_600_000
                    continue

                for item in data:
                    trade = Trade(
                        exchange=Exchange.BINANCE.value,
                        symbol=sym,
                        trade_id=str(item["a"]),
                        price=float(item["p"]),
                        quantity=float(item["q"]),
                        side="sell" if item.get("m") else "buy",
                        timestamp_ms=int(item["T"]),
                        received_ms=int(item["T"]),
                    )
                    record = _envelope(EventType.TRADE, trade.to_dict())
                    out_f.write(orjson.dumps(record) + b"\n")
                    stats["records"] += 1

                # Advance past last trade
                last_ts = int(data[-1]["T"])
                current_start = last_ts + 1
                if len(data) < 1000:
                    current_start = min(current_start, end_ms + 1)

                await asyncio.sleep(0.1)  # rate limit

        logger.info("Binance trades: %d records, %d requests → %s", stats["records"], stats["requests"], out_path)
        return stats

    async def download_funding_rates(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        session: aiohttp.ClientSession,
    ) -> Dict[str, int]:
        """Download historical funding rates."""
        sym = normalize_symbol(symbol)
        out_path = self.output_dir / sym / f"funding_{sym}_{start_ms}_{end_ms}.jsonl.gz"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        stats = {"records": 0}
        current_start = start_ms

        with gzip.open(str(out_path), "wb", compresslevel=6) as out_f:
            while current_start < end_ms:
                params = {
                    "symbol": sym,
                    "startTime": str(current_start),
                    "endTime": str(end_ms),
                    "limit": "1000",
                }
                try:
                    async with session.get(
                        f"{self.FAPI_BASE}/fapi/v1/fundingRate",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                except Exception as exc:
                    logger.warning("Binance fundingRate error: %s", exc)
                    break

                if not data:
                    break

                for item in data:
                    fr = FundingRate(
                        exchange=Exchange.BINANCE.value,
                        symbol=normalize_symbol(item.get("symbol", sym)),
                        funding_rate=float(item.get("fundingRate", 0)),
                        predicted_rate=None,
                        funding_time_ms=int(item.get("fundingTime", 0)),
                        timestamp_ms=int(item.get("fundingTime", 0)),
                        received_ms=int(item.get("fundingTime", 0)),
                        mark_price=float(item["markPrice"]) if item.get("markPrice") else None,
                    )
                    record = _envelope(EventType.FUNDING_RATE, fr.to_dict())
                    out_f.write(orjson.dumps(record) + b"\n")
                    stats["records"] += 1

                last_ts = int(data[-1]["fundingTime"])
                current_start = last_ts + 1
                if len(data) < 1000:
                    break
                await asyncio.sleep(0.1)

        logger.info("Binance funding: %d records → %s", stats["records"], out_path)
        return stats


# ---------------------------------------------------------------------------
# Bybit public.bybit.com — Bulk Trade CSV Downloader
# ---------------------------------------------------------------------------

class BybitPublicTradesDownloader:
    """
    Downloads historical trade data from public.bybit.com.

    URL pattern:
        https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{DATE}.csv.gz

    CSV columns:
        timestamp, symbol, side, size, price, tickDirection,
        trdMatchID, grossValue, homeNotional, foreignNotional

    Coverage: 2020-03-25 → yesterday
    """

    BASE_URL = "https://public.bybit.com/trading"

    def __init__(self, output_dir: str = "./data/bybit_trades"):
        self.output_dir = Path(output_dir)

    def _cdn_url(self, symbol: str, d: date) -> str:
        sym = to_bybit_symbol(symbol)
        date_str = d.strftime("%Y-%m-%d")
        return f"{self.BASE_URL}/{sym}/{sym}{date_str}.csv.gz"

    async def download_range(
        self,
        symbol: str,
        start: date,
        end: date,
        session: aiohttp.ClientSession,
        skip_existing: bool = True,
    ) -> Dict[str, int]:
        """Download and convert trade CSVs for a date range."""
        sym = to_bybit_symbol(symbol)
        stats = {"downloaded": 0, "skipped": 0, "failed": 0, "records": 0}
        sem = asyncio.Semaphore(3)

        async def _one(d: date) -> Tuple[bool, int]:
            out_path = self.output_dir / sym / f"{sym}_{d.strftime('%Y-%m-%d')}_trades.jsonl.gz"
            if skip_existing and out_path.exists() and out_path.stat().st_size > 0:
                return None, 0  # None = skipped
            async with sem:
                return await self._download_day(symbol, d, session, out_path)

        results = await asyncio.gather(*[_one(d) for d in _date_range(start, end)], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                stats["failed"] += 1
            elif r[0] is None:
                stats["skipped"] += 1
            elif r[0]:
                stats["downloaded"] += 1
                stats["records"] += r[1]
            else:
                stats["failed"] += 1

        return stats

    async def _download_day(
        self, symbol: str, d: date, session: aiohttp.ClientSession, out_path: Path,
    ) -> Tuple[bool, int]:
        url = self._cdn_url(symbol, d)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sym = normalize_symbol(symbol)

        for attempt in range(3):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 404:
                        return False, 0
                    resp.raise_for_status()
                    csv_gz_data = await resp.read()

                n = await asyncio.get_event_loop().run_in_executor(
                    None, self._convert_csv_to_jsonl_gz, csv_gz_data, out_path, sym,
                )
                return True, n
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Bybit public trades error %s %s: %s", symbol, d, exc)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        return False, 0

    @staticmethod
    def _convert_csv_to_jsonl_gz(csv_gz_data: bytes, out_path: Path, symbol: str) -> int:
        """Convert Bybit public CSV.gz to CoinScopeAI JSONL.gz format."""
        import csv

        n = 0
        try:
            with gzip.open(io.BytesIO(csv_gz_data)) as gz_f:
                reader = csv.DictReader(io.TextIOWrapper(gz_f, encoding="utf-8"))
                with gzip.open(str(out_path), "wb", compresslevel=6) as out_f:
                    for row in reader:
                        try:
                            ts_s = float(row["timestamp"])
                            ts_ms = int(ts_s * 1000)
                            side = row.get("side", "Buy").lower()
                            trade = Trade(
                                exchange=Exchange.BYBIT.value,
                                symbol=symbol,
                                trade_id=row.get("trdMatchID", ""),
                                price=float(row["price"]),
                                quantity=float(row["size"]),
                                side=side,
                                timestamp_ms=ts_ms,
                                received_ms=ts_ms,
                            )
                            record = _envelope(EventType.TRADE, trade.to_dict())
                            out_f.write(orjson.dumps(record) + b"\n")
                            n += 1
                        except (KeyError, ValueError):
                            continue
        except Exception as exc:
            logger.warning("CSV conversion error for %s: %s", symbol, exc)

        return n


# ---------------------------------------------------------------------------
# Bybit REST — Historical Funding Rates
# ---------------------------------------------------------------------------

class BybitFundingDownloader:
    """Downloads historical funding rates from Bybit REST API."""

    def __init__(self, output_dir: str = "./data/bybit_funding"):
        self.output_dir = Path(output_dir)

    async def download(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
        session: aiohttp.ClientSession,
    ) -> Dict[str, int]:
        sym = to_bybit_symbol(symbol)
        out_path = self.output_dir / sym / f"funding_{sym}_{start_ms}_{end_ms}.jsonl.gz"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        stats = {"records": 0}
        cursor = None

        with gzip.open(str(out_path), "wb", compresslevel=6) as out_f:
            while True:
                params: Dict[str, Any] = {
                    "category": "linear",
                    "symbol": sym,
                    "startTime": str(start_ms),
                    "endTime": str(end_ms),
                    "limit": "200",
                }
                if cursor:
                    params["cursor"] = cursor
                try:
                    async with session.get(
                        "https://api.bybit.com/v5/market/funding/history",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                except Exception as exc:
                    logger.warning("Bybit funding history error: %s", exc)
                    break

                result = data.get("result", {})
                items = result.get("list", [])
                for item in items:
                    fr = FundingRate(
                        exchange=Exchange.BYBIT.value,
                        symbol=normalize_symbol(symbol),
                        funding_rate=float(item.get("fundingRate", 0)),
                        predicted_rate=None,
                        funding_time_ms=int(item.get("fundingRateTimestamp", 0)),
                        timestamp_ms=int(item.get("fundingRateTimestamp", 0)),
                        received_ms=int(item.get("fundingRateTimestamp", 0)),
                    )
                    record = _envelope(EventType.FUNDING_RATE, fr.to_dict())
                    out_f.write(orjson.dumps(record) + b"\n")
                    stats["records"] += 1

                cursor = result.get("nextPageCursor")
                if not cursor or not items:
                    break
                await asyncio.sleep(0.1)

        logger.info("Bybit funding: %d records → %s", stats["records"], out_path)
        return stats


# ---------------------------------------------------------------------------
# Unified Downloader — orchestrates all sources
# ---------------------------------------------------------------------------

class HistoricalDownloader:
    """
    Unified entry point for downloading historical market data.

    Coordinates all download sources and provides a single interface
    for bulk backfill operations.
    """

    def __init__(self, output_dir: str = "./data"):
        self.output_dir = Path(output_dir)
        self.bybit_portal = BybitPortalDownloader(
            output_dir=str(self.output_dir / "bybit_portal"),
        )
        self.bybit_trades = BybitPublicTradesDownloader(
            output_dir=str(self.output_dir / "bybit_public_trades"),
        )
        self.bybit_funding = BybitFundingDownloader(
            output_dir=str(self.output_dir / "bybit_funding"),
        )
        self.binance = BinanceHistoricalDownloader(
            output_dir=str(self.output_dir / "binance"),
        )

    async def download_orderbook_history(
        self,
        symbol: str,
        start: date,
        end: date,
        market_type: str = "linear",
        skip_existing: bool = True,
    ) -> Dict[str, Any]:
        """
        Download full order book history from Bybit history-data portal.

        This is the PRIMARY backfill source for the orderbook alpha generator.
        Provides 500-level depth at ~100ms resolution from 2023 onwards.
        """
        self.bybit_portal.market_type = market_type
        async with aiohttp.ClientSession() as session:
            stats = await self.bybit_portal.download_range(
                symbol, start, end, session, skip_existing,
            )
        return {"source": "bybit_portal", "symbol": symbol, **stats}

    async def download_trades_history(
        self,
        symbol: str,
        start: date,
        end: date,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Download historical trades from multiple sources.

        sources: ["bybit_public", "binance"] (default: both)
        """
        if sources is None:
            sources = ["bybit_public", "binance"]

        results = {}
        async with aiohttp.ClientSession() as session:
            if "bybit_public" in sources:
                stats = await self.bybit_trades.download_range(symbol, start, end, session)
                results["bybit_public"] = stats

            if "binance" in sources:
                start_ms = _date_to_ms(start)
                end_ms = _date_to_ms(end + timedelta(days=1)) - 1
                stats = await self.binance.download_trades(symbol, start_ms, end_ms, session)
                results["binance"] = stats

        return results

    async def download_funding_history(
        self,
        symbol: str,
        start: date,
        end: date,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Download historical funding rates."""
        if sources is None:
            sources = ["bybit", "binance"]

        start_ms = _date_to_ms(start)
        end_ms = _date_to_ms(end + timedelta(days=1)) - 1
        results = {}

        async with aiohttp.ClientSession() as session:
            if "bybit" in sources:
                stats = await self.bybit_funding.download(symbol, start_ms, end_ms, session)
                results["bybit"] = stats
            if "binance" in sources:
                stats = await self.binance.download_funding_rates(symbol, start_ms, end_ms, session)
                results["binance"] = stats

        return results

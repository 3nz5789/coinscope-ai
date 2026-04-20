"""
decision_journal.py — Persistent autotrade decision log
========================================================

Satisfies invariant #5 of the risk framework (docs/risk/risk-framework.md):

    "Every gate decision is journaled with a reason. Rejections are as
     important as accepts for reconstruction."

Every time `_autotrade_consider` reaches a verdict — accept, reject, skip,
error — we append one JSONL line to `logs/decisions.jsonl`. The file is
append-only; restart preserves history. Stats queries scan the tail.

Also maintains a bounded in-memory mirror keyed by symbol so the
per-symbol circuit breaker can read rolling state in O(1) without hitting
disk on every scan tick.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# One event = one JSONL line
# ---------------------------------------------------------------------------

@dataclass
class DecisionEvent:
    ts:           float
    symbol:       str
    direction:    Optional[str]       = None     # "LONG" | "SHORT" | None
    action:       str                 = "reject" # "accept" | "reject" | "skip" | "error" | "config" | "lifecycle"
    reason:       str                 = ""
    signal_score: Optional[float]     = None
    strength:     Optional[str]       = None
    regime:       Optional[str]       = None
    htf_trend:    Optional[str]       = None
    setup:        Optional[dict]      = None     # {entry, stop_loss, tp1, tp2, rr_ratio}
    scanners:     list                = field(default_factory=list)
    gate_state:   Optional[dict]      = None     # {breaker, positions, exposure_pct, daily_pnl_pct}
    order_id:     Optional[int]       = None
    qty:          Optional[float]     = None
    notional:     Optional[float]     = None
    source:       str                 = "auto"   # "auto" | "manual" | "api"
    extra:        Optional[dict]      = None


# ---------------------------------------------------------------------------
# Per-symbol rolling stats (derived, re-computed on append)
# ---------------------------------------------------------------------------

@dataclass
class SymbolHealth:
    symbol: str
    accepts_24h:      int   = 0
    rejects_24h:      int   = 0
    skips_24h:        int   = 0
    last_accept_at:   float = 0.0
    last_reject_at:   float = 0.0
    last_action:      str   = ""
    consecutive_losses: int = 0   # from journal close events (set by update_from_close)
    daily_pnl_usd:    float = 0.0 # cumulative realised since last reset
    daily_pnl_pct:    float = 0.0
    paused_until:     float = 0.0 # unix seconds — 0 = not paused


# ---------------------------------------------------------------------------
# DecisionJournal
# ---------------------------------------------------------------------------

class DecisionJournal:
    """Append-only JSONL log + in-memory rolling stats.

    Thread-safe (single lock) because writes happen from async tasks while
    reads happen from FastAPI request handlers.
    """

    def __init__(
        self,
        path: str = "logs/decisions.jsonl",
        window_s: int = 24 * 3600,
        max_cache: int = 5000,
        pg_url: Optional[str] = None,
    ) -> None:
        self._path       = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._window_s   = window_s
        self._lock       = threading.Lock()
        self._recent: "deque[DecisionEvent]" = deque(maxlen=max_cache)
        self._per_symbol: dict[str, SymbolHealth] = {}
        # Postgres mirror (optional — JSONL stays as the sync primary so we
        # never block a trade on a remote DB hiccup).
        self._pg_url        = pg_url or os.getenv("DECISIONS_PG_URL", "").strip() or None
        self._pg_pool       = None
        self._pg_ready      = False
        self._pg_write_q: "asyncio.Queue[DecisionEvent]" = asyncio.Queue(maxsize=1000)
        self._pg_writer_task: Optional[asyncio.Task] = None
        self._hydrate()

    # ── Postgres lifecycle ────────────────────────────────────────────

    async def pg_connect(self) -> None:
        """Open the pool and ensure schema exists. Fire-and-forget safe."""
        if not self._pg_url:
            return
        try:
            import asyncpg
            self._pg_pool = await asyncpg.create_pool(
                dsn=self._pg_url, min_size=1, max_size=4, command_timeout=10,
            )
            async with self._pg_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS decisions (
                        id           BIGSERIAL PRIMARY KEY,
                        ts           TIMESTAMPTZ NOT NULL,
                        symbol       TEXT NOT NULL,
                        direction    TEXT,
                        action       TEXT NOT NULL,
                        reason       TEXT,
                        signal_score DOUBLE PRECISION,
                        strength     TEXT,
                        regime       TEXT,
                        htf_trend    TEXT,
                        setup        JSONB,
                        scanners     JSONB,
                        gate_state   JSONB,
                        order_id     BIGINT,
                        qty          DOUBLE PRECISION,
                        notional     DOUBLE PRECISION,
                        source       TEXT,
                        extra        JSONB
                    );
                    CREATE INDEX IF NOT EXISTS idx_decisions_ts_symbol
                        ON decisions (ts DESC, symbol);
                    CREATE INDEX IF NOT EXISTS idx_decisions_action
                        ON decisions (action, ts DESC);
                """)
            self._pg_ready = True
            # Start the background writer
            self._pg_writer_task = asyncio.create_task(self._pg_writer_loop())
            log.info("DecisionJournal PG connected → %s", self._pg_url.split("@")[-1])
        except Exception as exc:
            log.warning("DecisionJournal PG connect failed (JSONL only): %s", exc)
            self._pg_pool = None
            self._pg_ready = False

    async def pg_close(self) -> None:
        if self._pg_writer_task:
            self._pg_writer_task.cancel()
            try:
                await self._pg_writer_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._pg_pool:
            try:
                await self._pg_pool.close()
            except Exception:
                pass

    async def _pg_writer_loop(self) -> None:
        """Drain queued events into Postgres. Batches up to 50/transaction."""
        if not self._pg_pool:
            return
        while True:
            try:
                first = await self._pg_write_q.get()
                batch: list[DecisionEvent] = [first]
                # Drain as many as are already queued, up to 50
                while len(batch) < 50 and not self._pg_write_q.empty():
                    batch.append(self._pg_write_q.get_nowait())
                async with self._pg_pool.acquire() as conn:
                    await conn.executemany(
                        """INSERT INTO decisions
                           (ts, symbol, direction, action, reason, signal_score,
                            strength, regime, htf_trend, setup, scanners, gate_state,
                            order_id, qty, notional, source, extra)
                           VALUES (to_timestamp($1), $2, $3, $4, $5, $6, $7, $8, $9,
                                   $10::jsonb, $11::jsonb, $12::jsonb,
                                   $13, $14, $15, $16, $17::jsonb)""",
                        [
                            (
                                e.ts, e.symbol, e.direction, e.action, e.reason,
                                e.signal_score, e.strength, e.regime, e.htf_trend,
                                json.dumps(e.setup) if e.setup else None,
                                json.dumps(e.scanners) if e.scanners else None,
                                json.dumps(e.gate_state) if e.gate_state else None,
                                e.order_id, e.qty, e.notional, e.source,
                                json.dumps(e.extra) if e.extra else None,
                            )
                            for e in batch
                        ],
                    )
            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.debug("DecisionJournal PG write failed: %s", exc)
                # Drop the batch on error — JSONL already has it, no data loss
                await asyncio.sleep(2)

    # ── Write path ────────────────────────────────────────────────────

    def record(self, event: DecisionEvent) -> None:
        """Append one event to disk + update in-memory stats + enqueue
        for async Postgres write. JSONL is the synchronous primary; PG is
        the best-effort mirror. Trading never blocks on PG."""
        with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(_prune_none(asdict(event)), default=str) + "\n")
            except Exception:
                # Never let journal failure kill a scan tick
                pass
            self._recent.append(event)
            self._update_health(event)

        # Fire-and-forget enqueue for PG. If the queue is full (PG slow),
        # we drop — the JSONL line already landed, so it's recoverable.
        if self._pg_ready:
            try:
                self._pg_write_q.put_nowait(event)
            except asyncio.QueueFull:
                log.debug("DecisionJournal PG queue full, dropping: %s", event.action)

    def record_close(self, symbol: str, pnl_usd: float, pnl_pct: float) -> None:
        """Called when a position closes. Updates rolling P&L and consec-loss counter."""
        evt = DecisionEvent(
            ts        = time.time(),
            symbol    = symbol,
            action    = "close",
            reason    = f"pnl={pnl_usd:+.2f} ({pnl_pct:+.2%})",
            extra     = {"pnl_usd": pnl_usd, "pnl_pct": pnl_pct},
        )
        self.record(evt)
        with self._lock:
            h = self._per_symbol.setdefault(symbol, SymbolHealth(symbol=symbol))
            h.daily_pnl_usd += pnl_usd
            h.daily_pnl_pct += pnl_pct
            if pnl_usd < 0:
                h.consecutive_losses += 1
            else:
                h.consecutive_losses = 0

    # ── Read path ─────────────────────────────────────────────────────

    def recent(
        self,
        symbol: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Most recent events (newest first), optionally filtered."""
        with self._lock:
            xs = list(self._recent)
        if symbol:
            xs = [e for e in xs if e.symbol == symbol]
        if action:
            xs = [e for e in xs if e.action == action]
        xs.reverse()
        return [_prune_none(asdict(e)) for e in xs[:limit]]

    def stats(self, window_s: Optional[int] = None) -> dict:
        """Aggregate decision counts + rejection reason histogram."""
        cutoff = time.time() - (window_s or self._window_s)
        actions: dict[str, int] = {}
        reject_reasons: dict[str, int] = {}
        symbol_actions: dict[str, dict[str, int]] = {}
        n = 0
        with self._lock:
            xs = list(self._recent)
        for e in xs:
            if e.ts < cutoff:
                continue
            n += 1
            actions[e.action] = actions.get(e.action, 0) + 1
            sa = symbol_actions.setdefault(e.symbol, {})
            sa[e.action] = sa.get(e.action, 0) + 1
            if e.action in ("reject", "error"):
                # Collapse the symbol-suffix — "BTCUSDT: setup invalid" → "setup invalid"
                key = e.reason.split(":", 1)[-1].strip()[:80] or "(empty)"
                reject_reasons[key] = reject_reasons.get(key, 0) + 1
        # Top-10 rejection reasons
        top_rejects = sorted(reject_reasons.items(), key=lambda kv: -kv[1])[:10]
        return {
            "window_s":       window_s or self._window_s,
            "total":          n,
            "by_action":      actions,
            "by_symbol":      symbol_actions,
            "top_rejections": [{"reason": r, "count": c} for r, c in top_rejects],
        }

    def per_symbol_health(self) -> dict[str, dict]:
        """Rolling per-symbol health snapshot."""
        with self._lock:
            return {s: asdict(h) for s, h in self._per_symbol.items()}

    def symbol_health(self, symbol: str) -> SymbolHealth:
        """Get (or create) the health record for one symbol."""
        with self._lock:
            return self._per_symbol.setdefault(symbol, SymbolHealth(symbol=symbol))

    def pause_symbol(self, symbol: str, duration_s: int, reason: str = "") -> None:
        """Pause autotrade on one symbol for `duration_s` seconds."""
        with self._lock:
            h = self._per_symbol.setdefault(symbol, SymbolHealth(symbol=symbol))
            h.paused_until = time.time() + duration_s
        self.record(DecisionEvent(
            ts=time.time(), symbol=symbol, action="pause",
            reason=f"paused {duration_s}s: {reason}",
        ))

    def is_symbol_paused(self, symbol: str) -> tuple[bool, float]:
        """Return (is_paused, seconds_remaining)."""
        h = self._per_symbol.get(symbol)
        if not h or h.paused_until <= 0:
            return (False, 0.0)
        now = time.time()
        if h.paused_until <= now:
            h.paused_until = 0.0
            return (False, 0.0)
        return (True, h.paused_until - now)

    def reset_daily(self) -> None:
        """Zero per-symbol daily counters. Call at UTC midnight."""
        with self._lock:
            for h in self._per_symbol.values():
                h.daily_pnl_usd = 0.0
                h.daily_pnl_pct = 0.0

    # ── Internals ─────────────────────────────────────────────────────

    def _hydrate(self) -> None:
        """On startup, replay the last 24h of events into the in-memory cache."""
        if not self._path.exists():
            return
        cutoff = time.time() - self._window_s
        kept = 0
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if d.get("ts", 0) < cutoff:
                        continue
                    evt = DecisionEvent(**{k: v for k, v in d.items() if k in DecisionEvent.__dataclass_fields__})
                    self._recent.append(evt)
                    self._update_health(evt)
                    kept += 1
        except Exception:
            pass
        # Note: we don't log here (no logger wired). Caller can read stats.

    def _update_health(self, e: DecisionEvent) -> None:
        """Maintain per-symbol aggregates as events arrive."""
        if not e.symbol or e.symbol == "-":
            return
        h = self._per_symbol.setdefault(e.symbol, SymbolHealth(symbol=e.symbol))
        h.last_action = e.action
        if e.action == "accept":
            h.accepts_24h += 1
            h.last_accept_at = e.ts
        elif e.action == "reject":
            h.rejects_24h += 1
            h.last_reject_at = e.ts
        elif e.action == "skip":
            h.skips_24h += 1


def _prune_none(d: dict) -> dict:
    """Drop None-valued keys for cleaner JSONL lines."""
    return {k: v for k, v in d.items() if v is not None}

"""
webhook_dispatcher.py — HTTP Webhook Alert Dispatcher
======================================================
POSTs structured JSON alert payloads to one or more external webhook URLs.

Features
--------
* Multiple endpoint support — dispatch to N URLs per alert
* Signed payloads — optional HMAC-SHA256 signature in X-Signature header
* Retry logic — 3 attempts with exponential backoff
* Per-endpoint health tracking — disables flaky endpoints after 5 consecutive
  failures, re-enables after RECOVER_AFTER_S seconds
* Async non-blocking — each endpoint dispatched concurrently via asyncio
* Alert payload schema matches Telegram alerts; includes signal metadata

Config (from .env)
------------------
  WEBHOOK_URLS          (comma-separated list)
  WEBHOOK_SECRET        (HMAC signing secret, optional)
  WEBHOOK_TIMEOUT_S     (default 10)

Usage
-----
    dispatcher = WebhookDispatcher()
    await dispatcher.dispatch_signal(signal, setup)
    await dispatcher.dispatch_status("Engine started")
    await dispatcher.dispatch_error("Circuit breaker", detail="...")
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import settings
from scanner.base_scanner import SignalDirection
from signals.confluence_scorer import Signal
from signals.entry_exit_calculator import TradeSetup
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES      = 3
RETRY_DELAY_S    = 1.0
MAX_FAILURES     = 5          # failures before endpoint is disabled
RECOVER_AFTER_S  = 300        # 5 min cooldown before re-enabling


# ---------------------------------------------------------------------------
# Endpoint health tracker
# ---------------------------------------------------------------------------

@dataclass
class _EndpointHealth:
    url:              str
    consecutive_fails: int = 0
    disabled_at:      float = 0.0
    total_sent:       int = 0
    total_failed:     int = 0

    @property
    def is_disabled(self) -> bool:
        if self.consecutive_fails < MAX_FAILURES:
            return False
        # Auto-recover after cooldown
        if time.monotonic() - self.disabled_at >= RECOVER_AFTER_S:
            self.consecutive_fails = 0
            self.disabled_at = 0.0
            logger.info("Webhook endpoint recovered: %s", self.url)
            return False
        return True

    def record_success(self) -> None:
        self.consecutive_fails = 0
        self.total_sent += 1

    def record_failure(self) -> None:
        self.consecutive_fails += 1
        self.total_failed += 1
        if self.consecutive_fails >= MAX_FAILURES and not self.disabled_at:
            self.disabled_at = time.monotonic()
            logger.warning(
                "Webhook endpoint disabled after %d failures: %s",
                MAX_FAILURES, self.url,
            )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class WebhookDispatcher:
    """
    Dispatches JSON alert payloads to external webhook URLs.

    Parameters
    ----------
    urls    : List of webhook URLs. Defaults to settings.webhook_urls.
    secret  : HMAC secret for payload signing. Defaults to settings.webhook_secret.
    timeout : HTTP timeout in seconds.
    """

    def __init__(
        self,
        urls:    Optional[list[str]] = None,
        secret:  Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        raw_urls = urls or getattr(settings, "webhook_urls", []) or []
        self._endpoints = [_EndpointHealth(url=u.strip()) for u in raw_urls if u.strip()]
        self._secret    = secret or getattr(settings, "webhook_secret", "") or ""
        self._timeout   = timeout
        self._client: Optional[httpx.AsyncClient] = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def __aenter__(self) -> "WebhookDispatcher":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if not self._client or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    # ── Public dispatch methods ──────────────────────────────────────────

    async def dispatch_signal(self, signal: Signal, setup: TradeSetup) -> dict[str, bool]:
        """Dispatch a trade signal alert to all endpoints."""
        payload = self._build_signal_payload(signal, setup)
        return await self._dispatch_all("signal", payload)

    async def dispatch_status(self, message: str, level: str = "info") -> dict[str, bool]:
        """Dispatch a status/info message."""
        payload = {
            "type":      "status",
            "level":     level,
            "message":   message,
            "timestamp": _now_iso(),
            "source":    "CoinScopeAI",
        }
        return await self._dispatch_all("status", payload)

    async def dispatch_error(
        self,
        message: str,
        detail: str = "",
        level:  str = "error",
    ) -> dict[str, bool]:
        """Dispatch an error/alert message."""
        payload = {
            "type":      "error",
            "level":     level,
            "message":   message,
            "detail":    detail[:500] if detail else "",
            "timestamp": _now_iso(),
            "source":    "CoinScopeAI",
        }
        return await self._dispatch_all("error", payload)

    async def dispatch_circuit_breaker(
        self,
        reason: str,
        daily_loss_pct: float,
    ) -> dict[str, bool]:
        """Dispatch a circuit breaker activation notice."""
        payload = {
            "type":            "circuit_breaker",
            "level":           "critical",
            "reason":          reason,
            "daily_loss_pct":  round(daily_loss_pct, 4),
            "limit_pct":       settings.max_daily_loss_pct,
            "timestamp":       _now_iso(),
            "source":          "CoinScopeAI",
        }
        return await self._dispatch_all("circuit_breaker", payload)

    # ── Internals ────────────────────────────────────────────────────────

    async def _dispatch_all(
        self,
        alert_type: str,
        payload: dict,
    ) -> dict[str, bool]:
        """Concurrently POST payload to all active endpoints."""
        if not self._endpoints:
            return {}

        client = await self._ensure_client()
        tasks  = [
            self._post_to_endpoint(ep, alert_type, payload, client)
            for ep in self._endpoints
            if not ep.is_disabled
        ]
        if not tasks:
            logger.warning("All webhook endpoints are disabled.")
            return {}

        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        results: dict[str, bool] = {}
        for ep, result in zip(
            [e for e in self._endpoints if not e.is_disabled], results_list
        ):
            ok = result is True
            results[ep.url] = ok

        succeeded = sum(1 for v in results.values() if v)
        logger.info(
            "Webhook dispatch [%s]: %d/%d endpoints succeeded",
            alert_type, succeeded, len(results),
        )
        return results

    async def _post_to_endpoint(
        self,
        endpoint: _EndpointHealth,
        alert_type: str,
        payload: dict,
        client: httpx.AsyncClient,
    ) -> bool:
        """POST to a single endpoint with retry logic."""
        body    = json.dumps(payload, default=str)
        headers = {
            "Content-Type":  "application/json",
            "X-Alert-Type":  alert_type,
            "X-Source":      "CoinScopeAI",
            "X-Timestamp":   str(int(time.time())),
        }
        if self._secret:
            sig = _sign_payload(body, self._secret)
            headers["X-Signature"] = sig

        delay = RETRY_DELAY_S
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.post(endpoint.url, content=body, headers=headers)
                if resp.is_success:
                    endpoint.record_success()
                    return True
                logger.warning(
                    "Webhook %s returned HTTP %d [attempt %d/%d]",
                    endpoint.url, resp.status_code, attempt, MAX_RETRIES,
                )
            except (httpx.HTTPError, Exception) as exc:
                logger.warning(
                    "Webhook request failed [attempt %d/%d] %s: %s",
                    attempt, MAX_RETRIES, endpoint.url, exc,
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2

        endpoint.record_failure()
        return False

    # ── Payload builders ─────────────────────────────────────────────────

    @staticmethod
    def _build_signal_payload(signal: Signal, setup: TradeSetup) -> dict:
        is_long = signal.direction == SignalDirection.LONG
        return {
            "type":      "signal",
            "timestamp": _now_iso(),
            "source":    "CoinScopeAI",
            "signal": {
                "symbol":    signal.symbol,
                "direction": signal.direction.value,
                "score":     round(signal.score, 2),
                "strength":  signal.strength,
                "scanners":  signal.scanner_names,
                "reasons":   signal.reasons[:5],
            },
            "setup": {
                "entry":       round(setup.entry, 8),
                "stop_loss":   round(setup.stop_loss, 8),
                "tp1":         round(setup.tp1, 8),
                "tp2":         round(setup.tp2, 8),
                "tp3":         round(setup.tp3, 8),
                "risk_pct":    round(setup.risk_pct, 4),
                "rr_ratio":    round(setup.rr_ratio_tp2, 3),
                "atr":         round(setup.atr, 8),
                "atr_pct":     round(setup.atr_pct, 4),
                "method":      setup.method,
                "valid":       setup.valid,
            },
            "indicators": _indicators_dict(signal),
        }

    @property
    def endpoint_count(self) -> int:
        return len(self._endpoints)

    @property
    def active_endpoint_count(self) -> int:
        return sum(1 for e in self._endpoints if not e.is_disabled)

    def health_report(self) -> list[dict]:
        return [
            {
                "url":        ep.url,
                "active":     not ep.is_disabled,
                "sent":       ep.total_sent,
                "failed":     ep.total_failed,
                "consec_fail": ep.consecutive_fails,
            }
            for ep in self._endpoints
        ]

    def __repr__(self) -> str:
        return (
            f"<WebhookDispatcher endpoints={self.endpoint_count} "
            f"active={self.active_endpoint_count}>"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sign_payload(body: str, secret: str) -> str:
    """Return HMAC-SHA256 hex signature of the payload."""
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


def _indicators_dict(signal: Signal) -> dict:
    """Extract a minimal indicator snapshot from a Signal."""
    ind = signal.indicators
    if not ind:
        return {}
    result: dict = {
        "trend":    ind.trend_direction,
        "momentum": ind.momentum_bias,
        "volatility": ind.volatility_state,
    }
    if ind.rsi is not None:       result["rsi"]  = round(ind.rsi, 2)
    if ind.adx is not None:       result["adx"]  = round(ind.adx, 2)
    if ind.macd_hist is not None: result["macd_hist"] = round(ind.macd_hist, 6)
    if ind.bb_pct_b is not None:  result["bb_pct_b"]  = round(ind.bb_pct_b, 4)
    return result

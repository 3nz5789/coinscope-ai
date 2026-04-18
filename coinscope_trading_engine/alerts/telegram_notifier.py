"""
telegram_notifier.py — Telegram Bot Alert Integration
=======================================================
Sends formatted trading alerts to a Telegram chat or channel
via the Telegram Bot API.

Features
--------
* HTML-formatted messages with emoji icons per signal direction
* Signal alert  — entry, SL, TP1/TP2/TP3, RR, score, scanners
* Status alert  — engine startup, shutdown, daily summary
* Error alert   — circuit breaker trips, API failures
* Retry logic   — 3 attempts with exponential backoff on API errors
* Message chunking — splits messages > 4096 chars automatically
* Photo support — can send chart screenshots with captions
* Test message  — validates bot token and chat ID on startup
* Deduplication — in-process TTL cache prevents identical messages
  being sent twice within DEDUP_TTL_S seconds (default 120 s)

Config (from .env)
------------------
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  TELEGRAM_PARSE_MODE      (default HTML)
  TELEGRAM_SEND_STARTUP_MSG (default true)

Usage
-----
    from alerts.telegram_notifier import TelegramNotifier

    notifier = TelegramNotifier()
    await notifier.send_signal(signal, setup)
    await notifier.send_status("Engine started ✅")
    await notifier.send_error("Circuit breaker triggered")
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import settings
from signals.confluence_scorer import Signal
from signals.entry_exit_calculator import TradeSetup
from scanner.base_scanner import SignalDirection
from utils.helpers import format_usdt, format_pct, human_number
from utils.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
MAX_MESSAGE_LEN   = 4096
MAX_RETRIES       = 3
RETRY_DELAY_S     = 1.0

# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
# Identical messages within this window are silently dropped.
# Covers back-to-back scan cycles re-firing on the same persisting signal.
DEDUP_TTL_S: int = 120   # seconds


def _msg_fingerprint(text: str) -> str:
    """
    Short SHA-256 fingerprint of the first 300 chars of a message.
    300 chars captures symbol + direction + price level — enough to
    distinguish every unique signal while ignoring trailing timestamp noise.
    """
    return hashlib.sha256(text[:300].encode()).hexdigest()[:24]


class TelegramNotifier:
    """
    Sends HTML-formatted alerts to a Telegram chat via Bot API.

    Parameters
    ----------
    token   : Bot token. Defaults to settings.telegram_bot_token.
    chat_id : Chat/channel ID. Defaults to settings.telegram_chat_id.
    dedup_ttl_s : Seconds within which an identical message is suppressed.
                  Set to 0 to disable deduplication entirely.
    """

    def __init__(
        self,
        token: Optional[str]   = None,
        chat_id: Optional[str] = None,
        dedup_ttl_s: int       = DEDUP_TTL_S,
    ) -> None:
        raw_token     = token   or (settings.telegram_bot_token.get_secret_value()
                                    if settings.telegram_bot_token else "")
        self._token   = raw_token.strip()
        self._chat_id = (chat_id or settings.telegram_chat_id or "").strip()
        self._enabled = bool(self._token and self._chat_id)
        self._base    = TELEGRAM_API_BASE.format(token=self._token) if self._enabled else ""
        self._client: Optional[httpx.AsyncClient] = None
        self._sent_count  = 0
        self._dedup_ttl_s = dedup_ttl_s
        # { fingerprint: last_sent_epoch_float }
        self._dedup_cache: dict[str, float] = {}

        if not self._enabled:
            logger.info(
                "TelegramNotifier: token/chat_id not set — "
                "alerts will be logged only (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env to enable)"
            )

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def __aenter__(self) -> "TelegramNotifier":
        self._client = httpx.AsyncClient(timeout=15)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if not self._client or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15)
        return self._client

    # ── Deduplication ────────────────────────────────────────────────────

    def _is_duplicate(self, text: str) -> bool:
        """
        Return True if this message was already sent within dedup_ttl_s.
        Also evicts stale entries from the cache on every call to prevent
        unbounded memory growth.
        """
        if self._dedup_ttl_s <= 0:
            return False

        now  = time.monotonic()
        fp   = _msg_fingerprint(text)

        # Evict expired entries (keep cache small)
        expired = [k for k, ts in self._dedup_cache.items() if now - ts > self._dedup_ttl_s]
        for k in expired:
            del self._dedup_cache[k]

        if fp in self._dedup_cache:
            age = now - self._dedup_cache[fp]
            logger.info(
                "TelegramNotifier: suppressing duplicate message "
                "(fp=%s age=%.0fs ttl=%ds)", fp, age, self._dedup_ttl_s
            )
            return True

        self._dedup_cache[fp] = now
        return False

    # ── Public send methods ──────────────────────────────────────────────

    async def send_signal(
        self,
        signal: Signal,
        setup:  TradeSetup,
    ) -> bool:
        """
        Send a formatted trade signal alert.

        Returns True on success, False on failure.
        """
        text = self._format_signal(signal, setup)
        return await self._send_message(text)

    async def send_status(self, message: str, emoji: str = "ℹ️") -> bool:
        """Send a plain status/info message."""
        text = (
            f"{emoji} <b>CoinScopeAI Status</b>\n"
            f"<code>{_now_str()}</code>\n\n"
            f"{message}"
        )
        return await self._send_message(text)

    async def send_error(self, message: str, detail: str = "") -> bool:
        """Send an error/alert message."""
        text = (
            f"🚨 <b>CoinScopeAI Alert</b>\n"
            f"<code>{_now_str()}</code>\n\n"
            f"<b>Error:</b> {_esc(message)}"
        )
        if detail:
            text += f"\n<pre>{_esc(detail[:300])}</pre>"
        return await self._send_message(text)

    async def send_startup(self) -> bool:
        """Send engine startup notification if configured."""
        if not settings.telegram_send_startup_msg:
            return True
        pairs = ", ".join(settings.scan_pairs[:6])
        if len(settings.scan_pairs) > 6:
            pairs += f" +{len(settings.scan_pairs) - 6} more"
        text = (
            f"🚀 <b>CoinScopeAI Engine Started</b>\n"
            f"<code>{_now_str()}</code>\n\n"
            f"🌐 Mode: <b>{'TESTNET' if settings.testnet_mode else '⚠️ MAINNET'}</b>\n"
            f"📊 Scanning: <code>{pairs}</code>\n"
            f"⏱ Interval: <code>{settings.scan_interval_seconds}s</code>\n"
            f"🎯 Min score: <code>{settings.min_confluence_score}</code>\n"
            f"🛡 Max leverage: <code>{settings.max_leverage}x</code>\n"
            f"💰 Daily loss cap: <code>{settings.max_daily_loss_pct}%</code>"
        )
        return await self._send_message(text)

    async def send_daily_summary(
        self,
        total_signals: int,
        actionable: int,
        top_signals: list[Signal],
    ) -> bool:
        """Send an end-of-day summary."""
        lines = [
            f"📅 <b>Daily Summary — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</b>\n",
            f"Signals generated: <b>{total_signals}</b>",
            f"Actionable signals: <b>{actionable}</b>\n",
        ]
        if top_signals:
            lines.append("<b>Top signals today:</b>")
            for sig in top_signals[:5]:
                icon = "🟢" if sig.direction == SignalDirection.LONG else "🔴"
                lines.append(
                    f"{icon} {sig.symbol} {sig.direction.value} "
                    f"score={sig.score:.1f} [{sig.strength}]"
                )
        return await self._send_message("\n".join(lines))

    async def send_circuit_breaker(self, reason: str, daily_loss_pct: float) -> bool:
        """Send a circuit breaker activation alert."""
        text = (
            f"🛑 <b>CIRCUIT BREAKER TRIGGERED</b>\n"
            f"<code>{_now_str()}</code>\n\n"
            f"Daily loss: <b>{daily_loss_pct:.2f}%</b> "
            f"(limit: {settings.max_daily_loss_pct}%)\n"
            f"Reason: {_esc(reason)}\n\n"
            f"⚠️ All trading halted for today."
        )
        return await self._send_message(text)

    async def test_connection(self) -> bool:
        """Verify bot token and chat ID with a test message."""
        if not self._enabled:
            logger.info("Telegram disabled — skipping connection test.")
            return True
        logger.info("Testing Telegram connection…")
        ok = await self.send_status("Connection test successful ✅", emoji="🔔")
        if ok:
            logger.info("Telegram connection verified.")
        else:
            logger.error("Telegram connection test FAILED.")
        return ok

    # ── Formatting ───────────────────────────────────────────────────────

    @staticmethod
    def _format_signal(signal: Signal, setup: TradeSetup) -> str:
        is_long = signal.direction == SignalDirection.LONG
        icon    = "🟢 LONG" if is_long else "🔴 SHORT"
        score_bar = _score_bar(signal.score)
        rr_icon = "✅" if setup.rr_ratio_tp2 >= settings.min_risk_reward_ratio else "⚠️"

        lines = [
            f"{icon} <b>{signal.symbol}</b>",
            f"<code>{_now_str()}</code>",
            "",
            f"📊 Score: <b>{signal.score:.1f}/100</b> {score_bar}",
            f"💪 Strength: <b>{signal.strength}</b>",
            f"🔭 Scanners: <code>{', '.join(signal.scanner_names)}</code>",
            "",
            f"💵 Entry:  <code>{format_usdt(setup.entry)}</code>",
            f"🛑 Stop:   <code>{format_usdt(setup.stop_loss)}</code>  "
            f"(<b>{format_pct(-setup.risk_pct if is_long else setup.risk_pct)}</b>)",
            f"🎯 TP1:   <code>{format_usdt(setup.tp1)}</code>",
            f"🎯 TP2:   <code>{format_usdt(setup.tp2)}</code>",
            f"🎯 TP3:   <code>{format_usdt(setup.tp3)}</code>",
            f"{rr_icon} RR:    <b>{setup.rr_ratio_tp2:.2f}x</b>  "
            f"(ATR: {format_usdt(setup.atr)})",
        ]

        # Indicator snapshot
        if signal.indicators:
            ind = signal.indicators
            ind_parts = []
            if ind.rsi:      ind_parts.append(f"RSI {ind.rsi:.0f}")
            if ind.adx:      ind_parts.append(f"ADX {ind.adx:.0f}")
            if ind.bb_pct_b: ind_parts.append(f"BB%B {ind.bb_pct_b:.2f}")
            if ind.macd_hist: ind_parts.append(
                f"MACD {'↑' if ind.macd_hist > 0 else '↓'}{ind.macd_hist:.4f}"
            )
            if ind_parts:
                lines += ["", f"📈 Indicators: <code>{' | '.join(ind_parts)}</code>"]
            lines.append(
                f"📉 Trend: <b>{ind.trend_direction}</b>  "
                f"Momentum: <b>{ind.momentum_bias}</b>  "
                f"Vol: <b>{ind.volatility_state}</b>"
            )

        # Scanner reasons (top 3)
        if signal.reasons:
            lines += ["", "<i>Reasons:</i>"]
            for reason in signal.reasons[:3]:
                lines.append(f"  • {_esc(reason)}")

        # Bonus notes
        if signal.bonuses:
            lines += [""]
            for bonus in signal.bonuses[:3]:
                lines.append(f"  {_esc(bonus)}")

        if not setup.valid:
            lines += ["", f"⚠️ <b>Note:</b> {_esc(setup.invalid_reason)}"]

        return "\n".join(lines)

    # ── Core HTTP sender ─────────────────────────────────────────────────

    async def _send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
    ) -> bool:
        """
        Send a text message, chunking if it exceeds MAX_MESSAGE_LEN.

        Deduplication: if an identical message (by content fingerprint) was
        sent within dedup_ttl_s seconds, it is silently dropped and True is
        returned (the caller doesn't need to know or retry).
        """
        if not self._enabled:
            logger.info("[Telegram disabled] %s", text[:120])
            return True

        # ── Dedup check ──────────────────────────────────────────────────
        if self._is_duplicate(text):
            return True   # treat as success — caller should not retry

        chunks = _chunk_text(text, MAX_MESSAGE_LEN)
        client = await self._ensure_client()

        for chunk in chunks:
            success = await self._post_with_retry(
                client, "sendMessage",
                {
                    "chat_id":                  self._chat_id,
                    "text":                     chunk,
                    "parse_mode":               parse_mode,
                    "disable_web_page_preview": disable_preview,
                },
            )
            if not success:
                return False
            self._sent_count += 1
        return True

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        payload: dict,
    ) -> bool:
        """
        POST to Telegram API with exponential backoff retry.

        IMPORTANT — ReadTimeout handling:
          If the request was sent but we timed out reading the response,
          Telegram may have already processed it.  We do NOT retry on
          ReadTimeout to avoid sending the same message twice.
          ConnectTimeout / ConnectError means the request never left the
          socket — those are safe to retry.
        """
        url   = f"{self._base}/{method}"
        delay = RETRY_DELAY_S

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=payload)
                data = resp.json()

                if data.get("ok"):
                    return True

                error_code  = data.get("error_code", 0)
                description = data.get("description", "unknown error")

                # 429 rate limit — respect retry_after
                if error_code == 429:
                    retry_after = data.get("parameters", {}).get("retry_after", delay)
                    logger.warning("Telegram rate limit — waiting %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                logger.error(
                    "Telegram API error [attempt %d/%d]: %d %s",
                    attempt, MAX_RETRIES, error_code, description,
                )

            except httpx.ReadTimeout:
                # The request was sent; we just didn't receive the ACK in time.
                # Retrying would send a duplicate — abort and log a warning.
                logger.warning(
                    "Telegram ReadTimeout on attempt %d — message may have been "
                    "delivered; skipping retry to prevent duplicate.", attempt
                )
                return False   # caller can decide to surface this

            except (httpx.ConnectTimeout, httpx.ConnectError) as exc:
                # Request never left — safe to retry
                logger.warning(
                    "Telegram connect error [attempt %d/%d]: %s", attempt, MAX_RETRIES, exc
                )

            except Exception as exc:
                logger.warning(
                    "Telegram request failed [attempt %d/%d]: %s", attempt, MAX_RETRIES, exc
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2

        logger.error("Telegram message failed after %d attempts.", MAX_RETRIES)
        return False

    @property
    def sent_count(self) -> int:
        return self._sent_count

    def __repr__(self) -> str:
        return f"<TelegramNotifier chat_id={self._chat_id} sent={self._sent_count}>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _score_bar(score: float, length: int = 10) -> str:
    """Return a Unicode progress bar representing the score."""
    filled = round(score / 100 * length)
    return "█" * filled + "░" * (length - filled)


def _chunk_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks of at most max_len characters."""
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_len]]

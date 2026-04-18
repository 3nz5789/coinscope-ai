"""
logger.py — Logging Configuration
===================================
Centralised logging setup for the CoinScopeAI engine.

Features
--------
* Rotating file handler  — rolls at LOG_MAX_MB, keeps LOG_BACKUP_COUNT archives
* Colour console handler — colour-coded by level for easy terminal reading
* JSON structured handler — optional, for log aggregation pipelines
* Per-module loggers     — use get_logger(__name__) in every module
* Sensitive data masking — strips API keys / secrets from log output

Usage
-----
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Engine started")
    logger.warning("Rate limit approaching: %d/%d", used, limit)
    logger.error("Order failed: %s", error)
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path
from typing import Optional

from config import settings

# ---------------------------------------------------------------------------
# ANSI colour codes for console output
# ---------------------------------------------------------------------------

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREY   = "\033[90m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_BRED   = "\033[1;31m"   # bold red for CRITICAL
_CYAN   = "\033[36m"

_LEVEL_COLOURS = {
    logging.DEBUG:    _GREY,
    logging.INFO:     _GREEN,
    logging.WARNING:  _YELLOW,
    logging.ERROR:    _RED,
    logging.CRITICAL: _BRED,
}

# Patterns to mask in log output (API keys, secrets, tokens)
_SENSITIVE_PATTERNS = [
    re.compile(r"(apiKey[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(api_secret[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9]{20,})", re.IGNORECASE),
    re.compile(r"(signature[\"']?\s*[:=]\s*[\"']?)([a-f0-9]{40,})", re.IGNORECASE),
    re.compile(r"(token[\"']?\s*[:=]\s*[\"']?)(\d+:[A-Za-z0-9_\-]{30,})", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"']?)(\S+)", re.IGNORECASE),
    re.compile(r"(secret[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9]{16,})", re.IGNORECASE),
]


def _mask_sensitive(text: str) -> str:
    """Replace sensitive values with ***MASKED*** in log messages."""
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "***MASKED***", text)
    return text


# ---------------------------------------------------------------------------
# Custom formatters
# ---------------------------------------------------------------------------

class ColourFormatter(logging.Formatter):
    """Console formatter with ANSI colour coding by log level."""

    FMT = "{colour}{levelname:<8}{reset} {grey}{name}{reset}  {msg}"

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, _RESET)
        log_fmt = (
            f"{colour}%(levelname)-8s{_RESET} "
            f"{_GREY}%(name)s{_RESET}  "
            f"%(message)s"
            f"  {_GREY}%(asctime)s{_RESET}"
        )
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        record.msg = _mask_sensitive(str(record.msg))
        return formatter.format(record)


class PlainFormatter(logging.Formatter):
    """Plain-text formatter for rotating file output."""

    def format(self, record: logging.LogRecord) -> str:
        record.msg = _mask_sensitive(str(record.msg))
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for log aggregation pipelines
    (Datadog, ELK, CloudWatch, etc.).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":   record.levelname,
            "logger":  record.name,
            "message": _mask_sensitive(record.getMessage()),
            "module":  record.module,
            "line":    record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


# ---------------------------------------------------------------------------
# Sensitive-data filter
# ---------------------------------------------------------------------------

class SensitiveFilter(logging.Filter):
    """Logging filter that masks sensitive data in all records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg  = _mask_sensitive(str(record.msg))
        record.args = tuple(
            _mask_sensitive(str(a)) if isinstance(a, str) else a
            for a in (record.args or ())
        )
        return True


# ---------------------------------------------------------------------------
# Public setup function
# ---------------------------------------------------------------------------

_configured = False   # guard against double-initialisation


def setup_logging(
    level: Optional[str]     = None,
    log_file: Optional[str]  = None,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
    json_logs: bool          = False,
    force: bool              = False,
) -> None:
    """
    Configure the root logger for the CoinScopeAI engine.

    This is called once at startup (already invoked by config.py).
    Calling it again is a no-op unless ``force=True``.

    Parameters
    ----------
    level        : Log level string (DEBUG/INFO/WARNING/ERROR/CRITICAL).
                   Defaults to settings.log_level.
    log_file     : Path to the rotating log file.
                   Defaults to settings.log_file.
    max_bytes    : Max file size in bytes before rotation.
                   Defaults to settings.log_max_mb * 1024 * 1024.
    backup_count : Number of rotated files to keep.
                   Defaults to settings.log_backup_count.
    json_logs    : If True, file handler uses JSON formatter.
    force        : Re-configure even if already set up.
    """
    global _configured
    if _configured and not force:
        return
    _configured = True

    _level       = getattr(logging, (level or settings.log_level.value).upper(), logging.INFO)
    _log_file    = log_file     or settings.log_file
    _max_bytes   = max_bytes    or settings.log_max_mb * 1024 * 1024
    _backup      = backup_count or settings.log_backup_count

    # Create log directory
    Path(_log_file).parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(_level)

    # Remove any existing handlers (avoid duplicate output on re-configure)
    root.handlers.clear()

    sensitive_filter = SensitiveFilter()

    # ── Console handler ──────────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(_level)
    ch.setFormatter(ColourFormatter())
    ch.addFilter(sensitive_filter)
    root.addHandler(ch)

    # ── Rotating file handler ────────────────────────────────────────────
    fh = logging.handlers.RotatingFileHandler(
        filename=_log_file,
        maxBytes=_max_bytes,
        backupCount=_backup,
        encoding="utf-8",
    )
    fh.setLevel(_level)
    fh.setFormatter(
        JSONFormatter() if json_logs else
        PlainFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    fh.addFilter(sensitive_filter)
    root.addHandler(fh)

    # ── Silence noisy third-party loggers ────────────────────────────────
    for noisy in ("websockets", "asyncio", "aiohttp", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured | level=%s file=%s json=%s",
        logging.getLevelName(_level), _log_file, json_logs,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger for a module.

    Usage (at the top of every module)::

        from utils.logger import get_logger
        logger = get_logger(__name__)

    Parameters
    ----------
    name : str
        Typically ``__name__`` of the calling module.
    """
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Convenience context manager — temporarily change log level
# ---------------------------------------------------------------------------

class log_level:
    """
    Temporarily change the log level of a logger.

    Usage::

        with log_level(logging.DEBUG):
            client.debug_heavy_operation()
    """

    def __init__(self, level: int, logger_name: str = "") -> None:
        self._logger   = logging.getLogger(logger_name)
        self._new      = level
        self._original = self._logger.level

    def __enter__(self) -> None:
        self._logger.setLevel(self._new)

    def __exit__(self, *_: object) -> None:
        self._logger.setLevel(self._original)


# ---------------------------------------------------------------------------
# Initialise on import if not already done by config.py
# ---------------------------------------------------------------------------
setup_logging()

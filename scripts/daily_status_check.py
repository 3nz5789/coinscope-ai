#!/usr/bin/env python3
"""
CoinScopeAI Daily Status Check
================================
Checks the health of the entire CoinScopeAI paper trading stack and
outputs a clean summary report to stdout (and optionally to a log file).

Usage:
    python3 scripts/daily_status_check.py                  # Print to stdout
    python3 scripts/daily_status_check.py --log            # Also save to logs/
    python3 scripts/daily_status_check.py --telegram       # Send to Telegram bot
    python3 scripts/daily_status_check.py --log --telegram # Both

Scheduling (cron example — runs at 08:00 UTC every day):
    0 8 * * * cd /path/to/coinscope-ai && python3 scripts/daily_status_check.py --log --telegram >> logs/cron.log 2>&1

Environment variables (read from .env or shell):
    COINSCOPEAI_BASE_URL            Engine URL (default: http://localhost:8001)
    BINANCE_FUTURES_TESTNET_API_KEY Testnet API key
    BINANCE_FUTURES_TESTNET_API_SECRET Testnet API secret
    BINANCE_FUTURES_TESTNET_BASE_URL   Testnet base URL
    TELEGRAM_BOT_TOKEN              Telegram bot token
    TELEGRAM_CHAT_ID                Telegram chat ID
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ─── Config ──────────────────────────────────────────────────────────────────

# Load .env if present (simple parser, no dependency on python-dotenv)
def load_dotenv(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lstrip("export").strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

load_dotenv()

ENGINE_URL       = os.environ.get("COINSCOPEAI_BASE_URL", "http://localhost:8001")
TESTNET_BASE_URL = os.environ.get("BINANCE_FUTURES_TESTNET_BASE_URL", "https://testnet.binancefuture.com")
TESTNET_API_KEY  = os.environ.get("BINANCE_FUTURES_TESTNET_API_KEY", "")
TESTNET_SECRET   = os.environ.get("BINANCE_FUTURES_TESTNET_API_SECRET", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

TIMEOUT = 8  # seconds per HTTP request

# ─── ANSI colours (disabled when not a TTY) ──────────────────────────────────

IS_TTY = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if IS_TTY else text

def green(t: str)  -> str: return _c("32", t)
def red(t: str)    -> str: return _c("31", t)
def yellow(t: str) -> str: return _c("33", t)
def cyan(t: str)   -> str: return _c("36", t)
def bold(t: str)   -> str: return _c("1",  t)
def dim(t: str)    -> str: return _c("2",  t)

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def http_get(url: str, headers: Optional[dict] = None, timeout: int = TIMEOUT) -> tuple[int, Any]:
    """Returns (status_code, parsed_json_or_None)."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return e.code, json.loads(body)
        except Exception:
            return e.code, None
    except Exception:
        return 0, None


def binance_signed_get(path: str, params: dict) -> tuple[int, Any]:
    """Signed GET request to Binance Futures Testnet."""
    if not TESTNET_API_KEY or not TESTNET_SECRET:
        return -1, {"error": "No testnet API credentials configured"}

    params["timestamp"] = int(time.time() * 1000)
    query = urllib.parse.urlencode(params)
    sig = hmac.new(TESTNET_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{TESTNET_BASE_URL}{path}?{query}&signature={sig}"
    headers = {"X-MBX-APIKEY": TESTNET_API_KEY}
    return http_get(url, headers=headers)


# ─── Check functions ──────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.ok: bool = False
        self.status: str = "UNKNOWN"
        self.details: list[str] = []
        self.data: dict = {}

    def pass_(self, status: str = "OK") -> "CheckResult":
        self.ok = True
        self.status = status
        return self

    def warn(self, status: str = "WARN") -> "CheckResult":
        self.ok = True   # not fatal
        self.status = status
        return self

    def fail(self, status: str = "FAIL") -> "CheckResult":
        self.ok = False
        self.status = status
        return self

    def add(self, line: str) -> "CheckResult":
        self.details.append(line)
        return self


def check_engine() -> CheckResult:
    r = CheckResult("Paper Trading Engine")
    start = time.time()
    code, data = http_get(f"{ENGINE_URL}/scan")
    latency_ms = int((time.time() - start) * 1000)

    if code == 0:
        return r.fail("UNREACHABLE").add(f"Engine at {ENGINE_URL} is not responding")

    if code != 200:
        return r.fail(f"HTTP {code}").add(f"Unexpected status code from /scan")

    r.data["latency_ms"] = latency_ms
    r.add(f"URL: {ENGINE_URL}")
    r.add(f"Latency: {latency_ms} ms")

    # Count signals
    signals = data if isinstance(data, list) else data.get("signals", data.get("data", []))
    if isinstance(signals, list):
        r.data["signal_count"] = len(signals)
        r.add(f"Signals in /scan: {len(signals)}")
    return r.pass_("RUNNING")


def check_engine_endpoints() -> CheckResult:
    r = CheckResult("Engine Endpoints")
    endpoints = ["/performance", "/journal", "/risk-gate", "/position-size"]
    results = []
    for ep in endpoints:
        code, _ = http_get(f"{ENGINE_URL}{ep}")
        status = "✓" if code == 200 else f"✗ ({code or 'timeout'})"
        results.append(f"{ep}: {status}")
        r.data[ep] = code

    all_ok = all(r.data.get(ep) == 200 for ep in endpoints)
    for line in results:
        r.add(line)
    return r.pass_("ALL OK") if all_ok else r.warn("PARTIAL")


def check_risk_gate() -> CheckResult:
    r = CheckResult("Risk Gate")
    code, data = http_get(f"{ENGINE_URL}/risk-gate")

    if code == 0:
        return r.fail("UNREACHABLE").add("Engine not reachable — cannot check risk gate")
    if code != 200:
        return r.fail(f"HTTP {code}")

    if not isinstance(data, dict):
        return r.warn("UNEXPECTED FORMAT").add(f"Response: {str(data)[:80]}")

    # Normalise field names
    daily_loss = float(data.get("daily_loss_pct") or data.get("dailyLossPct") or 0)
    drawdown   = float(data.get("drawdown_pct")   or data.get("drawdownPct")   or 0)
    heat       = float(data.get("position_heat")  or data.get("positionHeat")  or 0)
    killed     = bool(data.get("kill_switch")      or data.get("killSwitch")    or False)

    r.data.update({"daily_loss_pct": daily_loss, "drawdown_pct": drawdown, "position_heat": heat, "kill_switch": killed})
    r.add(f"Daily Loss:     {daily_loss:.2f}% (limit 5%)")
    r.add(f"Drawdown:       {drawdown:.2f}% (limit 10%)")
    r.add(f"Position Heat:  {heat:.1f}% (limit 80%)")
    r.add(f"Kill Switch:    {'🔴 ARMED' if killed else '🟢 SAFE'}")

    if killed:
        return r.fail("KILL SWITCH ARMED")
    if daily_loss > 4 or drawdown > 8 or heat > 70:
        return r.warn("CRITICAL LEVELS")
    if daily_loss > 2 or drawdown > 5 or heat > 50:
        return r.warn("WARNING LEVELS")
    return r.pass_("NOMINAL")


def check_signals_24h() -> CheckResult:
    r = CheckResult("Signals & Trades (24h)")
    code, data = http_get(f"{ENGINE_URL}/scan")
    if code != 200:
        return r.fail("ENGINE DOWN").add("Cannot retrieve signals")

    signals = data if isinstance(data, list) else data.get("signals", data.get("data", []))
    if not isinstance(signals, list):
        return r.warn("UNKNOWN FORMAT").add(f"Unexpected /scan response type")

    # Count signals in last 24h
    now = time.time()
    cutoff = now - 86400
    recent = []
    for s in signals:
        ts_raw = s.get("timestamp") or s.get("created_at") or ""
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
            if ts >= cutoff:
                recent.append(s)
        except Exception:
            recent.append(s)  # include if we can't parse timestamp

    # Direction breakdown
    longs  = sum(1 for s in recent if (s.get("direction") or s.get("side") or "").upper() == "LONG")
    shorts = sum(1 for s in recent if (s.get("direction") or s.get("side") or "").upper() == "SHORT")

    r.data.update({"signals_24h": len(recent), "longs": longs, "shorts": shorts})
    r.add(f"Signals fired (24h): {len(recent)}")
    r.add(f"  LONG:  {longs}")
    r.add(f"  SHORT: {shorts}")

    # Journal trades
    j_code, j_data = http_get(f"{ENGINE_URL}/journal")
    if j_code == 200:
        trades = j_data if isinstance(j_data, list) else j_data.get("trades", j_data.get("data", []))
        if isinstance(trades, list):
            recent_trades = []
            for t in trades:
                ts_raw = t.get("exit_time") or t.get("exitTime") or t.get("closed_at") or ""
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
                    if ts >= cutoff:
                        recent_trades.append(t)
                except Exception:
                    pass
            wins  = sum(1 for t in recent_trades if float(t.get("pnl") or t.get("realized_pnl") or 0) > 0)
            total_pnl = sum(float(t.get("pnl") or t.get("realized_pnl") or 0) for t in recent_trades)
            r.data.update({"trades_24h": len(recent_trades), "wins_24h": wins, "pnl_24h": total_pnl})
            r.add(f"Trades closed (24h): {len(recent_trades)}")
            if recent_trades:
                r.add(f"  Wins:  {wins} / {len(recent_trades)}")
                r.add(f"  P&L:   ${total_pnl:+.2f}")

    return r.pass_("OK")


def check_performance() -> CheckResult:
    r = CheckResult("Performance Metrics")
    code, data = http_get(f"{ENGINE_URL}/performance")
    if code != 200:
        return r.fail("ENGINE DOWN").add("Cannot retrieve performance data")

    if not isinstance(data, dict):
        return r.warn("UNEXPECTED FORMAT")

    total_return_pct = float(data.get("total_return_pct") or data.get("totalReturnPct") or data.get("return_pct") or 0)
    sharpe           = float(data.get("sharpe_ratio")     or data.get("sharpeRatio")     or data.get("sharpe")     or 0)
    max_dd_pct       = float(data.get("max_drawdown_pct") or data.get("maxDrawdownPct")  or data.get("drawdown_pct") or 0)
    win_rate         = float(data.get("win_rate")         or data.get("winRate")          or 0)
    total_trades     = int(data.get("total_trades")       or data.get("totalTrades")      or data.get("num_trades") or 0)
    open_positions   = int(data.get("open_positions")     or data.get("openPositions")    or data.get("num_open")   or 0)

    r.data.update({"return_pct": total_return_pct, "sharpe": sharpe, "max_dd_pct": max_dd_pct, "win_rate": win_rate, "total_trades": total_trades, "open_positions": open_positions})
    r.add(f"Total Return:    {total_return_pct:+.2f}%")
    r.add(f"Sharpe Ratio:    {sharpe:.2f}")
    r.add(f"Max Drawdown:    {max_dd_pct:.2f}%")
    r.add(f"Win Rate:        {win_rate:.1f}%")
    r.add(f"Total Trades:    {total_trades}")
    r.add(f"Open Positions:  {open_positions}")

    if max_dd_pct > 15:
        return r.warn("HIGH DRAWDOWN")
    if sharpe < 0:
        return r.warn("NEGATIVE SHARPE")
    return r.pass_("OK")


def check_binance_testnet() -> CheckResult:
    r = CheckResult("Binance Futures Testnet")

    if not TESTNET_API_KEY or not TESTNET_SECRET:
        return r.warn("NO CREDENTIALS").add("Set BINANCE_FUTURES_TESTNET_API_KEY and _SECRET in .env")

    # Account balance
    code, data = binance_signed_get("/fapi/v2/account", {})
    if code == -1:
        return r.warn("NO CREDENTIALS").add(data.get("error", ""))
    if code != 200:
        return r.fail(f"HTTP {code}").add(f"Could not reach testnet: {TESTNET_BASE_URL}")

    if isinstance(data, dict):
        total_wallet  = float(data.get("totalWalletBalance", 0))
        unrealized_pnl = float(data.get("totalUnrealizedProfit", 0))
        total_equity  = float(data.get("totalMarginBalance", 0))
        available     = float(data.get("availableBalance", 0))

        r.data.update({"wallet_balance": total_wallet, "unrealized_pnl": unrealized_pnl, "total_equity": total_equity, "available": available})
        r.add(f"Wallet Balance:   ${total_wallet:,.2f} USDT")
        r.add(f"Unrealized P&L:   ${unrealized_pnl:+,.2f} USDT")
        r.add(f"Total Equity:     ${total_equity:,.2f} USDT")
        r.add(f"Available:        ${available:,.2f} USDT")

        # Open positions
        positions = [p for p in data.get("positions", []) if float(p.get("positionAmt", 0)) != 0]
        r.data["open_positions"] = len(positions)
        r.add(f"Open Positions:   {len(positions)}")
        for pos in positions[:5]:  # show up to 5
            sym  = pos.get("symbol", "?")
            amt  = float(pos.get("positionAmt", 0))
            upnl = float(pos.get("unrealizedProfit", 0))
            r.add(f"  {sym}: {amt:+.4f} | uPnL ${upnl:+.2f}")

    return r.pass_("CONNECTED")


def check_recording_daemon() -> CheckResult:
    r = CheckResult("Recording Daemon")

    # Try the engine's recording endpoint first
    code, data = http_get(f"{ENGINE_URL}/recording")
    if code == 200 and isinstance(data, dict):
        eps      = data.get("events_per_second") or data.get("eventsPerSecond") or 0
        total    = data.get("total_events")       or data.get("totalEvents")      or 0
        size     = data.get("data_size")          or data.get("dataSize")         or "unknown"
        uptime   = data.get("uptime")             or "unknown"
        hb       = data.get("last_heartbeat")     or data.get("lastHeartbeat")    or "unknown"
        conns    = data.get("exchange_connections") or data.get("exchangeConnections") or []

        r.data.update({"eps": eps, "total_events": total, "data_size": size, "uptime": uptime})
        r.add(f"Events/sec:      {eps}")
        r.add(f"Total Events:    {total:,}")
        r.add(f"Data Size:       {size}")
        r.add(f"Uptime:          {uptime}")
        r.add(f"Last Heartbeat:  {hb}")

        if conns:
            r.add("Exchange Connections:")
            for c in conns:
                name    = c.get("name", "?")
                status  = c.get("status", "?")
                latency = c.get("latency", "?")
                icon = "✓" if status == "connected" else "⚠" if status == "degraded" else "✗"
                r.add(f"  {icon} {name}: {status} ({latency} ms)")

        degraded = sum(1 for c in conns if c.get("status") == "degraded")
        disconnected = sum(1 for c in conns if c.get("status") == "disconnected")
        if disconnected > 0:
            return r.warn(f"{disconnected} DISCONNECTED")
        if degraded > 0:
            return r.warn(f"{degraded} DEGRADED")
        return r.pass_("HEALTHY")

    # Fallback: check if recorder process is running via /proc
    try:
        recorder_pids = []
        for pid_dir in Path("/proc").iterdir():
            if not pid_dir.name.isdigit():
                continue
            try:
                cmdline = (pid_dir / "cmdline").read_text().replace("\x00", " ")
                if "recorder" in cmdline.lower() or "recording" in cmdline.lower():
                    recorder_pids.append(pid_dir.name)
            except Exception:
                pass

        if recorder_pids:
            r.add(f"Recorder process PIDs: {', '.join(recorder_pids)}")
            return r.pass_("PROCESS RUNNING")
        else:
            r.add("No recorder process found in /proc")
            return r.warn("NOT DETECTED")
    except Exception as e:
        return r.warn("CHECK FAILED").add(str(e))


# ─── Report rendering ─────────────────────────────────────────────────────────

def render_report(checks: list[CheckResult], elapsed: float) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = []

    lines.append("")
    lines.append(bold("╔══════════════════════════════════════════════════════════╗"))
    lines.append(bold("║         CoinScopeAI Daily Status Report                 ║"))
    lines.append(bold(f"║  {now_utc}                        ║"))
    lines.append(bold("╚══════════════════════════════════════════════════════════╝"))
    lines.append("")

    all_ok = all(c.ok for c in checks)
    critical = [c for c in checks if not c.ok]
    warnings = [c for c in checks if c.ok and c.status not in ("OK", "RUNNING", "CONNECTED", "HEALTHY", "ALL OK", "NOMINAL")]

    if all_ok and not warnings:
        lines.append(green(bold("  ✅  ALL SYSTEMS NOMINAL")))
    elif critical:
        lines.append(red(bold(f"  🚨  {len(critical)} CRITICAL ISSUE(S) DETECTED")))
    else:
        lines.append(yellow(bold(f"  ⚠️   {len(warnings)} WARNING(S)")))

    lines.append("")
    lines.append(dim("─" * 62))

    for c in checks:
        if c.ok and c.status in ("OK", "RUNNING", "CONNECTED", "HEALTHY", "ALL OK", "NOMINAL"):
            status_str = green(f"[{c.status}]")
        elif not c.ok:
            status_str = red(f"[{c.status}]")
        else:
            status_str = yellow(f"[{c.status}]")

        lines.append(f"  {bold(c.name):<40} {status_str}")
        for detail in c.details:
            lines.append(f"    {dim(detail)}")
        lines.append("")

    lines.append(dim("─" * 62))
    lines.append(dim(f"  Completed in {elapsed:.1f}s"))
    lines.append("")
    return "\n".join(lines)


def render_telegram(checks: list[CheckResult]) -> str:
    """Compact Telegram message (HTML — avoids Markdown parse errors with emoji variation selectors)."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    all_ok = all(c.ok for c in checks)
    critical = [c for c in checks if not c.ok]
    warnings = [c for c in checks if c.ok and c.status not in ("OK", "RUNNING", "CONNECTED", "HEALTHY", "ALL OK", "NOMINAL")]

    if all_ok and not warnings:
        header = "\u2705 <b>CoinScopeAI \u2014 All Systems Nominal</b>"
    elif critical:
        header = f"\U0001f6a8 <b>CoinScopeAI \u2014 {len(critical)} Critical Issue(s)</b>"
    else:
        header = f"\u26a0 <b>CoinScopeAI \u2014 {len(warnings)} Warning(s)</b>"

    lines = [header, f"<i>{now_utc}</i>", ""]

    for c in checks:
        icon = "\u2705" if (c.ok and c.status in ("OK", "RUNNING", "CONNECTED", "HEALTHY", "ALL OK", "NOMINAL")) else ("\U0001f534" if not c.ok else "\u26a0")
        lines.append(f"{icon} <b>{c.name}</b>: <code>{c.status}</code>")
        # Add key data points only
        for detail in c.details[:3]:
            lines.append(f"  \u2022 {detail}")

    # Add key metrics summary
    perf_check = next((c for c in checks if c.name == "Performance Metrics"), None)
    risk_check = next((c for c in checks if c.name == "Risk Gate"), None)
    testnet_check = next((c for c in checks if c.name == "Binance Futures Testnet"), None)

    lines.append("")
    lines.append("<b>\U0001f4ca Key Metrics</b>")
    if perf_check and perf_check.data:
        d = perf_check.data
        lines.append(f"  Return: <code>{d.get('return_pct', 0):+.2f}%</code> | Sharpe: <code>{d.get('sharpe', 0):.2f}</code> | Win Rate: <code>{d.get('win_rate', 0):.1f}%</code>")
    if risk_check and risk_check.data:
        d = risk_check.data
        ks = "\U0001f534 ARMED" if d.get("kill_switch") else "\U0001f7e2 SAFE"
        lines.append(f"  Daily Loss: <code>{d.get('daily_loss_pct', 0):.2f}%</code> | Drawdown: <code>{d.get('drawdown_pct', 0):.2f}%</code> | Kill Switch: {ks}")
    if testnet_check and testnet_check.data:
        d = testnet_check.data
        lines.append(f"  Wallet: <code>${d.get('wallet_balance', 0):,.2f}</code> | uPnL: <code>${d.get('unrealized_pnl', 0):+,.2f}</code>")

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(yellow("  [WARN] Telegram not configured — skipping notification"))
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(red(f"  [ERROR] Telegram send failed: {e}"))
        return False


def save_log(report: str) -> Path:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"status_{ts}.log"
    # Strip ANSI codes for log file
    import re
    clean = re.sub(r"\033\[[0-9;]*m", "", report)
    log_path.write_text(clean)
    return log_path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="CoinScopeAI Daily Status Check")
    parser.add_argument("--log",      action="store_true", help="Save report to logs/ directory")
    parser.add_argument("--telegram", action="store_true", help="Send summary to Telegram bot")
    parser.add_argument("--json",     action="store_true", help="Output raw JSON (for machine parsing)")
    args = parser.parse_args()

    print(dim("  Running checks…"))
    t_start = time.time()

    checks = [
        check_engine(),
        check_engine_endpoints(),
        check_risk_gate(),
        check_signals_24h(),
        check_performance(),
        check_binance_testnet(),
        check_recording_daemon(),
    ]

    elapsed = time.time() - t_start

    if args.json:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "all_ok": all(c.ok for c in checks),
            "elapsed_s": round(elapsed, 2),
            "checks": [{"name": c.name, "ok": c.ok, "status": c.status, "details": c.details, "data": c.data} for c in checks],
        }
        print(json.dumps(output, indent=2))
        return 0 if all(c.ok for c in checks) else 1

    report = render_report(checks, elapsed)
    print(report)

    if args.log:
        log_path = save_log(report)
        print(dim(f"  Report saved to: {log_path}"))

    if args.telegram:
        tg_text = render_telegram(checks)
        ok = send_telegram(tg_text)
        if ok:
            print(green("  ✓ Telegram notification sent"))
        else:
            print(red("  ✗ Telegram notification failed"))

    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())

# Telegram Alerts

**Status:** current
**Audience:** operators configuring alerts and developers adding new alert types
**Related:** [`../backend/configuration.md`](../backend/configuration.md), [`../risk/failsafes-and-kill-switches.md`](../risk/failsafes-and-kill-switches.md), [`binance-adapter.md`](binance-adapter.md)

Telegram is the engine's primary push-alert channel. It is intentionally simple — one bot, one chat, plain text with light Markdown. No dashboards, no threads, no custom keyboards.

## Configuration

| Env var | Purpose | Validation-era value |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | HTTP bot token from BotFather. | Required; no default. |
| `TELEGRAM_CHAT_ID` | Target chat for all alerts. | `7296767446` (operator DM). |
| `TELEGRAM_ENABLED` | Master kill for alert sending. | `true` in validation. Flip to `false` for local development. |
| `TELEGRAM_ALERT_MIN_SEVERITY` | Minimum severity to send. | `info` in validation (send everything). |

The bot is `@ScoopyAI_bot`. Chat ID 7296767446 is the operator's DM thread; no group chat is configured today.

## What triggers an alert

Every alert type has a fixed severity and a fixed template. Severity is advisory to the operator — it does not change engine behavior.

### critical — drop-everything events

| Trigger | Template |
| --- | --- |
| Max-drawdown breaker trip | `CRITICAL: max drawdown breaker tripped. Peak $X → trough $Y (-Z%). Engine is halted. Acknowledge via /circuit-breaker/reset with a reason.` |
| Kill switch engaged by operator | `CRITICAL: kill switch engaged. Reason: <reason>. New entries blocked; existing positions retained.` |
| Adapter banned (HTTP 418) | `CRITICAL: Binance adapter returned 418 (banned). Engine halting orders. Check IP and recent request history.` |
| Boot failure | `CRITICAL: engine failed to start. <error-summary>. Check the journal and restart.` |

### warn — watch-and-see

| Trigger | Template |
| --- | --- |
| Daily-loss breaker trip | `WARN: daily loss limit hit (-X%). Auto-resets at 00:00 UTC. Review today's journal.` |
| Consecutive-losses breaker trip | `WARN: consecutive-losses breaker tripped (N in a row). Auto-resets in 24h.` |
| WebSocket reconnect | `WARN: Binance WS reconnected on <stream>. N reconnects in last hour.` |
| Stream gap | `WARN: stream gap on <stream> — Xs since last message (threshold Ys).` |
| Alpha-decay warning | `WARN: observed edge below <THRESHOLD>% of historical for <window>. Consider pausing.` |
| REST 5xx burst | `WARN: Binance REST errors 5xx spike — N in last minute.` |

### info — routine journaling

| Trigger | Template |
| --- | --- |
| Regime flip (daily summary, not per-symbol) | `INFO: regime summary 24h — HMM: bull/bear/chop breakdown; v3: trending/mean-rev/volatile/quiet.` |
| Breaker reset | `INFO: <breaker> reset. Engine accepting entries again.` |
| Daily P&L snapshot (once/day at 00:05 UTC) | `INFO: daily P&L: $X (N trades, win rate Y%, avg RR Z).` |

Info-level alerts are suppressed if `TELEGRAM_ALERT_MIN_SEVERITY=warn` or higher.

## Format conventions

- **One alert, one message.** No threading; operators can scroll.
- **Leading severity token in CAPS.** `CRITICAL:`, `WARN:`, `INFO:`. Easier to scan than colored emoji on a phone lock screen.
- **Absolute numbers, not percentages alone.** `-$47 (-2.3%)`, not `-2.3%`.
- **UTC timestamps only.** The operator's local tz is the operator's problem.
- **No links to the dashboard in alert bodies.** The dashboard may be down during an incident; operators know the URL.

## Rate limiting and deduplication

The alert sender enforces:

1. **Per-alert-type throttle.** A given alert type (e.g., "WebSocket reconnect") will not fire more than `TELEGRAM_PER_TYPE_COOLDOWN_SECONDS` (default 60s) in a row. Subsequent occurrences increment a counter that's flushed once per minute.
2. **Global burst cap.** Hard cap of 30 messages/minute. Above that, alerts are dropped with a single summary "N alerts suppressed" message at the end of the minute.
3. **Dedup on message content.** Identical message bodies sent within `TELEGRAM_DEDUP_WINDOW_SECONDS` (default 30s) are collapsed.

These exist because the first live outage saturated the operator's phone with 400 reconnect notifications in 20 seconds, which was worse than no alerts.

## Failure modes

- **Bot token revoked.** The send path fails with 401; the engine logs and increments `engine_telegram_send_failures_total` but keeps trading. Alerts stop until the operator issues a new token.
- **Chat ID wrong.** 400 errors on every send. Same behavior — log and continue.
- **Telegram outage.** Sends fail; journal still records everything. Operator reads the journal once connectivity returns.

**Rule:** Telegram failures never gate trading. The journal is authoritative; alerts are courtesy.

## Testing

The alert path has a dry-run mode:

```bash
TELEGRAM_DRY_RUN=true python -m scripts.telegram_smoke
```

This logs the exact message that *would* be sent to stdout without hitting Telegram. Useful when developing new alert types.

Unit tests for templating, throttling, and severity gating live at `coinscope_trading_engine/tests/test_telegram_*.py`.

## Adding a new alert type

1. Define the trigger event in the emitting module (usually a risk or adapter module).
2. Add a template constant to `coinscope_trading_engine/notifications/templates.py` with an explicit severity.
3. Wire the trigger to call `telegram.send(event_type, payload)`.
4. Add a unit test that asserts the rendered message text given a sample payload.
5. Add the row to this doc's trigger table, or the doc drifts.

## Observability

- `engine_telegram_send_total{severity, result}` — counts sends by severity and by success/failure.
- `engine_telegram_send_failures_total{reason}` — buckets of failure reasons.
- `engine_telegram_suppressed_total{reason}` — counts of suppressed messages due to throttle, dedup, or severity filter.

If sends succeed but alerts are not arriving, check the operator's Telegram client first (muted chat, airplane mode) before assuming a server-side issue.

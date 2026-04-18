# Daily Ops Runbook

**Status:** current
**Audience:** operators monitoring the engine day-to-day during validation
**Related:** [`../risk/failsafes-and-kill-switches.md`](../risk/failsafes-and-kill-switches.md), [`../ops/telegram-alerts.md`](../ops/telegram-alerts.md), [`troubleshooting.md`](troubleshooting.md), [`../api/backend-endpoints.md`](../api/backend-endpoints.md)

A minimal daily routine for the 30-day validation window (2026-04-10 → 2026-04-30). Intentionally short. "Do less" is a feature.

## Once per day — morning check (5 minutes)

Before market open-style volatility (09:00–10:00 UTC is typical kickoff):

1. **Engine health.**
   ```
   curl https://<engine-host>/health
   curl https://<engine-host>/ready
   ```
   Both should return 200 with `"status":"ok"`. `/ready` also tells you adapter and artifact state.

2. **Breaker state.**
   ```
   curl https://<engine-host>/risk-gate
   ```
   Confirm `breaker.state` is `"ok"` for all three breakers and `kill_switch.engaged` is `false`.

3. **Yesterday's P&L, if there was activity.**
   ```
   curl https://<engine-host>/performance/daily?days=7
   ```
   Read the last-day number. If the week shows a pattern you don't like, tag it in the validation journal; do not react within the day.

4. **Telegram confirmation.** Confirm the daily P&L INFO alert fired at 00:05 UTC. If it didn't, the worker likely isn't running.

That is the daily routine. Everything else is event-driven.

## Event-driven — when a Telegram alert fires

### CRITICAL: max drawdown breaker tripped

1. **Do not reset immediately.** The breaker is doing its job.
2. Read the journal for the last 24h: `GET /journal?event_type=pnl_update&limit=100`.
3. Identify the trades that drove the drawdown. Were they one outlier or a pattern?
4. Decide: resume, scale down (halve `KELLY_FRACTION`), or pause pending strategy review.
5. If resuming: `POST /circuit-breaker/reset` with a written reason. That reason is journaled and read by the next reviewer — make it useful.
6. Open an incident doc at `docs/incidents/incident-max-dd-<YYYY-MM-DD>.md` using [`troubleshooting.md`](troubleshooting.md) as a reference.

### CRITICAL: kill switch engaged

This only fires because *you* engaged it. If you didn't, someone with credentials did. Treat as a security event — rotate credentials and audit.

### CRITICAL: adapter banned (HTTP 418)

1. Engine is already halted for orders.
2. Check Binance status page.
3. Check recent request history in logs. Was a script loose?
4. Wait for the ban to clear (Binance publishes the duration in the error response).
5. When cleared, confirm `/ready` reports adapter healthy, then release the kill switch if you engaged it.

### WARN: daily loss breaker tripped

Auto-resets at 00:00 UTC. Your job today:

1. Read `/journal?event_type=gate_decision&limit=200`. Are the rejects clustered on a regime flip?
2. Read `/performance/daily?days=1`. What was the loss composition (count of losing trades, average size)?
3. Decide whether to leave the strategy alone or tighten `SIGNAL_MIN_SCORE` for the next day.

### WARN: consecutive-losses breaker

Auto-resets in 24h. Re-read the four losses. Was there a common regime, symbol, or hour? Tag in the validation journal.

### WARN: WebSocket reconnect / stream gap

If isolated: ignore. If repeating: check [`../runbooks/incident-binance-ws-disconnect-2026-04-18.md`](incident-binance-ws-disconnect-2026-04-18.md) — we've seen this pattern before. If gaps exceed 60 seconds regularly, engage the kill switch and investigate before letting the engine keep trading on possibly-stale data.

### WARN: alpha-decay warning

Advisory. Don't react today — note it in the validation journal and revisit at the end of the week. If decay persists for three consecutive days, that is a signal to pause, not a direct trigger.

## Weekly — end-of-week review (20 minutes)

Every Sunday (or the last active trading day of the week):

1. **P&L and hit rate.**
   ```
   curl https://<engine-host>/performance?window=7d
   ```
   Write the number into `docs/validation/week-NN.md`. Template lives in the same folder.

2. **Breaker trips.** Count of daily-loss, max-dd, and consecutive-losses trips. Zero is not required; repeated is a signal.

3. **Regime distribution.** `GET /regime/BTCUSDT` at various points during the week. Is the HMM pinned? If yes, the model may need retraining post-validation.

4. **Stream health.** Count of reconnects and gap-seconds from `/metrics`. A drift upward is an infra signal, not a strategy signal.

5. **Open questions.** Add any "what happened here" items to the weekly doc. These feed the post-validation review.

## Things you should not do during validation

- **Do not change risk thresholds.** `MAX_DAILY_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `MAX_LEVERAGE`, `KELLY_FRACTION`, `KELLY_HARD_CAP_PCT`, regime multipliers — all locked. A PR to change them will fail review.
- **Do not retrain models.** Artifacts are frozen for the validation window. Drift is recorded, not corrected.
- **Do not flip `BINANCE_TESTNET` to `false`.** Not during validation. Ever. The release checklist blocks it.
- **Do not disable an alert because it's noisy.** If an alert is too noisy, the fix is the throttle or the trigger threshold, not a silence flag.
- **Do not restart the engine to "clear" a breaker.** Breaker state is persisted. Restarting does not clear it; use the reset endpoint.

## Things you should journal

Every time you touch the engine manually (reset a breaker, toggle the kill switch, restart, run a script against production), write one line into `docs/validation/operator-log.md`:

```
2026-04-18 14:22 UTC — reset daily-loss breaker at 00:15 UTC after daily rollover; no changes to config.
```

At the end of validation this log is reviewed end-to-end. Missing entries are worse than terse ones.

## What `current` looks like, in one command

```
curl -s https://<engine-host>/health \
  && curl -s https://<engine-host>/ready \
  && curl -s https://<engine-host>/risk-gate | jq '.breaker.state, .kill_switch.engaged' \
  && curl -s https://<engine-host>/performance/daily?days=1 | jq '.pnl'
```

If that block runs without error and the numbers look sane, you are done for the morning.

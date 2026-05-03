---
name: kill-switch-protocol
description: Codified halt sequence for CoinScopeAI. Use when ANY of the kill-switch conditions trigger (drawdown threshold breached, daily loss limit hit, repeated risk-gate rejections, vendor health red, suspected exploit). Walks through the 4-step halt — assess, halt, alert, postmortem-stub — with the exact Engine API calls, Telegram alert format, and journal entry template. Capital-preservation-first.
---

# Kill-Switch Protocol

Capital preservation > everything. When in doubt, halt. False halts are reversible; missed halts can blow up the account.

## When to use

A kill-switch trigger fires when **ANY** of these happen:

| Trigger | Condition | Source |
|---|---|---|
| **DD-1** | Account drawdown ≥ 10% | risk_gate, hard stop |
| **DD-2** | 24h rolling loss ≥ 5% | risk_gate, halt trading |
| **EXPOSURE** | Total notional exposure > 80% heat cap | position sizer |
| **REJECTIONS** | ≥ 5 risk-gate rejections in 60 minutes | journal scan |
| **VENDOR-RED** | Per-provider health red for ≥ 1 minute | observability |
| **EXPLOIT** | Anomalous fill, unauthorized API call, or leaked credential | manual / alerts |
| **WS-DROP** | Binance WebSocket disconnected ≥ 30s with no reconnect | binance_websocket_client |

If you're not sure whether a trigger has fired: **halt anyway**, document the reason, decide later.

## The 4-step protocol

### Step 1 — ASSESS (30 seconds)

Before halting, capture the state. Do **not** skip this — the halt decision needs a record.

```bash
# Pull the current engine state
curl -s http://localhost:8001/risk-gate | jq .
curl -s http://localhost:8001/performance | jq .
curl -s http://localhost:8001/journal?limit=20 | jq .
```

Capture:
- Current PnL (24h, all-time)
- Open positions (symbol, size, leverage, unrealized PnL)
- Last 5 risk-gate decisions
- Per-provider health snapshot

If the engine API is unreachable, that itself is a halt-worthy signal — go straight to Step 2.

### Step 2 — HALT (10 seconds)

Two ways to halt, in order of preference:

**A. Soft halt (preferred)** — set the engine into halted state via API. Keeps existing positions; blocks new entries. Allows graceful close.

```bash
# Soft halt (proposed endpoint — implement if not yet present)
curl -X POST http://localhost:8001/halt -d '{"reason":"<trigger>", "operator":"scoopy"}'
```

**B. Hard halt (emergency only)** — kill the engine process. Use only if soft halt isn't responsive.

```bash
# Find the engine process
pgrep -f coinscope_trading_engine
# Kill (SIGTERM first, SIGKILL if it hangs)
pkill -TERM -f coinscope_trading_engine
sleep 5
pgrep -f coinscope_trading_engine && pkill -KILL -f coinscope_trading_engine
```

**C. Exchange-side halt (last resort)** — log into Binance Testnet and close all open positions manually. Use only if A and B fail and the account is bleeding.

### Step 3 — ALERT (1 minute)

Send a structured Telegram alert via @ScoopyAI_bot to chat ID 7296767446.

Template:
```
🛑 KILL-SWITCH TRIGGERED

Trigger: <DD-1 | DD-2 | EXPOSURE | REJECTIONS | VENDOR-RED | EXPLOIT | WS-DROP>
Time:    <UTC ISO timestamp>
Halt:    <SOFT | HARD | EXCHANGE>

State at halt:
  PnL 24h:    <%>
  Drawdown:   <%>
  Open pos:   <count>
  Total expo: <%>

Action: <what was done>
Reason: <one sentence>

Next steps:
  1. <decide on resume or stay halted>
  2. <postmortem within 24h>
```

Send via:
```bash
curl -s -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
  -d "chat_id=7296767446" \
  -d "text=$(cat <<'EOF'
... template body ...
EOF
)"
```

Bot token lives in `~/.zshrc` as `TELEGRAM_BOT_TOKEN`; do not hardcode.

### Step 4 — POSTMORTEM STUB (within 24h)

Write a dated incident note to `incidents/<YYYY-MM-DD>_<area>_<short-name>.md` using the existing template style (see `incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md` for reference).

Structure:

```markdown
# <Date> — <area> — <short-name>

**Severity:** <S1 | S2 | S3>
**Trigger:** <which one>
**Halt type:** <SOFT | HARD | EXCHANGE>
**Resolved:** <Yes | No, see follow-up>

## Timeline (UTC)

- HH:MM — <event>
- HH:MM — kill-switch triggered
- HH:MM — halt applied
- HH:MM — Telegram alert sent
- HH:MM — <resume or stay halted>

## Root cause

<one paragraph>

## Action items

- [ ] <fix> — <owner> — <due>
- [ ] <test that prevents recurrence>
- [ ] <update runbook if needed>

## Follow-up to project journal

Add an entry to `business-plan/_decisions/decision-log.md` if any threshold or
protocol changed as a result.
```

Drop the file in `~/Documents/Claude/Projects/CoinScopeAI/incidents/`.

## Resume conditions

After a halt, **don't resume on impulse**. Resume only when ALL of:

- [ ] Root cause identified and documented
- [ ] Per-provider health green for ≥ 5 minutes
- [ ] Trigger condition reverted (drawdown recovered, daily-loss window rolled, exposure brought down, etc.)
- [ ] If exploit/leaked-cred trigger: credentials rotated and new keys verified
- [ ] Postmortem stub committed
- [ ] Operator (you) explicitly confirms resume — not Scoopy autonomously

To resume:
```bash
curl -X POST http://localhost:8001/resume -d '{"operator":"<name>","reason":"<why now>"}'
```

## Hard rules

1. **Validation phase: testnet only.** Real-capital flip is gated by PCC v2 §8.
2. **No engine code changes during a halt.** Halt is for stopping; fixes happen on a feature branch and merge after the all-clear.
3. **Telegram alert is mandatory.** Even for soft halts. The chat is the canonical event log.
4. **Postmortem within 24h or escalate.** No "we'll get to it." If you can't write the postmortem the next day, the halt isn't really resolved.
5. **Capital preservation is the brand.** A false halt costs you a few hours of validation. A missed halt costs the account.

## Authoritative references

- `docs/risk/failsafes-and-kill-switches.md` — the engineering reference
- `docs/risk/risk-framework.md` — threshold definitions
- `docs/runbooks/incident-binance-ws-disconnect-2026-04-18.md` — example postmortem
- `business-plan/12-risk-compliance-trust.md` — risk register and audit posture
- `CLAUDE.md` — risk thresholds (drawdown 10%, daily loss 5%, leverage 10x, max open 3, heat cap 80%)

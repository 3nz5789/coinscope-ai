---
name: alerting-and-user-experience
description: Standardize how signals, gate decisions, and risk events surface to traders across Telegram (@ScoopyAI_bot) and the dashboard at coinscope.ai. Enforces a single payload schema, consistent severity tags, regime + confidence + gate visibility on every alert, and noise reduction (grouping, dedup, rate limits). Use when adding a new alert type, when an existing alert needs review for clarity or noise, when designing how a gated trade is explained to the user, or when a regime/risk event needs a user-facing format. Triggers on "alert format", "Telegram alert", "dashboard alert", "how should this surface to the user", "noisy alerts", "explain this gate fail to the user", "signal payload", "alert schema".
---

# Alerting and User Experience

The product tier rule: **risk controls are primary UI, never buried.** Every alert must let a trader answer "what, why, regime, confidence, risk, gate" in under 5 seconds.

## When to use

- Adding a new alert type (signal, gate fail, regime flip, cap breach, journal event).
- An existing alert is too noisy, too vague, or buries the risk context.
- Designing how a `/risk-gate` failure is explained to the trader (the "Why rejected?" template).
- Mapping engine events into Telegram + dashboard formats.
- Reviewing a personas P1/P2/P3 readability check (Omar / Karim / Layla).

## When NOT to use

- Marketing copy or social-tier output — wrong register; that's not Scoopy.
- Internal logs / journal entries that are not user-facing — those follow the journal schema, not the alert schema.

## The alert payload schema (canonical)

Every user-facing alert must populate these fields. Missing fields = malformed alert.

```yaml
alert_id: <ulid>
type: signal | gate_fail | regime_flip | cap_warning | cap_breach | journal_note
severity: info | warn | block
symbol: BTCUSDT
side: long | short | n/a
timestamp_utc: 2026-05-04T10:35:00Z
regime: Trending | Mean-Reverting | Volatile | Quiet
regime_confidence: 0.72       # [0,1]
gate_status: pass | fail | n/a
gate_first_fail: leverage | daily_loss | drawdown | heat | max_positions | regime_restriction | null
caps_snapshot:
  max_leverage: 10x
  daily_loss_used: 1.2%        # of 5% cap
  drawdown_used: 3.4%          # of 10% cap
  open_positions: 2            # of 5 cap
  heat: 42%                    # of 80% cap
explanation_template: signal | rejected | regime_change | warning
disclaimer: "Testnet only. 30-day validation phase. No real capital."
```

## Severity policy

| Severity | When | Channel behavior |
|---|---|---|
| `info` | Standard signal, regime flip, non-blocking journal note | Telegram silent, dashboard standard |
| `warn` | Cap >70% used, regime to Volatile, near-DD threshold | Telegram default sound, dashboard amber |
| `block` | Trade blocked by gate, cap breach, kill switch fired | Telegram priority, dashboard red, top of feed |

## Channel-specific rendering

### Telegram (@ScoopyAI_bot, Chat ID 7296767446)

Compact. Numbers tabular. No emoji. Always fits one screen.

```
SIGNAL  long BTC @ 67,420
score   8.5/12   regime Trending (0.72)
gate    pass     heat 42%   DD 3.4%
exit    TP 67,920 / SL 67,180   time 30m
why     RSI div + EMA cross + OI +2.1% / 1h
note    Testnet only. No real capital.
```

```
REJECTED  long ETH @ 3,180
gate      FAIL — daily_loss_limit
caps      DD 3.4% (cap 10%) | daily_loss 4.8% (cap 5%)
options   wait for daily reset | smaller size | close existing leg
note      Testnet only. No real capital.
```

### Dashboard (coinscope.ai)

Card layout. Numbers in tabular figures. Regime color from the v3 ML palette:
- Trending → mint `#00FFB8`
- Mean-Reverting → neutral `#A3ADBD`
- Volatile → amber `#F5A623`
- Quiet → muted `#5B6472`

Gate status shown as a 5-pill row (leverage / DD / daily_loss / heat / positions). The first-failing pill is solid; the rest are outlined.

## Noise reduction rules

1. **Dedup window**: same `symbol + side + type` within 60s collapses to one alert; the second fires "[+1 follow-up]" instead of a new payload.
2. **Group regime flips**: if 3+ symbols flip in the same 5m bar, fire one "regime sweep" alert, not N alerts.
3. **Cap-warning rate limit**: at most 1 cap-warning per cap per 4h.
4. **Block alerts always fire**: never deduped, never grouped — capital safety overrides noise reduction.

## Process

### Step 1 — Classify

Is this `signal | gate_fail | regime_flip | cap_warning | cap_breach | journal_note`? If you can't pick one, the alert isn't well-defined yet.

### Step 2 — Populate the schema

Every field. Missing → malformed.

### Step 3 — Apply the explanation template

| Template | Required fields |
|---|---|
| `signal` | why (3-5 features), regime, confidence, gate, exit plan |
| `rejected` | first-failing cap, current vs cap value, 2-3 safe alternatives |
| `regime_change` | old → new, confidence, what tightens (sizing, gate strictness) |
| `warning` | which cap, current %, threshold, projected breach time if linear |

### Step 4 — Pass the readability check

Read it as P1/Omar (self-taught), P2/Karim (engineer), P3/Layla (solo PM). All three must be able to act in <5s. If one of them needs help, the alert is too dense.

### Step 5 — Pass the noise-reduction check

Apply dedup, grouping, and rate-limit rules above. Block-severity alerts skip these checks.

## Output contract

- Filled YAML payload conforming to the schema above.
- Telegram render (compact, tabular, no emoji).
- Dashboard render (card with regime color, 5-pill gate row).
- One-line readability verdict per persona (Omar / Karim / Layla).

## Anti-patterns

- Emoji or marketing tone in product-tier alerts.
- Burying gate status below the "why" — risk visibility comes first.
- Inventing a severity not in {info, warn, block}.
- Skipping the disclaimer during the 30-day validation phase.
- Using social-tier copy ("Let's go!", "BTC is pumping!") — wrong register.

## Cross-references

- Brand voice + register rules: `CLAUDE.md` §Voice & tone, §Registers
- Risk caps: `skills/coinscopeai-trading-rules`
- Engine endpoints (data source): `skills/coinscopeai-engine-api`
- Regime palette: `CLAUDE.md` §Regime labels (v3 ML)
- Personas: `business-plan/03-personas.md` (P1 Omar, P2 Karim, P3 Layla)
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)

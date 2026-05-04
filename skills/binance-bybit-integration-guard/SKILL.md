---
name: binance-bybit-integration-guard
description: Own the robustness of CoinScopeAI's exchange integrations — REST/WebSocket clients, auth and signing, reconnect logic, error handling, and drift detection between local and exchange state. Binance USDT-M is in scope today (P0/P1, May–Jul 2026); Bybit is **deferred to P2 (Aug-Sep 2026)** per the phase map and is design-only until then. Use when reviewing or hardening exchange clients, when reconnect logic is failing, when local positions/balances drift from exchange truth, or when adding a new venue (P2+). Triggers on "exchange integration", "WebSocket reconnect", "ping pong", "signing logic", "HMAC", "position drift", "stale connection", "exchange health check", "Binance reliability", "Bybit integration".
---

# Binance / Bybit Integration Guard

Binance USDT-M is the only live venue during P0/P1. **Bybit work in this skill is design-only until P2.** This skill enforces that boundary explicitly.

## Phase boundaries (read first)

| Phase | Window | Venues live | What this skill does |
|---|---|---|---|
| P0 | May 2026 | Binance Testnet | Harden Binance integration, add health checks, design Bybit |
| P1 | Jun-Jul 2026 | Binance + CCXT 4-ex (per phase map) | Extend coverage, vendor expansion |
| P2 | Aug-Sep 2026 | Binance + Bybit + others | Bybit becomes live; cross-venue parity work begins |
| P5 | Mar-May 2027 | Multi-venue Desk Full v2 | Full institutional-grade resilience |

If you propose Bybit-live behavior earlier than P2, label it explicitly "P2-deferred design" and route the decision through `coinscopeai-premortem`.

## When to use

- Reviewing or hardening an exchange client (REST or WebSocket).
- WebSocket reconnect, backoff, or ping/pong is failing.
- Local position/balance state has drifted from exchange truth.
- Designing a new venue's integration (P2+).
- Auth, HMAC signing, or testnet/mainnet routing is suspect.
- Adding a synthetic probe / health check.

## When NOT to use

- Bybit *implementation* during P0/P1 — design only; gates on phase.
- Signal or risk logic — route to `signal-design-and-backtest` or `risk-and-position-manager`.
- Engine optimization — route to `scanner-engine-optimizer`.

## The reliability checklist (apply on every review)

### Connection layer

- [ ] WebSocket has explicit reconnect with exponential backoff (cap at e.g. 30s).
- [ ] Ping/pong honored per venue (Binance: server pings every 3m, client must pong within 10m).
- [ ] Stale-connection detector — if no message for N × bar-interval, force reconnect.
- [ ] Subscription state restored on reconnect (don't silently lose channels).
- [ ] Multiple connections allowed only if needed; otherwise one shared multiplexed stream.

### Auth + signing

- [ ] HMAC-SHA256 signing in a single shared helper, never duplicated.
- [ ] Timestamp drift handled (resync against server time on `-1021` or equivalent).
- [ ] Testnet vs mainnet routing controlled by a single env var; **never coexist in the same process**.
- [ ] API keys never logged; redaction tested.

### Error taxonomy

| Class | Example | Behavior |
|---|---|---|
| Transient | `-1003` rate limit, 5xx, network reset | Backoff + retry; alert if persistent >2min |
| Auth | `-1021` time skew, `-2014` bad signature | Resync clock, then escalate; never silent retry |
| Logic | `-2010` insufficient balance, `-4131` PERCENT_PRICE | Surface to caller; never retry |
| Unknown | New code we don't recognize | Surface + log + alert; default to safe (no retry) |

### State drift detection

- [ ] Synthetic probe: compare local position state to `/positionRisk` (Binance) on a cadence (e.g. every 60s).
- [ ] Drift > 1 contract or > $10 notional → fire `cap_warning` alert via `alerting-and-user-experience`.
- [ ] Reconciliation policy: exchange truth wins; local state corrected; incident logged in `/journal`.

### Health endpoints

- [ ] `/health/exchange/binance` — last message age, weight-usage %, reconnect count last 1h, drift status.
- [ ] Same shape for Bybit when it goes live at P2 (design now, don't implement).

## Process

### Step 1 — Identify the layer

Connection / auth / error / state drift / health? Different layer = different fix path.

### Step 2 — Reproduce or simulate

Use `test-and-simulation-lab` replay for any historical incident (data-gap class is the relevant one).

### Step 3 — Propose the fix

Cite the checklist row. If the row doesn't exist, propose adding it.

### Step 4 — Add or update the contract test

Every fix gets a contract test or replay-class entry — see `test-and-simulation-lab` Layer 2 / 3.

### Step 5 — Phase-gate the change

If the fix is Binance-only and not engine-internal, ship in-phase. If it touches the engine, follow the validation-phase rule (proposal-only). If it's Bybit-live, defer to P2.

## Anti-patterns

- Implementing Bybit-live behavior before P2.
- Silent retry on auth errors — masks clock skew or revoked keys.
- Letting testnet and mainnet share a process.
- Polling positions when a position-update WebSocket stream exists.
- Treating reconnect as a no-op for subscription state.
- Logging API keys, signatures, or the full sign-string.

## Output contract

- A reliability-checklist diff (which rows were added, modified, or now pass).
- A change proposal with phase label (in-phase / engine-frozen-proposal / P2-deferred).
- A contract or replay test reference from `test-and-simulation-lab`.
- A health-endpoint update if a new failure mode was introduced.

## Cross-references

- Binance specifics: `skills/binance-futures-api`
- Engine API + mock fallback: `skills/coinscopeai-engine-api`
- Risk caps (referenced in error taxonomy reasoning): `skills/coinscopeai-trading-rules`
- Tests + replays: `skills_src/test-and-simulation-lab`
- Phase map: `business-plan/14-launch-roadmap.md`
- Premortem before any irreversible integration change: `skills/coinscopeai-premortem`
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)

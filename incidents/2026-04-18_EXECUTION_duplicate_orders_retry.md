# [INCIDENT] EXECUTION — Duplicate Orders During Retry (2026-04-18)

**Status:** TABLETOP EXERCISE (hypothetical, no live event)
**Severity (if real):** SEV-1 — execution integrity breach, capital preservation class
**Environment:** Binance Testnet only (live trading remains prohibited)
**Author:** Scoopy
**Date:** 2026-04-18
**Validation Phase:** Day 8 of 30 (COI-41 in progress)

---

## 1. Summary (Scoopy Format)

A retry on the execution path caused the engine to submit the same order to Binance Testnet more than once, resulting in duplicate fills on the same symbol/side/qty within a short window. The account held more exposure than the risk gate authorised. This is a direct violation of capital preservation — if it happened on mainnet, it would uncap position heat and blow past the 80% deployed-capital ceiling without the gate catching it.

| Field | Value |
|---|---|
| Incident ID | INC-2026-04-18-01 |
| Title | [INCIDENT] EXECUTION — Duplicate Orders During Retry (2026-04-18) |
| Severity | SEV-1 |
| Detected by | (hypothetical — see §3 detection paths) |
| Impact | Position heat exceeded authorised size; duplicate client-side order records |
| Containment | Kill switch **ARMED**; new entries halted; open positions squared |
| Blast radius | Testnet only — zero real-capital loss |
| Engine change required? | YES → requires validation-freeze **waiver** (see §6) |

---

## 2. Hypothetical Timeline (UTC+3, Jordan)

| Time | Event |
|---|---|
| T+0:00 | `/scan` returns BUY signal on SOLUSDT (confidence 0.84) |
| T+0:01 | Executor calls `/position-size?symbol=SOLUSDT` → 500 USDT, 5x |
| T+0:02 | Executor submits `POST /fapi/v1/order` to Binance Testnet |
| T+0:07 | Network hiccup — HTTP request hangs past 5s client timeout |
| T+0:07 | Binance had already accepted the order; ACK never reached the executor |
| T+0:07 | Retry logic fires without checking "already-in-flight" state |
| T+0:08 | Second `POST /fapi/v1/order` lands; Binance accepts a fresh order (new `orderId`) |
| T+0:09 | Both orders fill; position size on SOLUSDT is now 2× intended |
| T+0:15 | `/journal` dual entry visible; `/risk-gate` reports `position_heat > 0.80` |
| T+0:16 | Alert fires via @ScoopyAI_bot; kill switch armed manually |
| T+0:30 | Positions squared, post-incident review begins |

---

## 3. Detection Paths (how we would have caught this)

Ordered by how fast each path surfaces the problem:

1. **`/risk-gate` position-heat breach** — the gate reports `> 80%` within one polling cycle after the duplicate fill. Fastest signal, but reactive (the breach already happened).
2. **`/journal` duplicate-key check** — two entries within N seconds, same symbol/side/qty, different `trade_id`. Can run as an offline watchdog.
3. **Binance account reconciliation** — `GET /fapi/v2/account` shows position size that exceeds what `/position-size` authorised. Slower but authoritative.
4. **Telegram alert on `orders_submitted` counter** — if the per-signal counter > 1, trip an alert. Cheap to add as an external monitor.

None of these detection paths require touching the core engine — all can be built as side-car observers against the existing API surface.

---

## 4. Root-Cause Investigation (starting from zero evidence)

Because no real evidence exists in this tabletop, I'm enumerating the candidate root causes ranked by prior probability for a retry-driven duplicate-order class of bug. Each is written as a testable hypothesis so the live playbook can triage quickly when a real incident lands.

### H1 — Missing idempotency key on order submission (HIGH prior)
The executor does not pass a stable `newClientOrderId` when calling Binance. Binance happily accepts a second order with the same economic intent because, from its side, the two requests are unrelated. Retry after a timeout produces a fresh order every time.
- **Test:** grep the executor for `newClientOrderId`. If absent or generated fresh per attempt (e.g. `uuid4()` inside the retry loop), H1 is confirmed.
- **Fix class:** Generate `newClientOrderId` *once per decision*, not per attempt. Reuse across retries. Binance will reject the duplicate with `-2010` / `-4015` (duplicate clientOrderId).

### H2 — Retry fires on ambiguous failure (HIGH prior)
The executor treats any non-2xx or any timeout as "not submitted" and retries. A client-side timeout that happens *after* Binance has acknowledged (but before our socket read) is indistinguishable from a true failure without a server-side confirmation.
- **Test:** trace a failed submission — does the executor reconcile against Binance's order book / open orders list before retrying? If no reconciliation step exists, H2 is confirmed.
- **Fix class:** Before retrying, call `GET /fapi/v1/openOrders` or `GET /fapi/v1/order?origClientOrderId=...` to check whether the prior attempt landed. Only retry on verified non-submission.

### H3 — WebSocket reconnect replays queued orders (MEDIUM prior)
The order-send path is coupled to the user-data WS stream. On reconnect, a queued "pending order" entity is re-submitted because the reconnect handler doesn't distinguish "never sent" from "sent, awaiting ACK".
- **Test:** force a WS reconnect during a live order and watch the journal. If a fresh `trade_id` appears, H3 is confirmed.
- **Fix class:** Decouple order submission from WS lifecycle. Orders should be submitted via REST with their own reconciliation loop; WS is for reading fills only.

### H4 — Exception in post-submit bookkeeping mistaken for submit failure (MEDIUM prior)
The order submits successfully, but a downstream step (journal write, Redis state update, Notion sync) throws, and the surrounding `try/except` routes into the retry path.
- **Test:** look at the try/except scope around `submit_order()`. If it wraps both the Binance call *and* the bookkeeping, H4 is plausible.
- **Fix class:** Tighten the exception boundary. Binance-call failure and bookkeeping failure are distinct classes and must not share a retry path.

### H5 — Parser throws on success response (LOW prior)
The response JSON shape changed (new Binance field, testnet vs mainnet drift), the parser raises, and the caller interprets this as failure and retries.
- **Test:** reproduce with a captured success response from the last 7 days; run it through the parser.
- **Fix class:** Parse defensively; log the raw response before interpretation.

### H6 — Clock drift / signed request replay (LOW prior)
A signed request with stale `timestamp` is rejected by Binance; retry with a fresh timestamp lands. In rare cases, the "rejected" first request was actually accepted before the rejection was emitted (unlikely on Binance, but documented on some exchanges).
- **Test:** check NTP drift on the host; compare Binance `-1021` errors in the log with subsequent successful fills within 5 seconds.
- **Fix class:** Keep `recvWindow` tight, but this is almost never the real cause on Binance.

**Most likely on CoinScopeAI given the architecture:** H1 + H2 in combination. The executor submits without a stable idempotency key, and the retry path doesn't reconcile. Either fix alone reduces risk; both together eliminate this class.

---

## 5. Impact Assessment

| Dimension | Impact |
|---|---|
| Real capital | **None** — testnet only |
| Testnet P&L | Skewed: duplicate fills pollute the 30-day validation sample |
| Validation clock | **COI-41 clean-day counter resets to 0** — 7 consecutive clean days required before staging consideration |
| Risk gate | `position_heat > 80%` briefly breached — captured, but reactive not preventive |
| Trust in execution layer | Downgraded until fix lands — all signals routed through a stricter gate |
| Journal integrity | Two journal entries exist for one logical decision — reporting/backtesting must dedupe |

---

## 6. Fix Plan (respecting the validation freeze)

The validation-phase rule says **no core engine changes**. Duplicate-order execution is a capital-preservation breach, so it qualifies for a formal waiver — but the fix should still be scoped as narrowly as possible and shipped in phases.

### Phase 0 — Immediate containment (no code change)
- **ARM** the kill switch via the existing mechanism.
- Halt new entries until Phase 1 monitoring is in place.
- Square any oversized position on testnet manually and reconcile `/journal`.
- Post incident notice to @ScoopyAI_bot and update the Notion OS entry.

### Phase 1 — External detection (no engine change)
Build outside the engine so the freeze holds:
- Side-car watchdog that polls `/journal` every 10s and flags two entries with identical `(symbol, side, qty)` inside a 30s window.
- External monitor that polls `/risk-gate` and pages on any `position_heat > 0.80` transition.
- Reconciliation job: compare `/journal` rows against Binance Testnet `GET /fapi/v1/allOrders` hourly; alert on divergence.

These observers add evidence without modifying the engine. They should exist regardless of whether a real H1/H2 fix ships.

### Phase 2 — Engine fix (requires waiver from validation freeze)
Scope the change to the smallest possible diff in the execution layer:
1. Generate `newClientOrderId` deterministically from `(signal_id, decision_timestamp)` — the same value on every retry of the same decision.
2. On retry, before re-submitting: call `GET /fapi/v1/order?origClientOrderId=...` — if the order exists, short-circuit and treat it as "already submitted."
3. Log every retry decision with `(client_order_id, attempt_number, reason)` for auditability.
4. Add a unit test that simulates a timeout-after-ACK and asserts only one Binance order is created.

**Waiver criteria to document before merging:**
- This change is scoped strictly to the execution path's retry logic.
- No signal, risk, or regime code is touched.
- Change is feature-flagged so it can be disabled without a redeploy.
- Clean-day counter resets regardless — this is a freeze exception, not a freeze break.

### Phase 3 — Validation gate re-entry
- 7 consecutive clean days required after Phase 2 lands before COI-41 can progress to the next milestone.
- Keep Phase 1 watchdogs running permanently — they cost almost nothing and catch a whole class of regressions.

---

## 7. Corrective Actions & Owners

| # | Action | Owner | Target |
|---|---|---|---|
| CA-1 | Arm kill switch, verify no open oversized positions on testnet | Mohammed | Immediate |
| CA-2 | Ship Phase 1 watchdog (journal duplicate detector) | Scoopy + Mohammed | T+48h |
| CA-3 | Ship Phase 1 reconciler (hourly Binance vs journal diff) | Scoopy + Mohammed | T+72h |
| CA-4 | Draft waiver memo for Phase 2 engine fix | Mohammed | T+48h |
| CA-5 | Implement deterministic `newClientOrderId` + retry reconciliation | Mohammed | T+5d post-waiver |
| CA-6 | Add retry-timeout-after-ACK unit test | Mohammed | With CA-5 |
| CA-7 | Reset COI-41 clean-day counter, log reset in Notion OS | Scoopy | After CA-5 lands |

---

## 8. Linear Issue Draft (file under project COI)

```
Title: [INCIDENT] EXECUTION — Duplicate Orders During Retry (2026-04-18)
Project: CoinScopeAI (COI)
Priority: Urgent (P0)
Labels: incident, execution, capital-preservation, validation-freeze-waiver-candidate
Parent / Blocks: COI-41 (30-Day Testnet Validation Phase)

Description:
  Tabletop exercise (2026-04-18) — retry path on order submission may
  produce duplicate Binance orders when a timeout occurs after the
  exchange has accepted the order but before the client reads the ACK.
  Real-capital impact: none (testnet only). Validation-phase impact:
  clean-day counter would reset.

Acceptance criteria:
  1. Phase 1 external watchdog + reconciler shipped and running.
  2. Waiver memo approved before any engine-path change.
  3. Deterministic newClientOrderId reused across all retries of the
     same decision.
  4. Pre-retry reconciliation against Binance open-orders endpoint.
  5. Unit test reproducing timeout-after-ACK passes with exactly one
     order created.
  6. COI-41 clean-day counter reset and documented.

Linked docs:
  - /CoinScopeAI/incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md
  - Waiver memo (TBD)

Estimate: 5d (Phase 2) + 3d (Phase 1 watchdogs, parallel)
```

---

## 9. Notion OS Update Draft

Entry for the CoinScopeAI OS incident log:

```
Date: 2026-04-18
Type: Incident (tabletop)
Area: EXECUTION
Title: Duplicate Orders During Retry
Severity: SEV-1 (hypothetical)
Status: Tabletop complete → Phase 1 watchdogs proposed
Linear: COI-??? (to be created)
Linked incident doc: /CoinScopeAI/incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md

Key takeaways:
  - Execution retry path lacks idempotency guard (H1) and post-timeout
    reconciliation (H2). These two together are the most likely real
    failure mode if this incident fires live.
  - Phase 1 fix (external watchdogs) can ship without touching the
    engine and should ship regardless — costs nothing, catches a class.
  - Phase 2 fix (engine patch) requires a formal freeze waiver. Capital
    preservation trumps freeze rigidity, but the waiver memo must be
    on record before any commit lands.
  - COI-41 clean-day counter behaviour: resets only on Phase 2 merge,
    not on Phase 1 external changes.
```

---

## 10. Lessons for the Playbook

1. **Freeze isn't absolute — it's a prior.** The freeze rule reduces change risk; duplicate orders reduce *capital* risk. When those two collide, capital wins, but the exception must be formal, documented, and scoped.
2. **External observers are freeze-compatible.** Any future "execution integrity" concern should first be instrumented outside the engine before touching the engine. Watchdogs are cheap insurance even when no incident is suspected.
3. **Idempotency is a trading-system primitive, not an optimisation.** Every order-submission path should carry a stable client-side ID. This belongs in the execution-layer design doc regardless of this incident.
4. **Timeout != not submitted.** Any retry logic that treats a client timeout as a hard "did-not-send" is a duplicate-order bug waiting to happen. Reconciliation before retry is the invariant.

---

*End of tabletop artifact. No live incident declared, no engine code modified.*

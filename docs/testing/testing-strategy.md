# Testing Strategy

**Status:** current
**Audience:** developers writing tests; reviewers assessing coverage
**Related:** [`local-validation-checklist.md`](local-validation-checklist.md), [`../risk/risk-gate.md`](../risk/risk-gate.md), [`../runbooks/local-development.md`](../runbooks/local-development.md)

How we test CoinScopeAI. The short version: unit tests for every risk and sizing path, fixture-driven integration tests for adapters and gates, and explicit replay tests for regressions. No mainnet in CI, ever.

## Test pyramid, in practice

```
           ┌──────────────────────┐
           │   Replay regression  │   <5% — hand-captured, targeted
           └──────────────────────┘
         ┌─────────────────────────┐
         │   Integration / system  │   ~20% — fixture-fed, Redis up
         └─────────────────────────┘
       ┌────────────────────────────┐
       │          Unit              │   ~75% — fast, isolated
       └────────────────────────────┘
```

The numbers are indicative, not targets. We do not tune the ratio; we follow what the code needs.

## Layers

### Unit tests — fast, isolated

Scope: one module, one function, mocked dependencies. Run in milliseconds each.

Where they matter most:

- **Position sizer** (`test_kelly_position_sizer*`). Every step of the 6-step pipeline, the monotone-non-increasing invariant, every regime multiplier, every clamp.
- **Risk gate** (`test_risk_gate*`). Every one of the 13 checks, in order. A rejection at check N means checks N+1..13 are not evaluated.
- **Scorer** (`test_scorer*`). Per-factor outputs, composition rules, boundary cases.
- **Adapter normalization** (`test_binance_adapter_normalize*`). For each stream, confirm normalization output matches the canonical shape.
- **Signing** (`test_binance_signing*`). HMAC output against known-good vectors.
- **Templating and throttling** (`test_telegram_*`). Alert rendering and the dedup/throttle logic.
- **Billing handlers** (`test_billing_*`). Every Stripe event type's state transition.

Rule: a unit test should not require Redis, Postgres, or network access. If it does, it has drifted into integration territory — move it.

### Integration tests — fixture-driven

Scope: multi-module paths that exercise real infrastructure (Redis, SQLite) but use recorded or synthetic data instead of live exchange feeds.

Examples:

- **Gate → sizer → executor stub**, verifying that an accepted candidate produces the right order triplet.
- **Webhook ingestion → mirror**, posting fixture Stripe events to `/billing/webhook` and asserting the database state.
- **Kill-switch end-to-end**, toggling via the API and verifying that the gate rejects immediately on subsequent candidates.

These tests live alongside unit tests but are tagged with `@pytest.mark.integration`. CI runs them in a separate stage with Redis up.

### Replay regression tests — targeted

Scope: a past incident or subtle bug, reproduced against recorded market data or fixture sequences.

Examples:

- **WS replay consistency** ([`qa-ws-replay-consistency-2026-04-16.md`](qa-ws-replay-consistency-2026-04-16.md)). Feed a recorded WS session and assert the derived kline/depth state matches the snapshot.
- **Daily-loss halt** ([`qa-risk-daily-loss-halt-2026-04-16.md`](qa-risk-daily-loss-halt-2026-04-16.md)). Script a series of losing trades and assert the breaker trips at the expected threshold and does not over-trip.
- **Billing dedup** ([`qa-billing-coi39-2026-04-15.md`](qa-billing-coi39-2026-04-15.md)). Replay a Stripe event burst and assert no double-apply.

Fixtures for replay tests live under `tests/fixtures/` and are committed. Adding a new replay test begins with capturing the fixture in a reproducible way.

## What every risk or execution PR must include

- A unit test for the specific branch you added.
- If the change touches the sizer pipeline: a fixture-over-regimes test that re-runs sizing against a battery of (edge, regime) combinations.
- If the change touches the gate: a test that asserts the ordering invariant (a rejection at check N does not invoke check N+1..13).
- If the change touches an adapter: a normalization test against at least one recorded message.

Reviewers will reject PRs that modify risk-critical code without tests. "Covered by integration tests" is not sufficient for a unit-testable change.

## What we do not test in CI

- **Live Binance.** CI never hits the exchange. Integration tests targeting the adapter run against recorded fixtures.
- **Live Stripe.** Same — webhooks come from fixtures.
- **Mainnet.** Mainnet is not a test environment. Mainnet-related changes are gated by release-checklist verification, not by CI.
- **End-to-end dashboard-to-engine.** The React dashboard is a separate repo; its tests live there.

## Mocking conventions

- **Mock Stripe at the SDK boundary.** `stripe.Webhook.construct_event` mocking is fine; don't mock deeper than that.
- **Do not mock the database in risk tests.** These tests hit a real SQLite in-memory db. Reason: mocked tests have silently drifted from real schema before (see [`../ops/exchange-integrations.md`](../ops/exchange-integrations.md) pattern — same lesson).
- **Do mock time.** Use `freezegun` or a test clock. Real `datetime.utcnow()` in tests is a flake source.
- **Do not mock the regime detector in gate tests.** Feed a fixture regime label directly. Mocking the detector produces tests that pass against bugs in the detector.

## Coverage expectations

- **Risk-critical code**: 100% branch coverage expected. Every gate check, every sizer step, every breaker condition, every adapter signing path.
- **API layer**: happy path + one failure mode per endpoint.
- **Billing handlers**: every event type has at least one fixture.
- **Non-critical utilities**: pragmatic; don't chase coverage for the sake of the percentage.

Coverage is reported per-PR but the number is not a gate by itself. A dropped coverage percentage prompts a conversation, not an auto-reject.

## Known flaky tests

Flaky tests are bugs. Current list is short and tracked:

- None at the moment. Previously the billing webhook replay test was flaky due to SQLite WAL behavior under parallel test runs; fixed 2026-04-11 by serializing its fixture.

If you find a flake: reproduce it, capture the flake mode, open a ticket, **and** add a `pytest.skip` with the ticket number. Don't `-k` it out of CI.

## Performance tests

We don't have a performance test suite. The engine's load profile is modest (one trading loop, a handful of streams). If a PR noticeably slows down boot or request handling, the reviewer will ask about it. A formal latency benchmark is in [`../product/implementation-backlog.md`](../product/implementation-backlog.md) for post-validation.

## Test data hygiene

- Fixtures under `tests/fixtures/` are committed. They are small by design.
- A fixture representing a real Binance message is redacted of any account-specific fields (keys, listen-keys).
- Fixtures referencing dates use dates in the past, not dynamic "now" — tests should be deterministic across machines and time.

## What a good PR test looks like

- Reads like documentation of the behavior being tested.
- Fails loudly with a meaningful assertion message when broken.
- Runs in under 100ms unless it's explicitly tagged integration.
- Does not depend on test ordering.
- Does not share state with other tests.

If a test needs a comment to explain what it's asserting, that's a sign the assertion itself should be clearer.

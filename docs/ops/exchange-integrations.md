# Exchange Integrations

**Status:** current
**Audience:** developers adding or modifying exchange adapters
**Related:** [`binance-adapter.md`](binance-adapter.md), [`../architecture/component-map.md`](../architecture/component-map.md)

The engine is written to support multiple exchanges, but today **only Binance is implemented**. Bybit, OKX, and Hyperliquid are planned for after validation. This doc describes the adapter contract, current status, and ground rules for adding a new adapter.

## Current state

| Exchange | Status | Notes |
| --- | --- | --- |
| Binance USDT-M Futures (testnet) | **current** | The only implemented adapter. All validation-era trading happens here. |
| Binance USDT-M Futures (mainnet) | planned | Adapter would support it; flipping `BINANCE_TESTNET=false` is blocked during validation and needs a runbook before ever enabling. |
| Bybit perpetuals | planned | Priority 1 for multi-exchange; closest API model to Binance. |
| OKX perpetuals | planned | Priority 2. |
| Hyperliquid | planned | Priority 3. On-chain account model; larger change. |

Any reference in the codebase to a non-Binance exchange (class stubs, env-var placeholders, commented imports) is aspirational, not functional.

## The adapter contract

Every adapter, current or future, must satisfy the same interface. Today the contract is expressed by the shape of the Binance adapter; it will be formalized into a typed `Adapter` protocol when the second adapter lands (see [`../architecture/future-state-roadmap.md`](../architecture/future-state-roadmap.md)).

An adapter is responsible for:

### Market data

- Subscribe to kline, depth, funding-rate, open-interest, and liquidation streams for the configured universe.
- Normalize every message into the canonical internal shape (see `coinscope_trading_engine/data/`).
- Attach monotonic local timestamps.
- Detect gaps and journal them. The adapter never silently bridges a gap.
- Handle reconnect with backoff. Exponential backoff with jitter; never hammer.

### Trading

- Submit market and limit orders.
- Submit stop-loss and take-profit orders alongside fills.
- Cancel working orders.
- Reconcile current positions against the journal on demand.

### Auth

- Sign requests according to the exchange's scheme (HMAC for Binance, signatures for OKX, wallet signatures for Hyperliquid).
- Never log signed payloads. Redact keys.
- Fail loudly at boot if keys are missing or invalid.

### Rate-limit awareness

- Track per-exchange request weight.
- Refuse to issue a request that would exceed the safety ceiling (`BINANCE_REQUEST_WEIGHT_MAX` for Binance).
- Expose current usage via Prometheus so the operator can see drift.

### Health

- Report adapter-level health to the engine's `/ready` check.
- Journal every reconnect, every rate-limit hit, every degraded mode.

## What adapters must not do

- **Make trading decisions.** An adapter does not decide whether to place an order. It places one when the executor asks.
- **Silently fail.** Any error worth not bubbling up is worth journaling.
- **Maintain independent state about positions.** The journal is authoritative; adapters reconcile against it.
- **Translate exchange error strings verbatim to API responses.** Errors are mapped to the engine's error codes (see [`../api/api-overview.md`](../api/api-overview.md)).

## Adding a new exchange (post-validation)

Ground rules:

1. **Do not start during validation.** The answer from 2026-04-10 to 2026-04-30 is always "wait."
2. **Start with testnet.** Every new adapter ships testnet-first. Mainnet cutover is a separate runbook.
3. **The second adapter forces the interface.** When you start on adapter #2, that's when the typed `Adapter` protocol comes out. Do not pre-factor the Binance adapter before you have a second implementation to validate the interface against.
4. **The second adapter is a PR with tests against recorded fixtures.** Not live tests only. Fixtures let the CI keep its distance from exchange outages.
5. **Document as you build.** Each adapter gets its own doc — `docs/ops/<exchange>-adapter.md` — modeled on [`binance-adapter.md`](binance-adapter.md).

## Per-exchange doc expectations

A complete exchange-adapter doc covers, at minimum:

- Base URLs (REST + WebSocket, testnet + mainnet).
- Auth scheme and how keys are configured.
- Rate limits (hard and soft).
- The stream set consumed.
- The order types supported (market, limit, stop, take-profit, any exchange-specific).
- Known quirks and incident history.
- How to run the adapter in isolation for debugging.

The current example is [`binance-adapter.md`](binance-adapter.md).

## Observability contract

All adapters expose these metrics (names may be prefixed by exchange):

- `engine_adapter_ws_reconnects_total`
- `engine_adapter_rest_errors_total{status=...}`
- `engine_adapter_rate_limit_hits_total`
- `engine_adapter_request_weight_current`
- `engine_adapter_stream_gap_seconds` — time since last message per stream.

These feed the operator dashboard and the Telegram alert logic.

## Why not use a generic library?

We use `ccxt` selectively for offline scripts but not in the live adapter. Reasons:

- Our normalization is tighter than ccxt's common shape (e.g., Decimal precision).
- We need to journal every interaction; the library doesn't.
- Stream handling differs by exchange enough that any shared abstraction leaks immediately.

For scripts and notebooks in `/scripts` and `/ml`, ccxt is fine. For the engine's live path, we write adapters by hand.

## What exists today that you might mistake for support

- `BYBIT_*`, `OKX_*`, `HYPERLIQUID_*` env-var placeholders in `.env.example`. Not wired to anything.
- Folder stubs or class placeholders for non-Binance exchanges (if they exist in a given commit). Not functional.
- Older commented imports. Remove them if you find them during cleanup PRs — they are noise.

**Treat anything not labeled `current` as "not real yet."** That's the convention across this doc tree.

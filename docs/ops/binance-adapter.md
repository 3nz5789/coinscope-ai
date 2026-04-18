# Binance Adapter

**Status:** current
**Audience:** developers working on the live market-data path or the order executor
**Related:** [`exchange-integrations.md`](exchange-integrations.md), [`../backend/configuration.md`](../backend/configuration.md), [`../runbooks/incident-binance-ws-disconnect-2026-04-18.md`](../runbooks/incident-binance-ws-disconnect-2026-04-18.md), [`telegram-alerts.md`](telegram-alerts.md)

The Binance USDT-M Futures adapter is the only production exchange adapter in the engine today. This page documents its surface area: URLs, auth, rate limits, streams, order types, known quirks, and how to run it in isolation.

## Endpoints and base URLs

| Surface | Testnet (current) | Mainnet (not enabled during validation) |
| --- | --- | --- |
| REST | `https://testnet.binancefuture.com` | `https://fapi.binance.com` |
| WebSocket — public streams | `wss://fstream.binancefuture.com/stream` | `wss://fstream.binance.com/stream` |
| WebSocket — user data stream | `wss://fstream.binancefuture.com/ws` (keyed) | `wss://fstream.binance.com/ws` (keyed) |

Selection is driven by `BINANCE_TESTNET` (boolean). During validation this is hard-pinned `true`; flipping it to `false` is blocked by the release checklist (see [`../runbooks/release-checklist.md`](../runbooks/release-checklist.md)).

### 2026-04-23 WebSocket path migration

Binance has announced a stream-path split effective 2026-04-23. The engine must move from the combined `/stream` path to segmented paths (`/public`, `/market`, `/private`). The adapter has a feature flag `BINANCE_WS_PATH_V2` (default `false`) that enables the new paths; on the cutover date we flip the flag and redeploy. See [`../runbooks/incident-binance-ws-disconnect-2026-04-18.md`](../runbooks/incident-binance-ws-disconnect-2026-04-18.md) for the incident that surfaced this requirement.

## Authentication

### Signing scheme

Binance USDT-M Futures signs every private request with **HMAC-SHA256** over the query string (`timestamp` appended) using the API secret as the key. The adapter's auth helper:

1. Builds the query string from ordered params.
2. Appends `timestamp=<ms since epoch>` and `recvWindow=<BINANCE_RECV_WINDOW_MS>`.
3. Computes `signature = HMAC_SHA256(query, secret)`.
4. Appends `signature=<hex>` to the query.
5. Sends with `X-MBX-APIKEY: <api_key>` header.

### Key configuration

| Env var | Purpose |
| --- | --- |
| `BINANCE_API_KEY` | API key. Required for any private call. |
| `BINANCE_API_SECRET` | API secret. Required; never logged. |
| `BINANCE_TESTNET` | `true` during validation; gates URL selection. |
| `BINANCE_RECV_WINDOW_MS` | Max clock-skew tolerance Binance will accept. Default 5000. |

Rules:

- **Never log the secret.** Structured log fields for auth are redacted. A PR that adds a `logger.info(api_secret)` line fails the pre-commit hook.
- **Fail loudly at boot if keys are missing.** The adapter raises `ConfigError` before the engine starts accepting traffic.
- **Keys are file-scoped.** They come from `.env`, never from CLI flags, never embedded in code.

## Rate limits

Binance USDT-M Futures enforces two independent limit families:

### Request weight

A per-minute weight budget, currently **2400/min** on testnet, **6000/min** on mainnet for a standard key. Every REST endpoint has a documented weight (e.g., `GET /fapi/v1/klines` = 1-10 depending on `limit`).

The adapter maintains a rolling counter and refuses to issue a request that would exceed `BINANCE_REQUEST_WEIGHT_MAX` (default 1800, a safety ceiling below the real cap). Refused requests raise `RateLimitGuardError`; the caller decides whether to back off or skip.

Current weight is exported as `engine_adapter_request_weight_current`.

### Order rate limits

Separate from request weight, Binance enforces **orders-per-10s** and **orders-per-minute**. The adapter caps outbound order traffic via a token bucket; exceeding it raises `OrderRateLimitGuardError` *before* the request goes out.

During validation the engine places very few orders, so the order-rate cap is never stressed — but the guard is in place for post-validation strategy expansion.

### What happens on a real 429 or 418

- **429** (warning): log, increment `engine_adapter_rate_limit_hits_total`, back off per `Retry-After`, continue.
- **418** (banned): this is a hard stop. The adapter throws `AdapterBannedError`, the executor refuses new orders, a Telegram alert fires, an operator must investigate. We have never hit a 418 in validation.

## Streams consumed

The adapter subscribes to the following public streams for every symbol in the configured universe:

| Stream | Purpose |
| --- | --- |
| `<symbol>@kline_1m` | 1-minute klines for the scanner and scorer. |
| `<symbol>@kline_5m` | 5-minute klines for multi-timeframe confirmation. |
| `<symbol>@depth20@100ms` | Top-of-book depth for slippage estimation. |
| `<symbol>@markPrice@1s` | Mark price and funding rate snapshot. |
| `<symbol>@forceOrder` | Liquidation feed. |

Plus one **user data stream** per API key (auth-scoped):

| Stream | Purpose |
| --- | --- |
| `ACCOUNT_UPDATE` | Position and balance updates. |
| `ORDER_TRADE_UPDATE` | Fill, cancel, and partial-fill notifications. |
| `MARGIN_CALL` | Maintenance-margin alerts. |

The adapter normalizes each message into the engine's canonical shapes defined in `coinscope_trading_engine/data/` and attaches a monotonic local timestamp. Gaps are detected by sequence number (for depth) and by kline completion time (for klines); detected gaps are journaled and exported as `engine_adapter_stream_gap_seconds`.

## Order types supported

| Type | Binance name | Used by the engine? |
| --- | --- | --- |
| Market | `MARKET` | Yes — entries and manual closes. |
| Limit | `LIMIT` | Yes — limit entries (infrequent). |
| Stop-loss | `STOP_MARKET` | Yes — the ATR stop. |
| Take-profit | `TAKE_PROFIT_MARKET` | Yes — the 2:1 RR target. |
| Reduce-only | flag on any of the above | Yes — applied to stop and TP so they cannot accidentally flip the position. |
| Post-only / `GTX` | flag on `LIMIT` | No — not used by current strategies. |
| Trailing stop | `TRAILING_STOP_MARKET` | No — not used; queued post-validation. |

Every entry places three orders: the entry (market or limit), the stop (stop-market, reduce-only), and the take-profit (take-profit-market, reduce-only). They are submitted as a best-effort group: if any of the three fail, the adapter raises and the executor reconciles.

## Known quirks and incident history

### Phantom disconnects without a close frame

The WebSocket client occasionally reports a dead connection without receiving a proper close frame. Root cause is Binance's edge infrastructure dropping idle sockets without a ping. Mitigation: the adapter sends a ping every 3 minutes and treats any lack of pong within 30 seconds as a reconnect signal. The full post-mortem for a case that bit us on 2026-04-18 is at [`../runbooks/incident-binance-ws-disconnect-2026-04-18.md`](../runbooks/incident-binance-ws-disconnect-2026-04-18.md).

### Price precision vs. tick size

Binance enforces a per-symbol tick size. If you place a limit order at a price that isn't a valid tick, the order is rejected with `code=-1111`. The adapter rounds prices to the nearest valid tick on the safe side (for buys, round down; for sells, round up) before submitting.

### Position-mode confusion

Binance supports one-way and hedge position modes on the same account. The engine assumes one-way. At boot, the adapter calls `GET /fapi/v1/positionSide/dual` and fails loudly if the account is in hedge mode. Do not flip position mode from the Binance UI while the engine is running.

### Symbol listings and delistings

New symbols appear without notice and get added to the exchange filter list. The scanner reads the symbol universe from `BINANCE_SYMBOL_UNIVERSE` (comma-separated env var); symbols not in the universe are ignored even if they're listed. Delistings that affect an open position are a manual operator situation — the adapter will fail to place the protective stop, and the executor will flag it.

### Clock skew

A server clock off by more than `BINANCE_RECV_WINDOW_MS` causes every signed request to fail with `code=-1021`. The engine verifies clock skew at boot (via `GET /fapi/v1/time`) and refuses to start if skew exceeds 500ms. In production this is handled by the VPS's NTP sync.

## Running the adapter in isolation

A standalone script exists for verifying the adapter against testnet without booting the full engine:

```bash
python -m scripts.binance_adapter_smoke \
  --symbols BTCUSDT,ETHUSDT \
  --duration 60
```

What it does:

1. Loads `.env`.
2. Instantiates the adapter with those symbols.
3. Subscribes to public streams.
4. Logs each normalized message (redacted where appropriate).
5. On interrupt, prints counters: messages received per stream, reconnects, rate-limit hits, gaps detected.

Extended variant for private endpoints:

```bash
python -m scripts.binance_adapter_smoke \
  --symbols BTCUSDT \
  --private \
  --duration 30
```

Opens the user data stream (requires `BINANCE_API_KEY`/`BINANCE_API_SECRET` in `.env`), logs heartbeat and any account events, exits cleanly. Does **not** place orders — there is no `--send-test-order` flag. Order placement is only ever done via the executor, never from ad-hoc scripts.

## Observability

Prometheus metrics the adapter exports (scraped by the stack described in [`../backend/backend-overview.md`](../backend/backend-overview.md)):

| Metric | Labels | Meaning |
| --- | --- | --- |
| `engine_adapter_ws_reconnects_total` | `stream=public\|private` | Count of WebSocket reconnects. |
| `engine_adapter_rest_errors_total` | `status=4xx\|5xx\|other` | REST errors by bucket. |
| `engine_adapter_rate_limit_hits_total` | — | 429s observed. |
| `engine_adapter_request_weight_current` | — | Rolling per-minute weight used. |
| `engine_adapter_stream_gap_seconds` | `stream` | Seconds since the last message on each stream. |
| `engine_adapter_order_latency_ms` | `type=entry\|stop\|tp` | Round-trip time on order submit. |

Alerts fire via Telegram (see [`telegram-alerts.md`](telegram-alerts.md)) when `engine_adapter_stream_gap_seconds` exceeds thresholds, on every reconnect, and on any `engine_adapter_rest_errors_total{status="5xx"}` increment.

## Pre-deploy and mainnet cutover

Mainnet cutover is explicitly out of scope during validation and is gated by:

1. A successful 30-day validation window on testnet with the risk controls firing as designed.
2. A signed-off release checklist (see [`../runbooks/release-checklist.md`](../runbooks/release-checklist.md)).
3. A separate mainnet-readiness doc that does not yet exist (queued in [`../product/implementation-backlog.md`](../product/implementation-backlog.md)).

Flipping `BINANCE_TESTNET=false` without the above is a policy violation, not a technical change.

## Testing

Unit and integration tests for the adapter live at `coinscope_trading_engine/tests/test_binance_adapter_*.py` and `coinscope_trading_engine/tests/test_binance_ws_*.py`. They cover:

- Signing correctness against fixture requests.
- Normalization output shape for each stream type.
- Rate-limit guard refusal before exceeding the ceiling.
- Gap detection on simulated out-of-order sequences.
- Reconnect backoff policy under repeated failures.
- Tick-rounding and step-size rounding.

When adding a new order type or stream, extend these tests before opening the PR.

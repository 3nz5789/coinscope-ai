# API Overview

**Status:** current
**Audience:** developers integrating with the engine's HTTP surface
**Related:** [`backend-endpoints.md`](backend-endpoints.md), [`../backend/backend-overview.md`](../backend/backend-overview.md), [`../backend/configuration.md`](../backend/configuration.md)

The engine exposes an HTTP API on FastAPI. This doc covers cross-cutting concerns — base URL, auth, errors, rate limits, versioning. For the endpoint-by-endpoint reference, read [`backend-endpoints.md`](backend-endpoints.md).

## Base URL

| Environment | Base URL |
| --- | --- |
| Local development | `http://localhost:8001` |
| Staging / VPS (internal) | `http://<vps-ip>:8001` |
| Production (behind reverse proxy) | `https://api.coinscope.ai` |

The React dashboard at https://coinscope.ai/ is a separate repository and points at the production base URL.

## Content type

- Requests: JSON (`Content-Type: application/json`) unless the endpoint explicitly takes form data (the Stripe webhook does).
- Responses: JSON (`application/json; charset=utf-8`).

## Authentication

Three authentication modes exist:

1. **Bearer token** for dashboard and operator requests.
   - Send `Authorization: Bearer <API_AUTH_TOKEN>` (configured via the `API_AUTH_TOKEN` env var).
   - Rotating the token invalidates all active dashboard sessions; plan for it.
2. **Stripe signature verification** for the Stripe webhook endpoint.
   - The endpoint reads the `Stripe-Signature` header and validates against `STRIPE_WEBHOOK_SECRET`.
   - The bearer token is ignored on this endpoint.
3. **Entitlement gating** on a subset of premium endpoints.
   - The endpoint first verifies the bearer token, then checks the caller's entitlement via the billing store.
   - On no-entitlement, returns `402 Payment Required` with the structured error format below.

Unauthenticated health probes hit `/health`, which is always open.

## Response envelope

Successful responses are the payload itself — no envelope wrapper. This keeps the API pleasant to consume from the dashboard and from `curl`.

Error responses use a consistent envelope:

```json
{
  "error": {
    "code": "string_machine_readable_code",
    "message": "Human-readable message",
    "details": { "optional": "structured context" }
  }
}
```

Expected codes include:

| HTTP | `error.code` | When |
| --- | --- | --- |
| 400 | `invalid_request` | Shape validation failed. |
| 401 | `unauthenticated` | Missing or invalid bearer token. |
| 402 | `payment_required` | Endpoint requires an active entitlement. |
| 403 | `forbidden` | Authenticated but not permitted (reserved for future). |
| 404 | `not_found` | Path or resource does not exist. |
| 409 | `conflict` | Idempotency / state conflict. |
| 422 | `unprocessable_entity` | Semantic validation failed (e.g., unknown symbol). |
| 429 | `rate_limited` | Caller exceeded a rate limit. |
| 503 | `engine_degraded` | Upstream dependency unavailable (Binance, Redis, journal). |
| 500 | `internal_error` | Everything else. |

## Versioning

The API is unversioned today. During validation, paths are considered stable. After 2026-04-30, any breaking change to a consumed endpoint must add a `/v2/` path rather than mutate the existing one.

Additive changes (new fields in a response, new optional query parameters) are not breaking.

## Rate limiting

The engine itself does not impose per-caller rate limits today — there is effectively one caller (the dashboard) plus operator `curl`. Behind a reverse proxy in production, the proxy layer can add rate limiting. If it does, the proxy returns the standard `429` with the envelope above.

The engine does enforce one internal rate limit: the adapter's Binance-request-weight accounting. Exceeding it is not returned to API callers; it causes degraded scan behavior. Metrics expose the weight usage.

## Idempotency

- Read endpoints are idempotent by definition.
- The Stripe webhook is idempotent via Stripe's event ID; replaying an event is a no-op.
- Future write endpoints should accept an `Idempotency-Key` header. None exist today.

## CORS

The engine allows cross-origin requests from the dashboard origin only. Configure via `CORS_ORIGINS` (see [`../backend/configuration.md`](../backend/configuration.md)). Local dev defaults to `http://localhost:3000` alongside the production origin.

## Timeouts

- Dashboard calls should use a 10-second request timeout.
- Scanner-backed endpoints (`/scan`, `/regime/{symbol}` on a cold cache) can take up to 5 seconds — the dashboard should show a progress state rather than assume sub-second response.
- The Stripe webhook returns within 1 second by design; longer work is enqueued to Celery.

## Error surface vs. engine safety

An API error is **never** allowed to leak raw internal state. In particular:

- No stack traces in responses.
- No Binance API error payloads passed through verbatim — they are mapped to our codes.
- No Stripe secret material or signed payloads echoed.

If you are adding an endpoint and find yourself reaching for `raise HTTPException(..., detail=exc.args[0])`, wrap it first.

## Observability hooks

Every request is logged with:

- Method, path, status.
- Duration.
- Caller identity if authenticated.
- A structured error code on failures.

Every request also increments a Prometheus counter. `/metrics` is scraped by local Prometheus in dev and by managed Prometheus in production.

## Where to go next

- Endpoint-by-endpoint reference: [`backend-endpoints.md`](backend-endpoints.md).
- How the backend is shaped: [`../backend/backend-overview.md`](../backend/backend-overview.md).
- How the engine decides anything behind these endpoints: [`../architecture/data-flow.md`](../architecture/data-flow.md).

# ADR-0001: FastAPI and Uvicorn as the web stack

**Status:** accepted
**Date:** 2026-02-12
**Authors:** Scoopy, operator
**Related:** [`../backend/backend-overview.md`](../backend/backend-overview.md), [`../api/api-overview.md`](../api/api-overview.md)

## Context

The engine needs to expose an HTTP API for three audiences:

1. The React dashboard at coinscope.ai.
2. The operator (curl, scripts).
3. Webhook callers (Stripe).

The engine is already Python — the ML stack, the adapter, and the risk layer are all Python. Introducing a second language for the API surface would complicate deployment and add a serialization seam between the hot path and the API.

Pre-existing reality: the scanner and the risk logic expect to be callable from both async (trading loop) and sync (ad-hoc scripts) contexts. The framework needs to be async-friendly without forcing every module to be async.

Volume is modest: a handful of requests per second in normal operation, spikes to ~20/s during bursts. Latency target for the hot paths (`/scan`, `/risk-gate`) is under 100ms p99.

## Decision

Use **FastAPI** as the web framework, **Uvicorn** as the ASGI server, and **Pydantic v2** for request/response models.

Rules:

- Every route function is `async def` even if it only calls sync code. Consistency beats micro-optimization.
- Every response is a Pydantic model — no raw dicts.
- Errors follow the envelope documented in [`../api/api-overview.md`](../api/api-overview.md); raise `HTTPException` with a standardized code, never a bare string.
- No custom middleware except CORS and request-id logging. If a cross-cutting concern appears, discuss before adding middleware.

## Alternatives considered

- **Flask + gunicorn.** Simpler, synchronous, well-known. Lost because async WebSocket ingestion and async outbound HTTP to Binance are core concerns; bolting them onto Flask via threads or gevent was a step backward.
- **Starlette directly.** FastAPI is already Starlette. Skipping FastAPI gives us Starlette's routing without Pydantic validation and OpenAPI generation. We wanted both; the cost of FastAPI on top of Starlette is negligible.
- **aiohttp.** Usable. Lost because Pydantic integration is second-class and the team's existing mental model is FastAPI.
- **gRPC.** Overkill for our traffic and hostile to a browser dashboard.
- **Status quo — a script-only engine with no HTTP layer.** Lost because the dashboard and the Stripe webhook both need HTTP.

## Consequences

**Positive:**

- Automatic OpenAPI at `/openapi.json`, which the dashboard consumes.
- Pydantic v2 is fast enough that request validation is not a hot-path concern.
- Uvicorn's lifespan hook gives us a clean place to start/stop the adapter, warm the ML artifacts, and open the journal.
- Easy to onboard — FastAPI is one of the most widely known Python web frameworks.

**Negative / costs:**

- FastAPI's dependency-injection system is powerful but can hide behavior. We've been disciplined about not nesting deps more than two layers.
- Pydantic v2's strictness around type coercion occasionally surprises new contributors (notably on datetimes).
- We accept Uvicorn's single-process default. Scaling past one process would require Gunicorn-in-front-of-Uvicorn or a different process model; we're not there.

**Neutral but worth noting:**

- The trading loop is a separate process from the API. FastAPI is only the edge.
- Async-throughout is enforced by code review, not by lints.

## Revisit when

- We need sustained throughput above ~100 req/s (currently well under this).
- We need in-process horizontal scaling (requires moving to Gunicorn or equivalent).
- Pydantic v3 lands with breaking changes — revisit migration path.

## Notes

Uvicorn config is in `coinscope_trading_engine/app.py`'s lifespan. Workers and reload are dev concerns, handled via CLI flags, not config.

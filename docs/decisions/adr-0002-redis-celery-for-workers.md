# ADR-0002: Redis + Celery for the async worker path

**Status:** accepted
**Date:** 2026-02-18
**Authors:** Scoopy, operator
**Related:** [`adr-0001-fastapi-and-uvicorn.md`](adr-0001-fastapi-and-uvicorn.md), [`../backend/backend-overview.md`](../backend/backend-overview.md), [`../architecture/data-flow.md`](../architecture/data-flow.md)

## Context

The engine has three categories of work:

1. **Hot-path, sync-critical** — gate decisions, order submissions, regime refreshes. These run in the trading loop and cannot tolerate queueing latency.
2. **Deferred but durable** — journal writes, Telegram alerts, rolling-window stats for alpha-decay, daily P&L summary. These must run reliably but can tolerate seconds of latency.
3. **Scheduled** — the 00:05 UTC daily summary, periodic heartbeat pings, cache-warming on boot.

Doing all three in the same event loop is the obvious first cut, and it's where we started. It broke the first time a Telegram send stalled for 12 seconds and delayed a gate decision. The lesson was clear: deferred work needs to be *actually* deferred, off the event loop, with its own failure mode.

The engine is single-node during validation. We don't need a distributed queue — we need a local one that's robust to process restarts and gives us visibility.

## Decision

Use **Celery** as the task framework with **Redis** as the broker and result backend. Run exactly one worker process on the same VPS as the API.

Rules:

- Hot-path code never calls a Celery task synchronously. It enqueues and returns.
- Scheduled tasks go through Celery Beat, not `asyncio.create_task`.
- Every task is idempotent or documented as "at most once OK."
- Tasks use explicit retries with bounded backoff — no infinite retry loops.
- Journaling writes are Celery tasks but also have a local-disk fallback so a Redis outage doesn't lose events.

## Alternatives considered

- **`asyncio.create_task` in the same process.** Free. Loses when the event loop stalls or the process crashes. The stalled-Telegram incident is the proof.
- **A thread pool (`concurrent.futures`).** Thread-safety with async code is fiddly; error handling is poor; no scheduled-task primitive.
- **RQ (Redis Queue).** Simpler than Celery. Lost on scheduling — Celery Beat is a known-good piece; RQ Scheduler is less mature.
- **Dramatiq.** Good alternative. Lost mostly on ecosystem familiarity and the scheduled-task story.
- **Arq.** Async-native, smaller surface. Lost because Celery's mature tooling (Flower, known operational patterns) outweighed the cleaner code.
- **SQS or a cloud queue.** Overkill for single-node. Added a dependency on cloud infrastructure we otherwise don't need.
- **Status quo — do deferred work on the event loop.** Lost because we already saw it fail.

## Consequences

**Positive:**

- Clear separation between hot-path and deferred work.
- Celery Beat handles scheduling without a separate cron.
- Visibility: task names, arguments, durations all go through a single logging path.
- Redis is already useful for cache + rate-limit counters, so it wasn't a pure-additional dependency.

**Negative / costs:**

- Operational complexity: two more processes (worker, beat) to keep running.
- Celery's configuration surface is large. We use a small subset and commit to keeping it that way.
- Celery 5.x has occasional compatibility friction with async code; we call Celery tasks from async code by enqueueing, never by awaiting results synchronously.
- If Redis goes down, the worker stalls. The journal's local-disk fallback covers the durability case; the rest is acceptable for our failure posture.

**Neutral but worth noting:**

- We do not run multiple workers. One worker, one Beat, one API, one trading loop. If we ever need more worker throughput, we revisit.
- Task results are mostly fire-and-forget; the result backend is used for a small set of tasks (alpha-decay windowing) that need a return value.

## Revisit when

- We add a second node or move off single-VPS deployment. At that point, either SQS or a managed Redis becomes more attractive.
- We hit Redis scaling issues (very unlikely at current volumes).
- A task category emerges that needs fan-out or priority queues beyond what Celery gives us cleanly.

## Notes

The Redis broker URL is in `REDIS_URL`. Celery config is in `coinscope_trading_engine/celery_app.py`. Beat schedule is defined in the same file — not a separate config file, deliberately, so one diff shows all scheduling changes.

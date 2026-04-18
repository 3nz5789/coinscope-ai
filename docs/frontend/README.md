# Frontend Docs

**Status:** draft
**Audience:** anyone looking for dashboard/UI documentation
**Related:** [`../README.md`](../README.md), [`../architecture/system-overview.md`](../architecture/system-overview.md), [`../api/api-overview.md`](../api/api-overview.md)

This directory is intentionally thin. The main user-facing UI — the React dashboard at <https://coinscope.ai/> — lives in a **separate repository** and has its own docs tree. It is not mirrored here.

## What lives in this repo

Three static HTML pages under `/dashboard/`:

| File | Purpose |
| --- | --- |
| `/dashboard/pricing.html` | Subscription tier pricing page. Static, served alongside the billing API. |
| `/dashboard/billing_success.html` | Post-checkout success landing. Receives `session_id` from Stripe redirect. |
| `/dashboard/pnl_widget.html` | Embeddable P&L widget. Reads from `/performance` on the engine API. |

These are single-file HTML with inline CSS + vanilla JS. No build step, no framework. They share a minimal mint-green accent palette (`#2de8a8`) aligned with the logo.

## What is not documented here

- The React dashboard's components, routing, state management, or build — those live in the dashboard repo.
- The engine API that the dashboard consumes — that is [`../api/api-overview.md`](../api/api-overview.md) and [`../api/backend-endpoints.md`](../api/backend-endpoints.md).
- The Stripe checkout flow the dashboard triggers — that is [`../ops/stripe-billing.md`](../ops/stripe-billing.md).

## Backlog

A fuller frontend doc — covering the React dashboard's architecture, build, deployment, and integration with the engine API — is listed in [`../product/implementation-backlog.md`](../product/implementation-backlog.md). It is blocked on a decision about whether to mirror the dashboard repo's docs here or just link out.

Until that decision, read the dashboard repo directly and use the engine API docs in this tree to understand what the dashboard consumes.

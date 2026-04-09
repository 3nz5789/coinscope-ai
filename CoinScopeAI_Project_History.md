# CoinScopeAI — Comprehensive Project History & Institutional Memory

**Document Date:** April 9, 2026
**User:** 3onooz (Mohammed) — Location: Jordan, UTC+3
**Agent:** Scoopy (Manus AI Operating Agent)
**GitHub:** [3nz5789/coinscope-ai](https://github.com/3nz5789/coinscope-ai)

---

This document serves as the **definitive institutional memory** for the CoinScopeAI project. It captures every significant event, decision, subtask, URL, user preference, and lesson learned from the project's inception on April 6, 2026 through April 9, 2026. It is intended to be loaded into MemPalace as the foundational knowledge base and to serve as the single source of truth for any agent or human working on the project.

---

## 1. Timeline of Events

All timestamps are in **UTC+3** (Mohammed's timezone in Jordan).

### Day 1 — April 6, 2026: Foundation

The project began when Mohammed (3onooz) initiated the conversation and established the working relationship. He named the agent "Scoopy" and a `soul.md` file was created at **01:12** to persist the operating persona. The first operational deliverable was the **API exploration report** at **01:24**, which mapped the CoinScopeAI engine's endpoints (`/scan`, `/performance`, `/journal`, `/risk-gate`, `/position-size`, `/regime/{symbol}`).

By **02:21**, the full project workspace had been unzipped and verified, establishing the local directory structure at `/home/ubuntu/coinscopeai_project/`. The workspace setup subtask ran through the morning, producing a comprehensive workspace setup summary that was copied to the project directory by **02:57**.

The Google Drive workspace was set up by **11:03**, followed by the Linear workspace blueprint at **12:01**. Around **12:23**, Mohammed shared a pasted content file that informed the project's direction. The `soul.md` was updated at **15:51** with the full CoinScopeAI operating persona, communication preferences, and project context.

The **strategic plan** was finalized and copied at **16:01**. A cross-platform audit report was completed at **17:00**, verifying consistency across Notion, Linear, GitHub, and Google Drive. The **data ingestion module** (110K+ Binance candles) was integrated at **17:25**, and the **backtesting engine** (walk-forward analysis) followed at **19:05**.

### Day 2 — April 7, 2026: Core Engine Build

The day started with the creation of the **OpenClaw integration master prompt** at **00:09**, designed to guide another Manus agent in building the OpenClaw integration. After a gap (likely overnight), work resumed at **12:53** with the **ML engine analysis** being copied to the project, followed by the **ML Engine V2 (LongTF)** at **13:46**.

A major sync operation occurred around **13:41**, producing a cross-platform sync summary. The **Drive audit report** was completed at **14:09**, and a second cross-platform audit at **14:23**. At **14:25**, **PR #3 was merged** on GitHub using the `gh` CLI — this was the first confirmed PR merge in the project.

At **18:31**, the Telegram bot integration was first discussed when Mohammed shared what appeared to be a bot token. The agent recognized it and proposed configuring live alerts for trade signals, fills, risk events, heartbeats, and daily summaries.

A pivotal decision point came at **21:57** when Scoopy recommended adding Bybit's history-data portal (free 500-level L2 order book data back to 2023) but advised against adding the crypto-market-data open-source project. Mohammed approved. By **22:37**, the **free real-time data streams** build was complete — 95/95 tests passing, 4,249 lines across 10 modules covering tick trades, L2 order book, funding rates, liquidations, and replay/backtest across all four exchanges (Binance, Bybit, OKX, Hyperliquid). **PR #7** was created and merged at **22:53**.

The evening push continued with the **EventBus integration** and **24/7 recording daemon**. A testnet check revealed the paper trading engine had run for 5.3 hours with zero signals because the WebSocket disconnected at exactly the 16:00 UTC 4h candle close. The **candle-miss bug was fixed** with a REST fallback, and both the engine (PID 21072) and recorder (PID 21441) were confirmed live at **23:48**, with the recorder capturing 133 events/second across 3 exchanges. **PR #8** was merged at **23:52**.

### Day 3 — April 8, 2026: Dashboard, Ops, and Deployment

The **frontend dashboard** build began at **23:53** (April 7) and was deployed by **00:12** with a "Command Center" military-grade HUD aesthetic. Mohammed requested the **Overview page** and **24h price change indicators**, which were added by **00:37**. A QA review at **00:49** found and fixed 5 issues (equity curve time selector, P&L distribution chart, configurable API base, console warnings, dynamic subtitles). **PR #9** was merged at **01:03**.

At **01:06**, Scoopy diagnosed the testnet engine and found **4 critical bugs**: an API mismatch (`compute()` vs `extract()`), a wrong import (`FeatureEngineV2` vs `LongTFFeatureEngine`), a missing timestamp column, and normalization parameters causing extreme distribution shift (z-scores reaching -72). The **ML v3 retraining** was initiated with 162 features (112 v2 base + 50 alpha proxies).

The **dashboard live engine integration** and **daily status check script** were completed at **02:12**. The Telegram bot setup hit a blocker at **02:16** because the token was a placeholder. Mohammed provided the real token at **02:24**, and by **02:33**, the bot (`@ScoopyAI_bot`) was fully configured, sending to chat ID 7296767446 (`@CoinScopeAI24`), with a cron job at 08:00 UTC+3.

The **Week 1 Integration Report** and **systemd service files** were pushed at **02:55**. The dashboard was confirmed live at **03:12**. Mohammed asked about always-on deployment at **04:11**, leading to the **Cloud Deployment Guide** (recommending Hetzner CPX32 in Singapore at ~$20/month) at **04:25**. A scheduled Manus task for daily Telegram reports was set up at **04:39**.

At **10:30**, the dashboard subtask was stopped because it had begun making unsolicited changes (blog section, SEO extras) without being asked. This was the **scope creep incident**. A system check at **10:52** showed a health score of 5/6 (83%), with only the engine API offline as expected.

At **15:38**, Mohammed shared a screenshot of a Hetzner signup error — the VAT ID field rejected his Jordanian input. Scoopy advised him to leave the field blank since Hetzner only validates EU VAT IDs.

### Day 4 — April 9, 2026: MemPalace, Stripe, and Lessons

Mohammed shared the **Graphify repo** at **00:43**. After review, Scoopy recommended against integration — it was a dead 2018 student project with no financial charting capability. Instead, **TradingView Lightweight Charts** was recommended and prototyped. The prototype was deployed at **01:20** to `coindash-iad7x9yd.manus.space`.

At **10:01**, Mohammed said he didn't like the TradingView dashboard and asked to go back to the previous one. The TradingView version was kept as a reference while the original remained primary.

The **MemPalace repo** was reviewed at **10:20** — a 29,819-star open-source AI memory system using ChromaDB. Mohammed decided to integrate it at **10:24**. The integration was complete by **11:01** with 7 specialized memory wings (trading, risk, scanner, models, system, dev, agent). Mohammed then shared a detailed review of the integration, identifying production gaps. Five critical improvements (non-blocking writes, idempotency, hall strategy, batch/flush, retention) were implemented by **11:30**.

At **11:37**, Mohammed shared a MemPalace management strategy document. Scoopy reviewed it and identified key considerations: MCP server hosting needs a VPS, concurrency safety for multi-agent writes, agent prompt discipline, and cold start handling.

The **Stripe integration** saga began at **13:22** when Mohammed shared a screenshot showing a completed subtask that had built Stripe checkout but whose preview failed to load. The Stripe code was lost because it only existed in the archived subtask's sandbox. A rebuild was initiated, and the first version deployed at **13:49** to `coinscopedash-tltanhwx.manus.space` with incorrect pricing (old 3-tier model with $0 and $1 prices).

At **14:02**, Mohammed shared his full pricing strategy (4-tier: Starter $19, Pro $49, Elite $99, Team ~$299). The merged dashboard was redeployed at **14:26** with 16 pages total. However, at **14:29**, Mohammed caught that the pricing page still showed wrong prices — the **pricing page incident**. At **14:31**, he said: *"that's why I need you to use MemPalace"* — a direct call-out that the spec had been lost in context. He further clarified at **14:34** that Scoopy should use MemPalace for its own memory first, before using it as a system component. The pricing fix was deployed at **14:35**.

---

## 2. All Decisions Made

### Identity and Vision

| Attribute | Decision |
|---|---|
| Project Name | CoinScopeAI |
| User Name | 3onooz (Mohammed) |
| Agent Name | Scoopy |
| User Location | Jordan (UTC+3) |
| Communication Style | Direct, concise, prefers "what you suggests" recommendations |

### Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| Frontend Framework | React + Vite + TypeScript | Modern, fast, type-safe |
| State Management | Zustand | Lighter than Redux, fits existing architecture |
| Portfolio Charts | Recharts | Good for equity curves, P&L, risk gauges |
| Financial Charts | TradingView Lightweight Charts | Canvas-based, built for candlesticks and streaming (prototyped, not yet in main) |
| Backend | FastAPI (Python) | Async, fast, good for ML integration |
| ML Models | LightGBM + Logistic Regression | Walk-forward validated, 10/10 4h configs profitable in V2 |
| Memory System | MemPalace (ChromaDB + SQLite) | Local, private, persistent agent memory |
| Infrastructure | Docker + systemd | Containerized with auto-restart policies |
| Payments | Stripe Checkout | Subscription management with test mode |
| Alerts | Telegram Bot (@ScoopyAI_bot) | Daily status reports at 08:00 UTC+3 |
| Cloud Hosting | Hetzner CPX32 Singapore | $20/mo, 8GB RAM, 4 vCPUs, low latency to Asian exchanges |

### Pricing Model (Confirmed April 9)

| Tier | Monthly | Annual | Notes |
|---|---|---|---|
| Starter | $19 | $190 | Entry-level |
| Pro | $49 | $490 | "Most Popular" badge |
| Elite | $99 | $990 | Advanced features |
| Team | ~$299 | Custom | Multi-seat, custom |

Annual pricing includes a **20% discount**. The pricing page includes a monthly/annual toggle, hero section, feature comparison matrix, FAQ, and CTA.

### Dashboard Preferences

Mohammed preferred the original "Command Center" HUD aesthetic with deep navy background (`#0a0e17`), emerald accents (`#10b981`), and JetBrains Mono typography. He explicitly rejected the TradingView prototype layout but agreed to keep it as a reference. He initially questioned the Blog, API Docs, Contact, and FAQ pages that a subtask had added, but after discussion, agreed they belong in a production SaaS dashboard.

### Architecture Decisions

The **EventBus** was chosen as the single integration point, allowing scanners and alpha generators to work identically on live and replayed data with zero code changes. The **recording daemon** was prioritized as time-sensitive because every hour without recording is data that can never be recovered. **Bybit L2 historical backfill** was approved (free 500-level depth back to 2023), while the crypto-market-data open-source project was deferred. The **ML v3 upgrade** synthesized alpha proxies from OHLCV data because only 1 day of streaming data existed — not enough to train on directly.

### MemPalace Adoption

MemPalace was adopted for two distinct purposes, in this order of priority:

1. **Agent Memory (Priority 1):** Scoopy must use MemPalace as its own operational memory to store project decisions, specs, architecture choices, and user preferences. This prevents context loss between sessions and across subtasks.

2. **System Integration (Priority 2):** MemPalace serves as the trading system's institutional memory — logging trade decisions, ML model parameters, risk events, and regime changes for post-trade analysis.

---

## 3. All Subtasks and Outcomes

### Workspace and Planning

| Subtask | Outcome | Key Artifacts |
|---|---|---|
| Workspace Setup (Manus, Google Drive, Linear, Notion, GitHub) | Full workspace synced across all platforms | `WORKSPACE_GUIDE.md`, `CoinScopeAI_Workspace_Setup_Summary.md` |
| Comprehensive Project Plan | Strategic plan with phased roadmap | `CoinScopeAI_Strategic_Plan.md` |
| API Endpoint Exploration | All 6 engine endpoints mapped | `coinscopeai_api_exploration.md` |
| GitHub Repo Setup | Private repo created at `3nz5789/coinscope-ai` | 347+ files, 10 PRs merged |
| Notion Trading System | Executive Dashboard, Engineering & Architecture pages | Updated throughout project |
| Cross-Platform Audits | Two audits (April 6 and April 7) confirming sync consistency | `CoinScopeAI_Cross_Platform_Audit_Report.md`, `CoinScopeAI_Cross_Platform_Audit_April7.md` |

### Core Engine Development

| Subtask | Outcome | Key Metrics |
|---|---|---|
| Data Ingestion Infrastructure | Pipeline built | 110K+ Binance candles ingested |
| Backtesting Engine | Walk-forward analysis engine | Integrated into main |
| ML Engine V2 (LongTF) | 10/10 4h configs profitable | LightGBM + LogReg ensemble |
| ML Engine V3 | 162 features (112 base + 50 alpha proxies) | Fixed normalization distribution shift |
| Paper Trading Pipeline | Live on Binance Testnet | Account: 4,955.54 USDT |
| Phase 1: Multi-Exchange Streams | WebSocket streams for 4 exchanges | Binance, Bybit, OKX, Hyperliquid |
| Phase 2: Alpha Generators + Regime Enricher | 5 alpha generators + regime detector | Funding, Liquidation, OI, Basis, Orderbook |

### Data and Integration

| Subtask | Outcome | Key Metrics |
|---|---|---|
| Free Data Streams | Unified streams across 4 exchanges | 95/95 tests, 4,249 lines, 10 modules |
| Integration V2 with Candle Fix | EventBus wired, candle-miss bug fixed | 339/339 tests, REST fallback added |
| 24/7 Recording Daemon | Live data capture | 133 events/sec, 3 exchanges, JSONL.gz with midnight rotation |
| Market Data Streams Research | Bybit L2 backfill approved, community dataset deferred | 500-level depth back to 2023 |

### Frontend and Dashboard

| Subtask | Outcome | URL |
|---|---|---|
| Dashboard Build (Original) | 10-page HUD Command Center | `coinscopedash-cv5ce7m8.manus.space` |
| TradingView Prototype | Candlestick charts with live WebSocket streaming | `coindash-iad7x9yd.manus.space` |
| Stripe Integration + Merge | 16-page merged dashboard with Stripe billing | `coinscopedash-tltanhwx.manus.space` |

### Operations and Deployment

| Subtask | Outcome | Key Artifacts |
|---|---|---|
| Daily Status Check Script | Zero-dependency Python script checking all endpoints | `scripts/daily_status_check.py` |
| Telegram Bot Setup | @ScoopyAI_bot, daily reports at 08:00 UTC+3 | Chat ID: 7296767446 |
| Week 1 Integration Report | Full documentation of v3 upgrade, bug fixes, and validation status | `Week1_Integration_Report.md` |
| Systemd Service Files | 3 service files + installer + Makefile | `deploy/systemd/` |
| Cloud Deployment Guide | 788-line step-by-step Hetzner guide | `Cloud_Deployment_Guide.md` |

### Research and Evaluation

| Subtask | Outcome | Verdict |
|---|---|---|
| OpenClaw Research | Master prompt created for integration | Deferred to future agent |
| Graphify Research | Reviewed and rejected | Dead project, wrong tool for financial data |
| MemPalace Research | Reviewed, approved, and integrated | 7 wings, 5 production improvements |
| VRC Strategy Analysis | Analyzed | Integrated into project planning |

### MemPalace Integration

| Subtask | Outcome | Key Details |
|---|---|---|
| Initial Integration | 7 specialized memory wings | wing_trading, wing_risk, wing_scanner, wing_models, wing_system, wing_dev, wing_agent |
| Production-Readiness Improvements | 5 critical fixes applied | Non-blocking async writes, idempotency/dedup, hall strategy enforcement, batch/flush (5s/50 events), retention/pruning |
| MemPalace SOP Review | Management strategy reviewed and approved | MCP server hosting, concurrency safety, agent prompt discipline identified as key concerns |

---

## 4. All URLs and Assets

### Live Dashboards

| Dashboard | URL | Status |
|---|---|---|
| Main (Merged with Stripe, 16 pages) | `https://coinscopedash-tltanhwx.manus.space` | **Primary — Use This** |
| Original (No Stripe, 10 pages + Blog/FAQ) | `https://coinscopedash-cv5ce7m8.manus.space` | Fallback |
| TradingView Prototype | `https://coindash-iad7x9yd.manus.space` | Reference only |

### Code and Project Management

| Service | URL/Details |
|---|---|
| GitHub Repository | `https://github.com/3nz5789/coinscope-ai` (private) |
| Linear Workspace | `https://linear.app/coinscopeai/` |
| Notion Workspace | Executive Dashboard, Engineering & Architecture pages |
| Google Drive | CoinScopeAI folder with Reports & Analytics |

### Telegram Bot

| Attribute | Value |
|---|---|
| Bot Username | @ScoopyAI_bot |
| Chat ID | 7296767446 |
| Chat Username | @CoinScopeAI24 |
| Schedule | Daily at 08:00 UTC+3 |

### Stripe (Test/Sandbox Mode)

| Key | Value |
|---|---|
| Publishable Key | `pk_test_***REDACTED***` |
| Secret Key | `sk_test_***REDACTED***` |
| Test Card | 4242 4242 4242 4242 (any future expiry, any CVC) |

### GitHub PRs (All Merged to Main)

| PR | Branch | Description |
|---|---|---|
| #3 | (early sync) | Initial codebase sync |
| #7 | feat/free-data-streams | 12 files, 5,595 insertions — unified streams |
| #8 | (integration-v2) | EventBus integration + candle fix + recorder |
| #9 | feat/dashboard | 103 files — 10-page HUD dashboard |
| Direct commits | main | Daily status check, systemd files, deployment guide, MemPalace |

### Engine API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /scan` | Scan market signals |
| `GET /performance` | Performance metrics |
| `GET /journal` | Trade journal |
| `GET /risk-gate` | Risk gate status |
| `GET /position-size` | Position sizing |
| `GET /regime/{symbol}` | Market regime detection |

---

## 5. User Preferences and Feedback

### Communication Style

Mohammed communicates in a direct, low-ceremony style. He frequently responds with "ok", "yes", "go", "start", or "what you suggests" — trusting Scoopy to make recommendations and execute. He prefers honest assessments over sugar-coated updates and expects the agent to flag problems proactively.

### Aesthetic Preferences

Mohammed strongly prefers the **military-grade HUD aesthetic**: deep navy void (`#0a0e17`), emerald accents (`#10b981`), JetBrains Mono typography for all data, corner-bracket card styling, and pulsing live indicators. He rejected the TradingView prototype's different layout but kept it as a reference for future improvement.

### Content Preferences

Initially, Mohammed questioned the Blog, API Docs, Contact, and FAQ pages that a subtask had added without explicit approval. However, after Scoopy acknowledged the overreaction and explained the value of these pages for a production SaaS, Mohammed agreed they should stay.

### Pricing Specification

Mohammed provided a detailed pricing strategy with 4 tiers (Starter $19, Pro $49, Elite $99, Team ~$299), monthly/annual toggle with 20% discount, hero copy, feature comparison matrix, and specific page layout. This spec was shared via a pasted content file and must be treated as a canonical reference.

### MemPalace Usage Directive

Mohammed explicitly stated that Scoopy must use MemPalace **for itself first** before using it as a system component. His exact words: *"before that you should use it for you, before we use it to our system, you got me?"* and *"as you manage the project and run other agents you have to use it."* This is a standing directive.

### Hetzner Signup

Mohammed attempted to sign up for Hetzner and encountered a VAT ID validation error because Jordan is not an EU country. He was advised to leave the VAT ID field blank. The signup status is unknown — it may still be pending.

---

## 6. Current Project State

### What Is Live and Working

The **merged dashboard** (16 pages including Stripe billing) is live at `coinscopedash-tltanhwx.manus.space`. The **daily Telegram status report** runs every morning at 08:00 UTC+3 via a Manus scheduled task, confirming dashboard availability and engine status. The **GitHub repository** is fully synced with all code, documentation, systemd service files, and deployment guides. All **10 PRs have been merged** to main with zero open.

### What Is Pending

The **VPS deployment** is the primary blocker. The backend engine, recording daemon, and MemPalace MCP server all require a persistent server to run 24/7. The Hetzner CPX32 in Singapore was recommended, and Mohammed began the signup process but may have been blocked by the VAT ID issue. Until the VPS is live, the engine API remains offline and the dashboard operates on mock data.

**MemPalace agent usage** has been committed to but not yet operationalized. Scoopy needs to actively store decisions, specs, and outcomes in MemPalace at the start of every session.

### Current Phase

The project is in the **30-day Testnet Validation Phase**. The priority is hands-off monitoring — no engine code changes, no new ML research. The v3 models need to prove themselves through real testnet performance before any staging promotion.

### Known Issues

The engine API (`localhost:8001`) is offline because it requires the VPS deployment. The dashboard shows mock data when the engine is unreachable (with an amber "MOCK DATA" badge). The pricing page had an incident where it showed wrong prices, which was fixed but highlights the need for MemPalace-backed spec persistence.

---

## 7. Lessons Learned

### The Pricing Page Incident

> **What happened:** The Stripe integration was deployed with an outdated 3-tier pricing model ($0/$1 prices) instead of Mohammed's specified 4-tier model (Starter $19, Pro $49, Elite $99, Team ~$299).

> **Root cause:** The detailed pricing spec was shared via a pasted content file, but it was lost in the context window by the time the subtask built the pricing page. The subtask defaulted to the old model because it never received the updated spec.

> **Mohammed's response:** *"that's why I need you to use MemPalace."*

> **Lesson:** Every user-provided spec must be immediately stored in MemPalace (`wing_dev/hall_facts`) so that any agent building any component can query it before writing code. Context windows are insufficient for multi-session, multi-agent projects.

### The Dashboard Scope Creep Incident

> **What happened:** A dashboard subtask began adding unsolicited features (blog section, SEO meta tags, extra pages) without being asked. Scoopy overreacted by archiving the entire subtask.

> **Root cause:** The subtask lacked clear boundaries on what it was authorized to build. Without explicit constraints, it kept iterating and adding features.

> **Mohammed's response:** He questioned why the Blog, API Docs, Contact, and FAQ pages were being removed, pointing out they were actually useful for a production SaaS.

> **Lesson:** (1) Subtasks need explicit scope boundaries — what to build and what NOT to build. (2) When a subtask goes off-track, stop the specific behavior, don't kill the whole task. (3) Not all unsolicited additions are bad — evaluate them before removing.

### Why MemPalace Was Adopted

> **The problem:** Standard LLM context windows are insufficient for a complex, multi-agent trading system project. Decisions made in one session are lost by the next. Specs shared in messages are forgotten when subtasks are spawned. Architectural choices made on Day 1 are invisible on Day 4.

> **The solution:** MemPalace provides persistent, searchable institutional memory using ChromaDB for vector storage and a temporal knowledge graph for fact tracking. It supports per-agent specialist memory with compressed context loading (~170-800 tokens on wake-up instead of full history).

> **The directive:** Mohammed explicitly stated that Scoopy must use MemPalace for its own operational memory first, before deploying it as a system component. This means storing every decision, spec, preference, and outcome immediately — not as a future improvement, but as a current operating requirement.

---

## Appendix: Full Stack on Main Branch

As of April 9, 2026, the following components are merged into the `main` branch of `3nz5789/coinscope-ai`:

| Component | Description |
|---|---|
| Data Ingestion Pipeline | 110K+ Binance candles |
| Backtesting Engine | Walk-forward analysis |
| ML Signal Engine V2 | 10/10 4h configs profitable |
| ML Signal Engine V3 | 162 features with alpha proxies |
| Paper Trading Pipeline | Live on Binance Testnet |
| Phase 1: Multi-Exchange Streams | Binance, Bybit, OKX, Hyperliquid |
| Phase 2: Alpha Generators + Regime Enricher | 5 generators + regime detector |
| Free Data Streams | Tick trades, L2 orderbook, funding, liquidations, replay |
| EventBus Integration | Thread-safe async pub/sub |
| 24/7 Recording Daemon | 133 events/sec, JSONL.gz |
| Frontend Dashboard | 16 pages, HUD aesthetic, Stripe billing |
| MemPalace Integration | 7 wings, production-ready |
| Docker Infrastructure | Compose files, Makefile |
| Systemd Service Files | Engine, recorder, dashboard services |
| Daily Status Check | Python script + cron wrapper |
| Cloud Deployment Guide | 788-line Hetzner guide |
| Week 1 Integration Report | Full changelog and decision log |

---

*This document was generated by Scoopy (Manus AI) on April 9, 2026 from the complete compacted conversation history. It should be stored in MemPalace (`wing_dev/hall_facts`) and updated as the project evolves.*

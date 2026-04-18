# CoinScopeAI Manus Workspace Setup & Workflow Guide

**Date:** April 9, 2026
**Project:** CoinScopeAI
**User:** 3onooz (Mohammed)
**Agent:** Scoopy (Manus AI Operating Agent)

This document serves as the central hub and operational manual for the CoinScopeAI project within the Manus environment. It defines the project structure, inventories all tasks, establishes strict workflow rules for the AI agent (Scoopy), and provides a quick reference for all critical project assets.

---

## 1. Project Structure

The CoinScopeAI Manus project is organized into logical categories to maintain order and ensure all components are easily accessible. This structure applies to both the local Manus workspace (`/home/ubuntu/coinscopeai_project/`) and the synchronized Google Drive.

### Active Tasks by Category

*   **Infrastructure:** Tasks related to server deployment, Docker containers, systemd services, and the core operating environment. This currently centers on the Hetzner VPS deployment.
*   **Dashboard:** Tasks focused on the React/Vite frontend, including UI/UX updates, Stripe billing integration, and data visualization (Recharts/TradingView).
*   **Trading Engine:** Tasks involving the FastAPI backend, ML models (LightGBM/LogReg), EventBus, data ingestion pipelines, and the paper trading execution logic.
*   **Ops/Monitoring:** Tasks related to system health, the 24/7 recording daemon, the daily status check script, and the Telegram alert bot.
*   **Research:** Tasks exploring new alpha generators, alternative data streams, or new architectural components (e.g., MemPalace integration).
*   **Documentation:** Tasks dedicated to maintaining the institutional memory, cross-platform sync reports, and standard operating procedures (SOPs).

### Scheduled & Recurring Tasks

*   **Daily Status Report:** A scheduled Manus task runs daily at **08:00 UTC+3**. It executes the `scripts/daily_status_check.py` script and sends a comprehensive health report via the Telegram bot (`@ScoopyAI_bot`) to the `@CoinScopeAI24` chat.

### Reference Documents & Guides

All key reference documents are maintained in the Google Drive workspace and synced locally. Key documents include:
*   `CoinScopeAI_Project_History.md` (The definitive institutional memory)
*   `CoinScopeAI_Strategic_Plan.md`
*   `Cloud_Deployment_Guide.md`
*   `Week1_Integration_Report.md`
*   `MemPalace SOP.md`

---

## 2. Current Task Inventory

This section lists all existing tasks and subtasks, categorized by their current status as of April 9, 2026.

### Active / In Progress

*   **Cloud VPS Deployment (COI-40):** Deploying the core engine and MemPalace to a Hetzner CPX32 instance in Singapore. *Status: Blocked (Pending VAT ID resolution).*
*   **30-Day Testnet Validation Phase (COI-41):** Monitoring the ML V3 engine on the Binance Testnet. *Status: Active (Hands-off monitoring).*

### Completed / Deployed

*   **Dashboard Build - Main (Merged):** The primary 16-page React dashboard featuring the "Command Center" HUD aesthetic and Stripe billing integration. Deployed to `coinscopedash-tltanhwx.manus.space`.
*   **Dashboard Build - Original Backup:** The initial 10-page dashboard without Stripe. Deployed to `coinscopedash-cv5ce7m8.manus.space`.
*   **Dashboard Build - TradingView Prototype:** A prototype utilizing TradingView Lightweight Charts. Deployed to `coindash-iad7x9yd.manus.space` (Kept for reference only).
*   **MemPalace Integration (COI-38):** Implementation of the ChromaDB-based memory system with 7 specialized wings and 5 production-readiness improvements.
*   **Stripe Payment Integration (COI-39):** Implementation of the 4-tier pricing model (Starter $19, Pro $49, Elite $99, Team ~$299) with monthly/annual toggles.
*   **Daily Telegram Status Reports:** Configuration of the `@ScoopyAI_bot` and the scheduled Manus cron job.
*   **Cross-Platform Audit:** Synchronization of Notion, Linear, GitHub, and Google Drive to reflect the April 9 state.
*   **ML Engine V3 Upgrade:** Implementation of 162 features (112 base + 50 alpha proxies) and normalization fixes.
*   **Free Real-Time Data Streams:** Integration of WebSocket streams for Binance, Bybit, OKX, and Hyperliquid.
*   **EventBus & Recording Daemon:** Implementation of the thread-safe async pub/sub system and the 24/7 data capture daemon.

### Archived / Rejected

*   **Graphify Integration:** Rejected. Identified as an outdated tool unsuitable for financial charting.
*   **OpenClaw Integration:** Deferred. Master prompt created but implementation paused for the current phase.

---

## 3. Workflow Rules for Scoopy (AI Agent)

To prevent context loss, scope creep, and desynchronization, Scoopy MUST adhere to the following strict workflow rules:

1.  **Centralized Task Creation:** Every new task or subtask MUST be created explicitly under the `CoinScopeAI` project umbrella. Orphaned tasks are not permitted.
2.  **Mandatory Documentation:** Every completed task MUST be fully documented before it is archived. This includes updating the relevant Notion pages, closing the Linear issue, and generating a summary report if applicable.
3.  **MemPalace First Policy:** MemPalace is the primary source of truth. Scoopy MUST query MemPalace (`wing_dev/hall_facts`) before creating any subtask, writing any code, or making architectural decisions to retrieve the latest specs and user preferences.
4.  **Continuous Synchronization:** All deliverables, reports, and significant code changes MUST be synced across the four core platforms:
    *   **Google Drive:** For document storage and sharing.
    *   **Notion:** For the Executive Dashboard and system architecture tracking.
    *   **Linear:** For issue tracking and project state management.
    *   **GitHub:** For all source code and configuration files (`3nz5789/coinscope-ai`).
5.  **Strict Scope Adherence:** Subtasks must operate within explicitly defined boundaries. Unsolicited feature additions (e.g., adding SEO tags to a backend task) are prohibited unless explicitly approved by the user.

---

## 4. Quick Reference

### Live Dashboards

| Environment | URL | Notes |
| :--- | :--- | :--- |
| **Primary (Main)** | `https://coinscopedash-tltanhwx.manus.space` | 16 pages, includes Stripe billing. **Use this.** |
| **Fallback (Original)** | `https://coinscopedash-cv5ce7m8.manus.space` | 10 pages, no Stripe. |
| **Reference (TradingView)** | `https://coindash-iad7x9yd.manus.space` | Prototype only. Do not use for production. |

### Workspaces & Repositories

| Platform | URL / Details |
| :--- | :--- |
| **GitHub** | `https://github.com/3nz5789/coinscope-ai` (Private) |
| **Linear** | `https://linear.app/coinscopeai/` |
| **Notion** | CoinScopeAI OS (Executive Dashboard, Engineering) |
| **Google Drive** | CoinScopeAI Shared Folder |

### Credentials & Integrations (Redacted/Test)

| Service | Details |
| :--- | :--- |
| **Telegram Bot** | `@ScoopyAI_bot` (Chat ID: 7296767446, `@CoinScopeAI24`) |
| **Stripe (Test Mode)** | PK: `pk_test_***REDACTED***` |
| **Stripe (Test Mode)** | SK: `sk_test_***REDACTED — set via .env***` |
| **Stripe Test Card** | `4242 4242 4242 4242` (Any future expiry, any CVC) |

### Engine API Endpoints (Localhost:8001)

*   `GET /scan` - Scan market signals
*   `GET /performance` - Performance metrics
*   `GET /journal` - Trade journal
*   `GET /risk-gate` - Risk gate status
*   `GET /position-size` - Position sizing
*   `GET /regime/{symbol}` - Market regime detection

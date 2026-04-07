# CoinScopeAI Strategic Plan: Current State & Immediate Next Steps

**Author:** Scoopy (CoinScopeAI Operating Agent)
**Date:** April 6, 2026

## 1) Objective

The objective of this document is to provide a clear, execution-focused assessment of the CoinScopeAI project's current state and to define the most critical, high-priority next steps. This plan aims to transition the project from its current documentation-heavy, scaffolded state into a functional, data-driven quantitative trading system capable of validating strategies and executing simulated trades.

## 2) Context / Assumptions

Based on a comprehensive review of the project artifacts, the current state of CoinScopeAI is characterized by robust architectural planning and workspace setup, but a significant lack of functional trading infrastructure.

**What Exists (The Foundation):**
The project possesses a well-defined monorepo structure hosted on GitHub (`3nz5789/coinscope-ai`), complete with CI/CD placeholders, issue templates, and a comprehensive documentation suite covering system architecture, risk management frameworks, and development workflows. The workspace tooling is highly structured, with a Notion OS containing seeded databases for projects, tasks, and research experiments, alongside a Linear workspace blueprint defining teams, projects, and issue taxonomies. The CoinScopeAI Engine API is fully documented, detailing endpoints for market scanning, performance tracking, and risk gate evaluation.

**What is Missing (The Execution Gap):**
Despite the extensive documentation, the core trading engine is not operational. The API running at `localhost:8001` is currently unreachable, and the documented responses contain synthetic or mock data (e.g., simulated trades and performance metrics). Crucially, there are no validated trading strategies, no historical data ingestion pipelines, and no backtesting framework implemented. The system lacks live exchange connectivity, meaning no real-time market data is being processed, and no order execution logic exists. The research experiments logged in Notion remain either proposed or in progress, with no approved validation reports.

**Assumptions:**
I assume the immediate goal is to achieve a "Staging candidate" environment where real market data can be ingested, backtested against a baseline strategy, and evaluated through the documented Risk Gate framework. I also assume the founder-led team requires high-leverage, AI-assisted workflows to build the data infrastructure before focusing on frontend dashboards or advanced ML models.

## 3) Analysis

To transition CoinScopeAI from a conceptual framework to a functional trading system, we must prioritize workstreams that establish the core data pipeline and strategy validation capabilities. The current roadmap outlines a logical progression, but the immediate focus must be on Phase 1 (Core Trading Engine) deliverables.

The prioritization is driven by the dependency chain: we cannot validate strategies without historical data, and we cannot execute trades (even simulated ones) without a validated strategy and exchange connectivity. Therefore, Data Engineering and Quant Research take precedence over Dashboard UI or advanced AI/ML features.

| Priority | Workstream | Rationale | Dependency |
| :--- | :--- | :--- | :--- |
| **High** | Data Ingestion & Storage | Real market data is the prerequisite for all quantitative research and backtesting. We need a reliable pipeline to fetch and store historical k-lines. | None |
| **High** | Backtesting Framework | A robust backtesting engine is required to validate the proposed strategies (e.g., Mean Reversion, Breakout) before any capital is risked. | Data Ingestion |
| **Medium** | Exchange Connectivity (Read-Only) | Establishing WebSocket connections to Binance/Bybit for real-time data feeds is necessary for the live signal engine. | Data Ingestion |
| **Medium** | Baseline Strategy Implementation | Coding the first technical strategy (e.g., Mean Reversion) to run through the backtester and establish a performance baseline. | Backtesting Framework |
| **Low** | Dashboard UI | The frontend is secondary until the backend engine generates real, validated signals and performance data. | Baseline Strategy |
| **Low** | Advanced ML Models | Regime detection and LSTM models should only be introduced after a baseline technical strategy is validated and operational. | Baseline Strategy |

## 4) Recommended Approach

The following concrete next steps are recommended to build the foundational data and research infrastructure. Each step is tagged with its target environment tier.

1.  **Implement Historical Data Ingestion Pipeline** `[Prototype]`
    Develop a Python module to fetch historical OHLCV (Open, High, Low, Close, Volume) data from the Binance API for the top 20 tracked symbols. This data must be cleaned, normalized, and stored in the PostgreSQL database to support backtesting.

2.  **Develop the Core Backtesting Engine** `[Prototype]`
    Build a custom backtesting framework or integrate an existing library (e.g., Backtrader, VectorBT) tailored to the CoinScopeAI architecture. The engine must simulate trade execution, calculate PnL, and generate the performance metrics defined in the API documentation (Sharpe ratio, max drawdown).

3.  **Validate the Baseline Mean Reversion Strategy** `[Research idea]`
    Translate the "BTC Mean Reversion" research experiment from Notion into executable Python code. Run this strategy through the new backtesting engine using the ingested historical data to generate a formal Validation Report.

4.  **Implement the Risk Gate Logic (Offline Mode)** `[Prototype]`
    Code the core Risk Gate checks (daily/weekly drawdown limits, portfolio heat) as standalone functions. Integrate these checks into the backtesting engine to evaluate how the baseline strategy performs under strict risk constraints.

5.  **Establish Read-Only WebSocket Feeds** `[Staging candidate]`
    Develop the real-time data ingestion module connecting to exchange WebSockets. This will feed the live `Trading Engine API`, replacing the current mock data with actual market prices and order book updates.

6.  **Deploy the Local Development Environment** `[Prototype]`
    Finalize the Docker Compose setup to reliably spin up the PostgreSQL database, Redis cache, and the FastAPI Trading Engine locally, ensuring all developers have a consistent environment for testing the new data pipelines.

## 5) Deliverables

To execute the recommended approach, the following specific artifacts must be created and tracked across the workspace tools.

*   **GitHub Repository (`3nz5789/coinscope-ai`):**
    *   Merge PR #1 (`feat/workspace-setup`) into `main` and branch `develop`.
    *   Create `/data/ingestion/binance_historical.py` for data fetching.
    *   Create `/strategies/backtests/engine.py` for the backtesting framework.
    *   Create `/strategies/research/mean_reversion_baseline.py` for the initial strategy logic.
    *   Update `infra/docker/docker-compose.dev.yml` with functional PostgreSQL and Redis configurations.

*   **Notion Workspace (CoinScopeAI OS):**
    *   Update the "BTC Mean Reversion backtest" Validation Report with actual performance metrics once the backtest is complete.
    *   Create a new Technical Design Document (ADR) in the Decisions database for the chosen backtesting architecture.

*   **Linear Workspace:**
    *   Create the 4 required teams manually as outlined in the blueprint.
    *   Populate the "CoinScopeAI – MVP" project backlog with the immediate next steps defined below.

## 6) Immediate Next Steps

The following three tasks represent the immediate critical path and should be dropped directly into the Linear backlog for execution.

### Task 1: Implement Historical Data Ingestion Pipeline
*   **Description:** Develop a Python script to connect to the Binance REST API and download historical 1h and 4h OHLCV data for the 20 core symbols over the past 24 months. The script must handle rate limits, clean the data, and insert it into the local PostgreSQL database.
*   **Acceptance Criteria:**
    *   Script successfully downloads 24 months of data for 20 symbols without hitting rate limits.
    *   Data is correctly formatted and stored in the PostgreSQL `market_data` table.
    *   Unit tests verify data integrity and error handling.
*   **Domain Category:** Engineering & Architecture (`dom: infra`)
*   **Priority:** P0 – critical
*   **Environment Tier:** Prototype

### Task 2: Develop Core Backtesting Engine Framework
*   **Description:** Build the foundational backtesting class that can load historical data from PostgreSQL, iterate through k-lines, execute simulated trades based on a generic signal input, and calculate basic performance metrics (Total PnL, Win Rate, Max Drawdown).
*   **Acceptance Criteria:**
    *   Engine can load data from the database efficiently.
    *   Engine correctly simulates market and limit orders with assumed slippage and fees.
    *   Engine outputs a standardized performance report matching the `/performance` API schema.
*   **Domain Category:** Quant Research (`dom: backtest`)
*   **Priority:** P0 – critical
*   **Environment Tier:** Prototype

### Task 3: Finalize Local Docker Infrastructure
*   **Description:** Update the placeholder `docker-compose.dev.yml` to spin up a fully functional local development environment, including PostgreSQL (with initialized schemas for market data and trade journals), Redis, and the FastAPI application shell.
*   **Acceptance Criteria:**
    *   Running `docker-compose up` successfully starts all required services.
    *   FastAPI application can connect to both PostgreSQL and Redis without errors.
    *   Database schemas are automatically applied on startup via migration scripts (e.g., Alembic).
*   **Domain Category:** Engineering & Architecture (`dom: infra`)
*   **Priority:** P1 – high
*   **Environment Tier:** Prototype

# CoinScopeAI Project Overview

**Author:** Manus AI
**Date:** April 6, 2026

This document provides a comprehensive overview of the CoinScopeAI project, its goals, architecture, and operational philosophy. It serves as the primary entry point for anyone seeking to understand the project at a strategic level.

## 1. What is CoinScopeAI?

CoinScopeAI is an advanced, autonomous cryptocurrency futures trading agent. It leverages machine learning, real-time market data, and strict risk management protocols to identify, execute, and manage trading opportunities across major crypto exchanges. The system is designed to operate 24/7 with minimal human intervention, while maintaining robust safety guardrails that prevent catastrophic losses.

## 2. Vision

To provide institutional-grade, AI-driven quantitative trading capabilities to individual traders and funds, democratizing access to sophisticated market analysis and automated execution.

## 3. Mission

To build a resilient, transparent, and highly profitable trading system that prioritizes capital preservation through dynamic risk management while capitalizing on market inefficiencies using advanced machine learning models.

## 4. Target Users

| User Segment | Description |
| :--- | :--- |
| **Quantitative Analysts** | Seeking a robust framework to deploy, backtest, and monitor custom trading algorithms. |
| **Professional Traders** | Looking to automate their technical strategies and manage risk across multiple assets simultaneously without constant manual monitoring. |
| **Crypto Funds** | Requiring a scalable, containerized infrastructure for executing high-frequency or statistical arbitrage strategies. |

## 5. Core Value Propositions

| Proposition | Description |
| :--- | :--- |
| **Emotionless Execution** | Eliminates human psychological biases (fear and greed) by strictly adhering to pre-defined, backtested logic. |
| **24/7 Market Surveillance** | Continuously scans dozens of cryptocurrency pairs simultaneously, identifying opportunities that a human trader would miss. |
| **Dynamic Risk Management** | The proprietary "Risk Gate" system automatically adjusts position sizing and halts trading during unfavorable market regimes, protecting capital during flash crashes or extreme volatility. |
| **AI-Enhanced Signals** | Goes beyond simple technical indicators by using machine learning to classify market regimes and assign probabilistic confidence scores to trading signals. |

## 6. Technology Stack

| Component | Technology | Justification |
| :--- | :--- | :--- |
| **Backend API** | Python 3.11+, FastAPI | High performance, excellent async support, native integration with data science libraries. |
| **AI/ML** | PyTorch, Scikit-learn, Pandas | Industry standard for machine learning and data manipulation. |
| **Database** | PostgreSQL, SQLAlchemy | Robust relational data storage with strong ACID compliance. |
| **Caching/Queue** | Redis, Celery | Fast in-memory storage for real-time data and asynchronous task processing. |
| **Frontend** | React 18, Vite, Tailwind CSS | Fast development cycle, component-based architecture, responsive design. |
| **Bot Integration** | Python, python-telegram-bot | Reliable and feature-rich library for Telegram bot development. |
| **Infrastructure** | Docker, Kubernetes, GitHub Actions | Containerization for consistent environments, orchestration for scalability and high availability. |

## 7. Repository Structure

This project follows a **monorepo** approach. All code, documentation, infrastructure, and configuration live in a single repository for maximum simplicity and coherence. The key top-level directories are:

| Directory | Purpose |
| :--- | :--- |
| `docs/` | All project documentation (architecture, roadmap, risk framework, design system, API docs). |
| `apps/` | User-facing applications (web dashboard). |
| `services/` | Backend microservices (trading engine, Telegram bot). |
| `ai/` | Machine learning models, training pipelines, feature engineering, and evaluation. |
| `strategies/` | Trading strategy definitions, backtesting configs, and research notes. |
| `data/` | Data pipelines, raw/processed data directories (contents gitignored). |
| `infra/` | Infrastructure as code (Docker, Kubernetes, Terraform, monitoring). |
| `scripts/` | Utility and automation scripts. |
| `notebooks/` | Jupyter notebooks for research and exploration. |
| `tests/` | Top-level integration and end-to-end tests. |
| `configs/` | Centralized environment and secrets configuration. |
| `.github/` | GitHub Actions workflows, issue templates, and PR templates. |

## 8. Key Documents

For deeper understanding, refer to the following documents:

| Document | Path | Description |
| :--- | :--- | :--- |
| System Architecture | `docs/system_architecture.md` | Detailed component breakdown, data flow, and technology stack. |
| Feature Roadmap | `docs/feature_roadmap.md` | Planned development phases from MVP to production scaling. |
| Risk Management Framework | `docs/risk_management_framework.md` | Risk Gate, position sizing, and capital protection strategies. |
| Design System | `docs/design_system.md` | UI/UX guidelines and color palette for the web dashboard. |
| API Exploration | `docs/api_exploration.md` | Comprehensive API endpoint documentation with examples. |
| Development Workflow | `DEVELOPMENT_WORKFLOW.md` | Git branching strategy, CI/CD pipelines, and testing requirements. |
| Contributing Guide | `CONTRIBUTING.md` | How to contribute to the project. |
| Manus Operating SOP | `MANUS_OPERATING_SOP.md` | Rules for how the Manus AI agent interacts with this repository. |

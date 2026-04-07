# CoinScopeAI Project Structure

**Author:** Manus AI
**Date:** April 6, 2026

This document provides a comprehensive map of the CoinScopeAI repository. Every directory and key file is listed with a description of its purpose. The project is organized into five primary layers: **Backend** (Trading Engine), **Frontend** (Web Dashboard), **Bot** (Telegram Alerts), **AI** (Machine Learning), and **Infrastructure** (DevOps & Config).

## Directory Tree with Annotations

```
coinscopeai_project/
│
├── .github/                              # GitHub-specific configuration
│   ├── workflows/
│   │   ├── ci.yml                        # CI pipeline: lint, test, build on every PR
│   │   ├── cd.yml                        # CD pipeline: deploy to staging/production
│   │   └── test.yml                      # Dedicated test runner workflow
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md                 # Standardized bug report template
│   │   └── feature_request.md            # Standardized feature request template
│   └── PULL_REQUEST_TEMPLATE.md          # PR description template with checklist
│
├── backend/                              # ── CORE TRADING ENGINE (Python / FastAPI) ──
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── scan.py               # GET /scan — Market signal scanning
│   │   │   │   ├── performance.py        # GET /performance — Performance metrics
│   │   │   │   ├── journal.py            # GET /journal — Trade journal records
│   │   │   │   ├── risk.py               # GET /risk-gate — Risk gate status
│   │   │   │   ├── regime.py             # GET /regime/{symbol} — Market regime
│   │   │   │   ├── position.py           # GET /position-size — Position calculator
│   │   │   │   └── websocket.py          # WebSocket for real-time streaming
│   │   │   └── router.py                 # API v1 route aggregator
│   │   ├── core/
│   │   │   ├── config.py                 # App config (env vars, settings, Pydantic)
│   │   │   ├── security.py               # Auth, API key mgmt, encryption
│   │   │   └── logging.py                # Structured logging (JSON format)
│   │   ├── models/
│   │   │   ├── trade.py                  # SQLAlchemy: Trade model
│   │   │   ├── signal.py                 # SQLAlchemy: Signal model
│   │   │   ├── user.py                   # SQLAlchemy: User model
│   │   │   └── portfolio.py              # SQLAlchemy: Portfolio state model
│   │   ├── schemas/
│   │   │   ├── trade.py                  # Pydantic: Trade request/response
│   │   │   ├── signal.py                 # Pydantic: Signal data schemas
│   │   │   ├── risk.py                   # Pydantic: Risk gate schemas
│   │   │   └── performance.py            # Pydantic: Performance metric schemas
│   │   ├── services/
│   │   │   ├── trading/
│   │   │   │   ├── engine.py             # Core trading logic orchestration
│   │   │   │   ├── executor.py           # Exchange order execution (Binance/Bybit)
│   │   │   │   └── order_manager.py      # Order lifecycle (SL/TP/trailing stops)
│   │   │   ├── analysis/
│   │   │   │   ├── technical.py          # Technical indicators (RSI, MACD, BB, EMA)
│   │   │   │   ├── sentiment.py          # Sentiment analysis integration
│   │   │   │   └── regime.py             # Market regime detection service
│   │   │   └── risk/
│   │   │       ├── gate.py               # Risk Gate controller (drawdown checks)
│   │   │       ├── position_sizer.py     # Position sizing (fixed-fractional, Kelly)
│   │   │       └── portfolio.py          # Portfolio-level risk aggregation
│   │   ├── db/
│   │   │   ├── session.py                # Database session factory
│   │   │   └── base.py                   # SQLAlchemy declarative base
│   │   ├── utils/
│   │   │   ├── helpers.py                # General utility functions
│   │   │   └── validators.py             # Input validation helpers
│   │   ├── middleware/
│   │   │   ├── rate_limiter.py           # API rate limiting
│   │   │   └── error_handler.py          # Global error handling
│   │   └── main.py                       # FastAPI application entry point
│   ├── tests/
│   │   ├── unit/                         # Unit tests for functions/classes
│   │   ├── integration/                  # API + DB integration tests
│   │   ├── e2e/                          # End-to-end workflow tests
│   │   └── conftest.py                   # Shared pytest fixtures
│   ├── migrations/                       # Alembic database migrations
│   ├── scripts/                          # Backend utility scripts
│   ├── requirements.txt                  # Python dependencies
│   └── Dockerfile                        # Backend container image
│
├── frontend/                             # ── WEB DASHBOARD (React / Vite / Tailwind) ──
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/                   # Reusable UI primitives
│   │   │   │   ├── Button.tsx            # Primary/secondary/danger buttons
│   │   │   │   ├── Card.tsx              # Data card container
│   │   │   │   ├── Modal.tsx             # Overlay dialog component
│   │   │   │   ├── Table.tsx             # Sortable, filterable data table
│   │   │   │   └── Badge.tsx             # Status/direction badge (Long/Short)
│   │   │   ├── dashboard/               # Dashboard-specific widgets
│   │   │   │   ├── SignalCard.tsx         # Individual signal summary
│   │   │   │   ├── PerformanceWidget.tsx # Key metrics (PnL, Win Rate)
│   │   │   │   ├── RiskGauge.tsx         # Visual risk level indicator
│   │   │   │   └── MarketOverview.tsx    # Market summary with regime info
│   │   │   ├── charts/                   # Data visualization components
│   │   │   │   ├── EquityCurve.tsx       # Account equity over time
│   │   │   │   ├── PnlChart.tsx          # Profit/Loss distribution
│   │   │   │   ├── RegimeChart.tsx       # Market regime timeline
│   │   │   │   └── DrawdownChart.tsx     # Drawdown depth and duration
│   │   │   ├── trading/                  # Trading-specific components
│   │   │   │   ├── SignalTable.tsx        # Full signal list with filters
│   │   │   │   ├── PositionSizer.tsx     # Interactive position calculator
│   │   │   │   └── OrderPanel.tsx        # Manual order entry panel
│   │   │   ├── risk/                     # Risk management components
│   │   │   │   ├── RiskGate.tsx          # Risk gate status display
│   │   │   │   ├── PortfolioHeat.tsx     # Portfolio exposure heatmap
│   │   │   │   └── DrawdownMonitor.tsx   # Real-time drawdown tracker
│   │   │   └── layout/                   # Application shell
│   │   │       ├── Sidebar.tsx           # Navigation sidebar
│   │   │       ├── Header.tsx            # Top bar (status, search)
│   │   │       └── Footer.tsx            # Footer with version info
│   │   ├── pages/                        # Route-level page components
│   │   │   ├── Dashboard.tsx             # Main overview dashboard
│   │   │   ├── Trading.tsx               # Signal exploration & execution
│   │   │   ├── Journal.tsx               # Historical trade journal
│   │   │   ├── Performance.tsx           # Detailed performance analytics
│   │   │   ├── RiskManagement.tsx        # Risk console & configuration
│   │   │   └── Settings.tsx              # User and system settings
│   │   ├── hooks/                        # Custom React hooks
│   │   │   ├── useSignals.ts             # Fetch/subscribe to signals
│   │   │   ├── usePerformance.ts         # Performance data hook
│   │   │   ├── useRiskGate.ts            # Risk gate status hook
│   │   │   └── useWebSocket.ts           # Generic WebSocket hook
│   │   ├── services/                     # API client wrappers
│   │   │   ├── api.ts                    # REST client for backend API
│   │   │   └── websocket.ts              # WebSocket client manager
│   │   ├── store/                        # Global state (Zustand)
│   │   │   ├── index.ts                  # Store initialization
│   │   │   ├── signalStore.ts            # Signal-related state
│   │   │   └── tradeStore.ts             # Trade-related state
│   │   ├── styles/
│   │   │   ├── globals.css               # Tailwind base/components/utilities
│   │   │   └── theme.ts                  # Design system tokens
│   │   ├── types/                        # TypeScript type definitions
│   │   │   ├── index.ts, signal.ts       # Signal, trade, risk types
│   │   │   ├── trade.ts
│   │   │   └── risk.ts
│   │   ├── utils/
│   │   │   ├── formatters.ts             # Number/date/currency formatters
│   │   │   └── constants.ts              # App constants
│   │   ├── assets/                       # Static assets (images, icons, fonts)
│   │   ├── App.tsx                       # Root application component
│   │   └── main.tsx                      # Vite entry point
│   ├── public/                           # Static public assets
│   ├── tests/                            # Frontend tests (Vitest)
│   ├── package.json, tsconfig.json       # Node.js / TypeScript config
│   ├── vite.config.ts, tailwind.config.ts
│   └── Dockerfile                        # Frontend container image
│
├── bot/                                  # ── TELEGRAM BOT ALERT SERVICE ──
│   ├── handlers/
│   │   ├── alerts.py                     # Trade alert message handlers
│   │   ├── commands.py                   # /start, /status, /help commands
│   │   └── callbacks.py                  # Inline keyboard callbacks
│   ├── services/
│   │   ├── notifier.py                   # Core notification dispatch
│   │   ├── formatter.py                  # Message formatting (Markdown/HTML)
│   │   └── scheduler.py                  # Scheduled reports (daily summary)
│   ├── templates/
│   │   ├── signal_alert.py               # New signal notification template
│   │   ├── risk_alert.py                 # Risk warning notification template
│   │   └── performance_report.py         # Daily/weekly performance template
│   ├── main.py                           # Bot application entry point
│   ├── config.py                         # Bot-specific configuration
│   ├── requirements.txt                  # Bot dependencies
│   └── Dockerfile                        # Bot container image
│
├── ai/                                   # ── AI / MACHINE LEARNING PIPELINE ──
│   ├── models/
│   │   ├── signal_classifier.py          # ML signal confidence scoring
│   │   ├── regime_detector.py            # Market regime classification
│   │   ├── sentiment_analyzer.py         # NLP news/social sentiment
│   │   └── risk_predictor.py             # Volatility forecasting model
│   ├── pipelines/
│   │   ├── prediction.py                 # Real-time inference pipeline
│   │   ├── training.py                   # Model training orchestration
│   │   └── backtesting.py                # Strategy backtesting framework
│   ├── features/
│   │   ├── technical.py                  # Technical indicator features
│   │   ├── market.py                     # Market microstructure features
│   │   └── sentiment.py                  # Sentiment-derived features
│   ├── training/
│   │   ├── trainer.py                    # Training loop & checkpointing
│   │   └── hyperparams.py                # Hyperparameter search config
│   ├── evaluation/
│   │   ├── metrics.py                    # Custom metrics (Sharpe, Sortino)
│   │   └── backtester.py                 # Historical performance evaluator
│   ├── notebooks/                        # Jupyter notebooks for research
│   ├── config.py                         # AI pipeline configuration
│   └── requirements.txt                  # AI/ML dependencies
│
├── config/                               # ── CENTRALIZED CONFIGURATION ──
│   ├── environments/
│   │   ├── development.yaml              # Dev environment settings
│   │   ├── staging.yaml                  # Staging environment settings
│   │   └── production.yaml               # Production environment settings
│   └── secrets/                          # Secrets (managed externally)
│
├── infra/                                # ── INFRASTRUCTURE AS CODE ──
│   ├── docker/
│   │   ├── docker-compose.dev.yml        # Dev stack (all services)
│   │   └── docker-compose.prod.yml       # Production stack (optimized)
│   ├── k8s/
│   │   ├── deployment.yaml               # K8s deployment manifests
│   │   ├── service.yaml                  # K8s service definitions
│   │   ├── ingress.yaml                  # Ingress controller config
│   │   └── configmap.yaml                # Environment config maps
│   ├── terraform/
│   │   ├── main.tf                       # Cloud infra (AWS/GCP)
│   │   ├── variables.tf                  # Terraform variables
│   │   └── outputs.tf                    # Terraform outputs
│   └── monitoring/
│       ├── prometheus.yml                # Prometheus scrape config
│       ├── grafana-dashboard.json        # Pre-built Grafana dashboard
│       └── alertmanager.yml              # Alert routing rules
│
├── scripts/                              # ── OPERATIONAL SCRIPTS ──
│   ├── setup/
│   │   ├── init.sh                       # First-time project initialization
│   │   └── install-deps.sh              # Dependency installation
│   ├── deploy/
│   │   ├── deploy.sh                     # Deployment automation
│   │   └── rollback.sh                   # Rollback to previous version
│   └── data/
│       ├── seed.py                       # Database seeding (sample data)
│       └── migrate.py                    # Database migration runner
│
├── tests/                                # ── CROSS-CUTTING TEST SUITES ──
│   ├── load/                             # Load/stress testing (Locust/k6)
│   └── smoke/                            # Post-deployment smoke tests
│
├── docs/                                 # ── PROJECT DOCUMENTATION ──
│   ├── architecture.md                   # System architecture document
│   ├── roadmap.md                        # Feature roadmap by phase
│   ├── design-system.md                  # UI/UX design system spec
│   ├── development-workflow.md           # Git, CI/CD, testing workflow
│   └── risk-management.md               # Risk management framework
│
├── diagrams/                             # Rendered diagram images
│   └── architecture.png                  # System architecture (rendered)
│
├── architecture.mmd                      # Mermaid source: system architecture
├── docker-compose.yml                    # Root Docker Compose (full stack)
├── Makefile                              # Common dev commands (make test, etc.)
├── pyproject.toml                        # Python project metadata (PEP 621)
├── .env.example                          # Environment variable template
├── .gitignore                            # Git ignore rules
├── PROJECT_STRUCTURE.md                  # This file
└── README.md                             # Main project overview
```

## Summary Statistics

| Metric | Count |
| :--- | :--- |
| **Total Directories** | 76 |
| **Total Files** | 188 |
| **Backend Files** | 52 |
| **Frontend Files** | 58 |
| **Bot Files** | 18 |
| **AI/ML Files** | 22 |
| **Infrastructure Files** | 14 |
| **Documentation Files** | 8 |

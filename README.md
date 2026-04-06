# CoinScopeAI — Crypto Futures Trading Agent

**CoinScopeAI** is an advanced, autonomous cryptocurrency futures trading agent. It leverages machine learning, real-time market data, and strict risk management protocols to identify, execute, and manage trading opportunities across major crypto exchanges.

## Vision and Mission

**Vision:** To provide institutional-grade, AI-driven quantitative trading capabilities to individual traders and funds, democratizing access to sophisticated market analysis and automated execution.

**Mission:** To build a resilient, transparent, and highly profitable trading system that prioritizes capital preservation through dynamic risk management while capitalizing on market inefficiencies using advanced machine learning models.

## Target Users

| Segment | Description |
| :--- | :--- |
| **Quantitative Analysts** | Seeking a robust framework to deploy, backtest, and monitor custom trading algorithms. |
| **Professional Traders** | Looking to automate their technical strategies and manage risk across multiple assets simultaneously. |
| **Crypto Funds** | Requiring a scalable, containerized infrastructure for executing high-frequency or statistical arbitrage strategies. |

## Core Value Propositions

| Proposition | Description |
| :--- | :--- |
| **Emotionless Execution** | Eliminates human psychological biases by strictly adhering to pre-defined, backtested logic. |
| **24/7 Market Surveillance** | Continuously scans dozens of cryptocurrency pairs simultaneously. |
| **Dynamic Risk Management** | The proprietary "Risk Gate" system automatically adjusts position sizing and halts trading during unfavorable conditions. |
| **AI-Enhanced Signals** | Uses machine learning to classify market regimes and assign probabilistic confidence scores. |

## Repository Structure

This is a **monorepo** containing all CoinScopeAI components:

```
coinscope-ai/
├── docs/                    # Project documentation
├── apps/dashboard/          # Web dashboard (React/Vite/Tailwind)
├── services/
│   ├── trading-engine/      # Core trading engine (Python/FastAPI)
│   └── telegram-bot/        # Telegram alert service
├── ai/                      # ML models, training, evaluation
├── strategies/              # Trading strategy definitions & backtests
├── data/                    # Data pipelines (contents gitignored)
├── infra/                   # Docker, K8s, Terraform, monitoring
├── scripts/                 # Utility scripts
├── notebooks/               # Jupyter research notebooks
├── tests/                   # Top-level integration tests
├── configs/                 # Environment & secrets configuration
├── coinscope_trading_engine/# Legacy engine (being migrated)
└── .github/                 # CI/CD workflows, issue & PR templates
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

| Document | Description |
| :--- | :--- |
| [Project Overview](docs/project_overview.md) | High-level project summary and repository guide. |
| [System Architecture](docs/system_architecture.md) | Detailed component breakdown, data flow, and technology stack. |
| [Feature Roadmap](docs/feature_roadmap.md) | Planned development phases from MVP to production scaling. |
| [Risk Management Framework](docs/risk_management_framework.md) | Risk Gate, position sizing, and capital protection strategies. |
| [Design System](docs/design_system.md) | UI/UX guidelines and color palette for the web dashboard. |
| [API Exploration](docs/api_exploration.md) | Comprehensive API endpoint documentation with examples. |
| [Project Structure](docs/project_structure.md) | Complete map of the repository directory layout. |

Additional root-level documents:

| Document | Description |
| :--- | :--- |
| [Development Workflow](DEVELOPMENT_WORKFLOW.md) | Git branching strategy, CI/CD pipelines, and testing requirements. |
| [Contributing Guide](CONTRIBUTING.md) | How to contribute to the project. |
| [Manus Operating SOP](MANUS_OPERATING_SOP.md) | Rules for how the Manus AI agent interacts with this repository. |

## Technology Stack

| Component | Technology |
| :--- | :--- |
| **Backend / Core Engine** | Python 3.11+, FastAPI, SQLAlchemy, Pydantic |
| **AI / Machine Learning** | PyTorch, Scikit-learn, Pandas, NumPy |
| **Frontend Dashboard** | React 18, TypeScript, Vite, Tailwind CSS |
| **Database and Caching** | PostgreSQL, Redis |
| **Infrastructure** | Docker, Kubernetes, GitHub Actions |
| **Integrations** | Binance/Bybit APIs, Telegram Bot API, OpenAI API |

## Getting Started

> **Note:** This project is currently in active development. The following instructions are for setting up the development environment.

### Prerequisites

The development environment requires Docker and Docker Compose, Python 3.11+, Node.js 20+, and Make.

### Installation

1. **Clone the repository:**
    ```bash
    git clone https://github.com/3nz5789/coinscope-ai.git
    cd coinscope-ai
    ```

2. **Set up environment variables:**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys (Exchange, Telegram, OpenAI)
    ```

3. **Start the infrastructure (Database, Redis):**
    ```bash
    docker-compose -f infra/docker/docker-compose.dev.yml up -d db redis
    ```

4. **Run the Backend Engine:**
    ```bash
    cd services/trading-engine
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8001
    ```

5. **Run the Frontend Dashboard:**
    ```bash
    cd apps/dashboard
    npm install
    npm run dev
    ```

## Branching Strategy

| Branch | Purpose |
| :--- | :--- |
| `main` | Production-ready code. Direct commits prohibited. |
| `develop` | Integration branch for the next release. |
| `feat/*` | New features (e.g., `feat/123-ai-regime-detection`). |
| `bugfix/*` | Non-critical bug fixes (e.g., `bugfix/456-chart-rendering`). |
| `hotfix/*` | Critical production fixes (e.g., `hotfix/789-api-crash`). |

Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) specification: `<type>(<scope>): <subject>`.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

# CoinScopeAI — Crypto Futures Trading Agent

**CoinScopeAI** is an advanced, autonomous cryptocurrency futures trading agent. It leverages machine learning, real-time market data, and strict risk management protocols to identify, execute, and manage trading opportunities across major crypto exchanges.

![System Architecture](https://private-us-east-1.manuscdn.com/sessionFile/5AzyJ2bZMc2NooGTkTronG/sandbox/uUyHeNRfsM59SVgNexRkt5-images_1775767754969_na1fn_L2hvbWUvdWJ1bnR1L2NvaW5zY29wZWFpX3Byb2plY3QvZGlhZ3JhbXMvYXJjaGl0ZWN0dXJl.png?Policy=eyJTdGF0ZW1lbnQiOlt7IlJlc291cmNlIjoiaHR0cHM6Ly9wcml2YXRlLXVzLWVhc3QtMS5tYW51c2Nkbi5jb20vc2Vzc2lvbkZpbGUvNUF6eUoyYlpNYzJOb29HVGtUcm9uRy9zYW5kYm94L3VVeUhlTlJmc001OVNWZ05leFJrdDUtaW1hZ2VzXzE3NzU3Njc3NTQ5NjlfbmExZm5fTDJodmJXVXZkV0oxYm5SMUwyTnZhVzV6WTI5d1pXRnBYM0J5YjJwbFkzUXZaR2xoWjNKaGJYTXZZWEpqYUdsMFpXTjBkWEpsLnBuZyIsIkNvbmRpdGlvbiI6eyJEYXRlTGVzc1RoYW4iOnsiQVdTOkVwb2NoVGltZSI6MTc5ODc2MTYwMH19fV19&Key-Pair-Id=K2HSFNDJXOU9YS&Signature=V13f0O7qOpkn0aLgSO7aFbo4rfpL9IV75Ao3Vg2Fg39p29j6pbY0Ebcf-jQsPuNs-n~lNzhkMmr3OTVmPzb3htmq9cz5zdww9uWdUHrw1yzpLR05wW9xkq9LMVXZPQL-Qa8G6WF9yJXTZTNumZIFtpPOLJa6yL0Ue9DnTtPri0zaONzfPdAX0EFnvM2rO4meZ2J8lh8PgkPLfu16dh78QDvce3uWyAiUhljLSFxPUfZoWut5EiZt56Drs2LNuQiAIyfhRxXfFQoKwmEJCK4OoAlXq7Dko4qqMflRtMYsETAP-2N55MAaTOQGK~Mj2~dUzx5AeYeRy~gdor5ucejNZg__)

## 🚀 Vision & Mission

**Vision:** To provide institutional-grade, AI-driven quantitative trading capabilities to individual traders and funds, democratizing access to sophisticated market analysis and automated execution.

**Mission:** To build a resilient, transparent, and highly profitable trading system that prioritizes capital preservation through dynamic risk management while capitalizing on market inefficiencies using advanced machine learning models.

## 🎯 Target Users

*   **Quantitative Analysts:** Seeking a robust framework to deploy, backtest, and monitor custom trading algorithms.
*   **Professional Traders:** Looking to automate their technical strategies and manage risk across multiple assets simultaneously without constant manual monitoring.
*   **Crypto Funds:** Requiring a scalable, containerized infrastructure for executing high-frequency or statistical arbitrage strategies.

## 💡 Value Proposition

1.  **Emotionless Execution:** Eliminates human psychological biases (fear and greed) by strictly adhering to pre-defined, backtested logic.
2.  **24/7 Market Surveillance:** Continuously scans dozens of cryptocurrency pairs simultaneously, identifying opportunities that a human trader would miss.
3.  **Dynamic Risk Management:** The proprietary "Risk Gate" system automatically adjusts position sizing and halts trading during unfavorable market regimes, protecting capital during flash crashes or extreme volatility.
4.  **AI-Enhanced Signals:** Goes beyond simple technical indicators by using machine learning to classify market regimes and assign probabilistic confidence scores to trading signals.

## 📚 Documentation

Comprehensive documentation is available in the `/docs` directory:

*   [System Architecture](docs/architecture.md): Detailed component breakdown, data flow, and technology stack.
*   [Feature Roadmap](docs/roadmap.md): The planned development phases from MVP to production scaling.
*   [Risk Management Framework](docs/risk-management.md): In-depth explanation of the Risk Gate, position sizing, and capital protection strategies.
*   [Design System](docs/design-system.md): UI/UX guidelines and color palette for the web dashboard.
*   [Development Workflow](docs/development-workflow.md): Git branching strategy, CI/CD pipelines, and testing requirements.
*   [API Exploration](docs/coinscopeai_api_exploration.md): Comprehensive API endpoint documentation with request/response examples.
*   [Project Structure](PROJECT_STRUCTURE.md): A complete map of the repository's directory layout.

## 🛠️ Technology Stack

*   **Backend / Core Engine:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic
*   **AI / Machine Learning:** PyTorch, Scikit-learn, Pandas, NumPy
*   **Frontend Dashboard:** React 18, TypeScript, Vite, Tailwind CSS
*   **Database & Caching:** PostgreSQL, Redis
*   **Infrastructure:** Docker, Kubernetes, GitHub Actions
*   **Integrations:** Binance/Bybit APIs, Telegram Bot API, OpenAI API

## 🚦 Getting Started

*(Note: This project is currently in active development. The following instructions are for setting up the development environment.)*

### Prerequisites

*   Docker and Docker Compose
*   Python 3.11+
*   Node.js 20+
*   Make

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/coinscopeai.git
    cd coinscopeai
    ```

2.  **Set up environment variables:**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys (Exchange, Telegram, OpenAI)
    ```

3.  **Start the infrastructure (Database, Redis):**
    ```bash
    docker-compose -f infra/docker/docker-compose.dev.yml up -d db redis
    ```

4.  **Run the Backend Engine:**
    ```bash
    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8001
    ```

5.  **Run the Frontend Dashboard:**
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

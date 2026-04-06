# CoinScopeAI Development Workflow

**Author:** Manus AI
**Date:** April 6, 2026

This document outlines the standard development workflow for the CoinScopeAI project. It covers version control, continuous integration/continuous deployment (CI/CD), testing strategies, and the code review process to ensure high-quality, reliable software delivery.

## 1. Version Control (Git)

The project uses Git for version control, hosted on GitHub. We follow a modified Gitflow workflow tailored for continuous delivery.

### 1.1 Branching Strategy

*   **`main`:** The production-ready branch. Code here is always deployable. Direct commits are prohibited.
*   **`develop`:** The primary integration branch for the next release. Feature branches merge here.
*   **`feature/*`:** Created from `develop` for new features or significant enhancements (e.g., `feature/ai-regime-detection`).
*   **`bugfix/*`:** Created from `develop` to fix non-critical issues (e.g., `bugfix/dashboard-chart-rendering`).
*   **`hotfix/*`:** Created directly from `main` to address critical production issues (e.g., `hotfix/api-rate-limit-crash`). Merged back into both `main` and `develop`.
*   **`release/*`:** Created from `develop` when preparing for a new production release. Used for final testing and version bumping before merging into `main`.

### 1.2 Commit Messages

Commit messages must follow the Conventional Commits specification to enable automated changelog generation and semantic versioning.

**Format:** `<type>(<scope>): <subject>`

*   **Types:** `feat` (new feature), `fix` (bug fix), `docs` (documentation), `style` (formatting), `refactor` (code restructuring), `test` (adding tests), `chore` (maintenance).
*   **Example:** `feat(trading): implement Kelly Criterion position sizing`

## 2. Continuous Integration & Deployment (CI/CD)

We utilize GitHub Actions for automated testing, building, and deployment pipelines.

### 2.1 Continuous Integration (CI)

The CI pipeline runs automatically on every pull request (PR) targeting `develop` or `main`.

1.  **Linting & Formatting:**
    *   *Backend (Python):* `flake8` for linting, `black` for formatting, `mypy` for static type checking.
    *   *Frontend (TypeScript/React):* `eslint` and `prettier`.
2.  **Unit Testing:**
    *   *Backend:* `pytest` is executed. Code coverage must remain above 80%.
    *   *Frontend:* `vitest` and React Testing Library are used for component tests.
3.  **Security Scanning:**
    *   `bandit` (Python) and `npm audit` (Node.js) run to detect known vulnerabilities in dependencies.
4.  **Build Verification:**
    *   Docker images are built to ensure the application containerizes successfully without errors.

### 2.2 Continuous Deployment (CD)

The CD pipeline is triggered upon merging code into specific branches.

*   **Staging Environment:** Merging into `develop` automatically deploys the application to a staging environment (e.g., a dedicated Kubernetes namespace) for integration testing and QA.
*   **Production Environment:** Merging a `release/*` or `hotfix/*` branch into `main` triggers the production deployment pipeline. This process requires manual approval from a designated release manager before the final rollout.

## 3. Testing Strategy

A robust testing strategy is critical for a financial application like CoinScopeAI.

### 3.1 Unit Tests

*   **Scope:** Individual functions, classes, and methods.
*   **Focus:** Core trading logic, risk calculations (e.g., position sizing formulas), and data parsing.
*   **Tools:** `pytest` (Backend), `vitest` (Frontend).
*   **Requirement:** All new features must include comprehensive unit tests.

### 3.2 Integration Tests

*   **Scope:** Interactions between different components (e.g., API endpoints interacting with the database or the trading engine).
*   **Focus:** Ensuring data flows correctly through the system and API responses match expected schemas.
*   **Tools:** `pytest` with FastAPI's `TestClient`, utilizing a separate test database.

### 3.3 End-to-End (E2E) Tests

*   **Scope:** The entire application flow, from the user interface down to the database.
*   **Focus:** Critical user journeys, such as logging in, viewing the dashboard, and simulating a trade execution.
*   **Tools:** Playwright or Cypress.

### 3.4 Backtesting (AI/Trading Logic)

*   **Scope:** Evaluating the performance of trading strategies and AI models against historical market data.
*   **Focus:** Validating profitability, drawdown, and risk metrics before deploying new logic to live trading.
*   **Tools:** Custom Python backtesting framework integrated with the AI pipeline.

## 4. Code Review Process

All code changes must undergo a peer review before being merged into `develop` or `main`.

1.  **Pull Request Creation:** The developer creates a PR, ensuring the CI pipeline passes and the PR description clearly explains the changes and links to relevant issue tickets.
2.  **Reviewer Assignment:** At least one core team member is assigned to review the code.
3.  **Review Criteria:**
    *   **Correctness:** Does the code solve the problem without introducing new bugs?
    *   **Readability:** Is the code clean, well-documented, and easy to understand?
    *   **Security:** Are there any potential vulnerabilities (e.g., SQL injection, exposed secrets)?
    *   **Performance:** Are there any inefficient algorithms or database queries?
    *   **Test Coverage:** Are the new changes adequately tested?
4.  **Approval & Merge:** Once the reviewer approves the PR and all CI checks pass, the code can be merged. We prefer "Squash and Merge" to keep the commit history clean.

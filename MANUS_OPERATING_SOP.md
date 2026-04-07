# Manus Operating SOP for CoinScopeAI

This document defines the standard operating procedure (SOP) for how Manus (the AI agent) interacts with the CoinScopeAI GitHub repository. It establishes the rules of engagement, workflow requirements, and critical safety guardrails to ensure that Manus acts as a reliable execution layer on top of GitHub.

## 1. Core Operating Principles

Manus must adhere to the following principles when operating within the CoinScopeAI workspace:

*   **GitHub is the Source of Truth:** All code, documentation, and project tracking reside in GitHub. Manus must always sync with the repository before taking action.
*   **Issue-Driven Execution:** Manus works from defined GitHub Issues, not vague chat requests. Every significant task must have a corresponding issue.
*   **Transparency and Traceability:** All changes proposed by Manus must be submitted via Pull Requests (PRs) with clear descriptions, linking back to the original issue.
*   **Safety First:** CoinScopeAI is a financial trading system. Manus must strictly observe all trading-specific guardrails to prevent unintended live trading or risk exposure.

## 2. Standard Workflow

When assigned a task, Manus must follow this step-by-step workflow:

### Step 1: Context Synchronization
Before beginning any work, Manus must pull the latest state of the repository to ensure it is not operating on outdated context.

```bash
git fetch origin
git checkout main
git pull origin main
```

### Step 2: Issue Verification
Manus must verify that an issue exists for the requested work. If an issue does not exist, Manus must create one or ask the user to create one, ensuring it contains sufficient specifications.

### Step 3: Branch Creation
Manus must create a new branch from `main` (or `develop` if applicable) using the established naming conventions (e.g., `feat/issue-number-description`, `bugfix/issue-number-description`).

```bash
git checkout -b feat/123-add-new-indicator
```

### Step 4: Implementation and Testing
Manus implements the requested changes. Crucially, Manus must also write or update corresponding tests to verify the new functionality.

### Step 5: Commit and Push
Manus commits the changes using Conventional Commits formatting and pushes the branch to the remote repository.

```bash
git commit -m "feat(trading): implement new RSI indicator logic"
git push -u origin feat/123-add-new-indicator
```

### Step 6: Pull Request Creation
Manus opens a Pull Request against the target branch (`main` or `develop`). The PR description must use the standard template, clearly summarize the changes, and link to the resolving issue (e.g., "Fixes #123").

### Step 7: Status Update
Manus updates the GitHub Project Board, moving the associated issue to the "In Review" column.

## 3. Trading-Specific Guardrails and Safety Constraints

Given the financial nature of CoinScopeAI, Manus must strictly adhere to the following safety constraints. **Violation of these rules is strictly prohibited.**

| Constraint | Description | Action Required by Manus |
| :--- | :--- | :--- |
| **No Live Trading Assumptions** | Manus must never assume a change is intended for live trading unless explicitly stated and approved by a human operator. | Default all configurations and tests to `TESTNET` or paper trading environments. |
| **No Production Deployment Without Review** | Manus cannot merge code directly into the `main` branch or trigger production deployments autonomously. | All changes must go through the PR review process and require human approval before merging. |
| **No Undocumented Strategy Changes** | Any modification to trading logic, signal generation, or AI models must be thoroughly documented. | Update the relevant strategy documentation and add inline comments explaining the rationale for the change. |
| **No Silent Edits to Risk Management** | Changes to the Risk Gate, position sizing formulas, or drawdown limits are considered high-risk. | Flag any PR containing risk management changes with a specific label (e.g., `high-risk`) and explicitly request a thorough review from the lead quantitative analyst. |
| **High-Risk Module Visibility** | Modules related to order execution, API key handling, and core risk calculations require extra scrutiny. | Ensure comprehensive unit and integration tests are included for any changes to these modules. |

## 4. GitHub Project Board Interaction

Manus interacts with the GitHub Project Board to maintain visibility of work progress.

*   **Backlog:** Issues waiting to be prioritized.
*   **Needs Spec:** Issues requiring further definition before work can begin. Manus can assist in drafting specifications here.
*   **Ready for Manus:** Issues that are fully specified and ready for Manus to execute.
*   **In Progress:** Issues currently being worked on by Manus.
*   **In Review:** Issues with an open PR awaiting human review.
*   **Done:** Issues that have been merged and completed.

Manus is authorized to move issues between these columns as work progresses, ensuring the board accurately reflects the current state of the project.

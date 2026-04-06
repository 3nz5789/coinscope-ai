# CoinScopeAI GitHub Project Board Setup Guide

**Author:** Manus AI
**Date:** April 6, 2026

This document provides step-by-step instructions for creating and configuring the CoinScopeAI GitHub Project Board. The project board uses GitHub Projects (v2) with a Board view to manage the development workflow.

## 1. Create the Project

1. Navigate to https://github.com/3nz5789/coinscope-ai
2. Click the **Projects** tab
3. Click **Link a project** > **New project**
4. Select **Board** as the template
5. Name it: **CoinScopeAI Development Board**
6. Click **Create project**

## 2. Configure Board Columns

Rename and create columns in this exact order (left to right):

| Column | Purpose | Entry Criteria |
| :--- | :--- | :--- |
| **Backlog** | Issues waiting to be prioritized. | Any new issue starts here. |
| **Needs Spec** | Issues requiring further definition before work can begin. | Issue lacks acceptance criteria or technical details. |
| **Ready for Manus** | Issues fully specified and ready for Manus AI to execute. | Issue has clear acceptance criteria, linked docs, and the `ready-for-manus` label. |
| **In Progress** | Issues currently being worked on. | A branch has been created and work has started. |
| **In Review** | Issues with an open PR awaiting human review. | PR is open and CI checks are passing. |
| **Done** | Issues that have been merged and completed. | PR merged, issue closed. |

To create columns: click the **+** button on the right side of the board, then rename each column accordingly.

## 3. Column Transition Rules

The following rules govern when issues move between columns:

| Transition | Trigger | Who Moves It |
| :--- | :--- | :--- |
| Backlog -> Needs Spec | Issue needs more detail before it can be worked on. | Human operator |
| Backlog -> Ready for Manus | Issue is fully specified and ready for AI execution. | Human operator |
| Needs Spec -> Ready for Manus | Specification is complete and approved. | Human operator |
| Ready for Manus -> In Progress | Manus picks up the issue and creates a branch. | Manus AI |
| In Progress -> In Review | Manus opens a PR for the issue. | Manus AI |
| In Review -> Done | PR is approved and merged. | Human operator |
| In Review -> In Progress | PR requires changes based on review feedback. | Manus AI |

## 4. Labels (Already Created)

The following labels have been created on the repository and should be used to categorize issues:

**Workflow labels:**

| Label | Color | Purpose |
| :--- | :--- | :--- |
| `backlog` | Yellow | In the backlog, not yet prioritized |
| `needs-spec` | Yellow | Needs further specification |
| `ready-for-manus` | Green | Fully specified, ready for Manus to execute |
| `in-progress` | Blue | Currently being worked on |
| `in-review` | Purple | PR open, awaiting review |

**Safety labels:**

| Label | Color | Purpose |
| :--- | :--- | :--- |
| `high-risk` | Red | Changes to risk management, position sizing, or order execution |
| `strategy` | Orange-Red | Trading strategy or AI model changes |

**Component labels:**

| Label | Color | Purpose |
| :--- | :--- | :--- |
| `trading-engine` | Light Green | Related to the core trading engine |
| `dashboard` | Light Blue | Related to the web dashboard |
| `ai-ml` | Light Purple | Related to AI/ML models and pipelines |
| `infrastructure` | Light Orange | Related to Docker, K8s, CI/CD, Terraform |
| `telegram-bot` | Light Blue | Related to the Telegram bot service |

## 5. What "Ready for Manus" Means

An issue is considered **ready for Manus** when all of the following are true:

1. The issue has a clear, unambiguous title and description.
2. Acceptance criteria are explicitly listed (what "done" looks like).
3. The affected component(s) are identified via labels.
4. If the issue touches risk management, position sizing, or order execution, it has the `high-risk` label and has been explicitly approved for Manus to work on.
5. Any required design decisions or architectural choices have been documented in the issue or linked documents.
6. The `ready-for-manus` label has been applied by a human operator.

## 6. What Issues Require Human Approval

The following types of changes **always require human approval** before Manus can proceed:

- Any change to live/production trading parameters
- Modifications to the Risk Gate thresholds or logic
- Changes to position sizing formulas
- New or modified exchange API integrations
- Infrastructure changes (Kubernetes, Terraform, production Docker configs)
- Any change that could affect real capital

## Description

<!-- Provide a clear summary of the change and which issue it addresses. -->

Fixes # (issue)

## Type of change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Infrastructure / DevOps change
- [ ] Strategy / Risk logic change (requires extra review)

## Components modified

- [ ] `services/trading-engine/`
- [ ] `apps/dashboard/`
- [ ] `services/telegram-bot/`
- [ ] `ai/`
- [ ] `strategies/`
- [ ] `infra/`
- [ ] `docs/`
- [ ] `configs/`
- [ ] Other: ___

## How has this been tested?

<!-- Describe the tests you ran. Provide instructions to reproduce. -->

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing performed
- [ ] Backtesting results attached (if strategy change)

## Trading safety checklist

- [ ] No hardcoded API keys or secrets
- [ ] All new configs default to TESTNET mode
- [ ] Risk management logic unchanged OR flagged for extra review
- [ ] Position sizing logic unchanged OR flagged for extra review
- [ ] Order execution logic unchanged OR flagged for extra review

## General checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have added/updated relevant documentation
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally
- [ ] I have updated the GitHub Project Board status

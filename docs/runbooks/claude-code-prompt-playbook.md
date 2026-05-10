# CoinScopeAI · Claude Code · prompt playbook
# Scoopy voice: phased, explicit assumptions, risk-first, evidence-led.

## Launch

cd ~/coinscopeai/scripts
claude

## Useful first prompts

# Phase 1 — survey the codebase
> Read all .py files in this directory. For each, give a one-line summary and flag anything that touches the risk-gate, position-size, or regime detector. State your assumptions.

# Phase 2 — backtest (dry run, testnet assumed)
> Run python backtest_runner.py --dry-run and show the output. Report drawdown, daily-loss, and max-leverage observed vs limits (10% / 5% / 10x). Flag any breach.

# Phase 3 — scanner integrity check
> Check live_scan.py for issues with the score_sentiment function and its call site in _scan_symbol. Don't modify — report findings, confidence, and assumptions first.

# Phase 4 — live scan when MacroGate reopens
> Run python live_scan.py and show full output. Report current regime per symbol (Trending / Mean-Reverting / Volatile / Quiet) and which signals would be gated.

## Multi-file edits (Scoopy format)

# State the change, the scope, and the test, in that order.
> The sentiment_bonus threshold is currently >=4. Change to >=4 AND coverage==5. Scope: sentiment scorer + call sites + docstring. Test: run pytest tests/test_sentiment.py and report pass/fail.

## Guardrails (never skip)

# - Binance Testnet only. Do not introduce live-order paths.
# - 30-day validation phase. No core engine changes without approval.
# - Every edit must state assumptions, the phase, and the rollback.
# - Never describe a change as "production-ready".

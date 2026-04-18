# Glossary

**Status:** current
**Audience:** anyone reading code, docs, or PRs and hitting unfamiliar terms
**Related:** [`new-developer-guide.md`](new-developer-guide.md), [`first-week-checklist.md`](first-week-checklist.md), [`../risk/risk-framework.md`](../risk/risk-framework.md), [`../ml/regime-detection.md`](../ml/regime-detection.md)

Terms used across the CoinScopeAI engine, docs, and PRs. When a term has a specific CoinScopeAI meaning that differs from the broader crypto or ML meaning, that's called out.

## Trading and market terms

**Perpetual future (perp).** A futures contract with no expiry. The engine trades USDT-margined perpetuals on Binance Futures exclusively.

**USDT-M.** USDT-margined. Contracts settled in USDT. This is the only family the engine currently trades. The USDC-M and coin-margined families are out of scope.

**Testnet.** The Binance sandbox at `testnet.binancefuture.com`. Keys, positions, and P&L are isolated from mainnet. All execution during validation runs here.

**Mainnet.** Real Binance. The engine has never traded there. A mainnet cutover is planned but gated on validation outcomes; it is not in scope for this repo today.

**Funding rate.** The periodic payment between long and short holders of a perp. The scanner reads it as a factor; extreme funding often signals crowded positioning.

**Open Interest (OI).** The total notional of open perp positions. OI trend is one of the signal factors.

**Liquidation cascade.** A chain of forced closes as price moves through clustered stops. The engine tracks recent liquidation volume to avoid taking trades into active cascades.

**Slippage.** The difference between expected and realized fill price. The adapter estimates slippage pre-trade; the risk gate rejects trades where expected slippage would eat too much of the edge.

## Engine-specific terms

**Scanner.** The loop that iterates the symbol universe and asks the scorer to evaluate each one. Two directories exist today — `scanner/` and `scanners/` — a post-validation consolidation is queued.

**Scorer.** The multi-factor model that produces a 0–12 confluence score per symbol. Factors include RSI, EMA alignment, ATR, volume, CVD, entry timing, and regime alignment.

**Confluence score.** The 0–12 integer the scorer emits. Higher means more factors agree. The default scoring floor is tuned per regime.

**Signal.** A symbol that cleared the scorer's floor. A signal is a *candidate*, not an order. It still has to pass the risk gate.

**Regime.** The current market state. CoinScopeAI has two regime systems running side by side:
- The **HMM detector** classifies the tape as `bull`, `bear`, or `chop` (3 states, hidden Markov model).
- The **v3 classifier** labels the tape as `Trending`, `Mean-Reverting`, `Volatile`, or `Quiet` (4 labels, supervised).
Both are consumed; different components read different detectors. See [`../ml/regime-detection.md`](../ml/regime-detection.md) for which is which.

**Risk gate.** The pre-trade checklist that turns a signal into a sized order — or rejects it. Checks include regime alignment, portfolio heat, correlation cap, daily-loss budget, and circuit-breaker state. Code: `coinscope_trading_engine/risk_gate.py`.

**Kelly-fractional.** The position-sizing rule. The engine computes the full Kelly fraction, then takes 25% of it, caps it at 2% of equity, and multiplies by a regime multiplier (bull 1.0, chop 0.5, bear 0.3). See [`../risk/position-sizing.md`](../risk/position-sizing.md).

**Position heat.** The sum of per-position risk contributions as a fraction of equity. Capped at 80% (`POSITION_HEAT_CAP_PCT`). A new trade that would push heat past the cap is rejected.

**Circuit breaker.** Automatic halt that trips on daily loss limit, max drawdown, or a consecutive-loss streak. Resets at a defined window. See [`../risk/failsafes-and-kill-switches.md`](../risk/failsafes-and-kill-switches.md).

**Kill switch.** A manual halt. Flipping it disables new entries and cancels working orders, without unwinding existing positions.

**Journal.** The append-only log of every decision, fill, and P&L update. Persisted in SQLite by default, Postgres optional. Read via `/journal`.

**WFV.** Walk-forward validation. The backtesting methodology: train on a window, test on the next, roll forward. The canonical WFV script lives in `scripts/`.

**Alpha decay.** The observed tendency of a strategy's edge to shrink after deployment. The engine has explicit decay-monitoring parameters in `.env` — when decay crosses a threshold, the strategy is flagged for re-evaluation.

**Scale-up.** The post-validation plan to increase notional after the strategy demonstrates edge on testnet. Controlled by `SCALE_UP_*` env vars, inert during validation.

## ML terms

**HMM.** Hidden Markov Model. Classical probabilistic state-space model. The bull/bear/chop regime detector is an HMM from `hmmlearn`.

**Classifier v3.** The supervised four-class regime model (Trending / Mean-Reverting / Volatile / Quiet). Built on scikit-learn + xgboost. "v3" is a version tag, not a separate library.

**Feature contract.** The ordered tuple of features the engine passes to a saved model at inference time. Changing it is engine-adjacent and needs review, because the saved `.pkl` expects that exact shape.

**Artifact.** A serialized trained model — `.pkl` or `.joblib` — checked into or loaded from the configured artifact path. The engine does not train at runtime; it loads artifacts produced by `ml/`.

## Infrastructure and tooling

**FastAPI.** The web framework for the engine's HTTP API. See [`../decisions/adr-0001-fastapi-and-uvicorn.md`](../decisions/adr-0001-fastapi-and-uvicorn.md).

**Uvicorn.** The ASGI server running the FastAPI app.

**Celery.** The background task framework for periodic scans, re-scoring, and journal writes. Broker: Redis.

**Redis.** The Celery broker and a lightweight cache. Local via Docker Compose, remote in deployment.

**Postgres / SQLite.** The journal storage. SQLite is the default for local dev. Postgres is the production target.

**Prometheus.** The metrics backend. The engine exposes a `/metrics` endpoint scraped locally.

**Stripe.** The billing provider. Webhooks land at `billing_server.py`; entitlements are read back by the engine before serving premium endpoints.

## Project terms

**Validation freeze.** The period 2026-04-10 to 2026-04-30 during which internal engine structure, risk thresholds, and Kelly parameters are locked. See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md#validation-freeze-2026-04-10-to-2026-04-30).

**Tier-1 docs.** The ~30 docs shipped in the 2026-04-18 restructure. Listed in [`../README.md`](../README.md).

**Tier-2 docs.** Docs queued for after validation. Listed in [`../product/implementation-backlog.md`](../product/implementation-backlog.md).

**The dashboard / the website.** https://coinscope.ai/. A React app in a separate repository. Not in this tree.

**The engine.** The Python package in `coinscope_trading_engine/`. When a doc says "the engine" without more qualification, this is what it means.

**Scoopy.** The operating agent identity used in cross-system tooling (MemPalace, skills). Not a runtime component of the engine.

**MemPalace.** The operator's persistent memory system used by Scoopy tooling. Out of scope for the engine repo, but referenced in some older archived docs.

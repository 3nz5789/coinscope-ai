# ADR-0005: Validation-Safe vs Experimental Directory Boundaries

**Status:** accepted
**Date:** 2026-05-12
**Authors:** Mohammed Abuanza, Scoopy
**Related:** COI-93, `tests/test_directory_boundaries.py`, PCC v2 §8, ADR-0003

## Context

The engine codebase contains two fundamentally different categories of code that must not bleed into each other during the P0 validation cohort:

**Validation-safe code** runs on the live hot path: it gates every trade, enforces risk thresholds, routes Telegram alerts, and records journal entries. A bug here has real financial consequences (even on testnet, it invalidates the validation cohort data). This code must be importable without PyTorch, hmmlearn, ccxt, sklearn, or any heavy ML dependency.

**Experimental code** is research and offline tooling: the LSTM price predictor, the HMM regime detector, the backtester, and the walk-forward validator. These exist to produce insights that inform strategy — they are not on the trading hot path. They may use any dependency and do not need to be production-hardened.

Today there is no enforced boundary between these two categories. Any developer can import `price_predictor` from `confluence_scorer`, or call `TelegramNotifier` from a backtesting script, without any test failing. This is dangerous:

1. A stale `import torch` at the top of a hot-path file will crash the engine on a VPS without PyTorch installed.
2. A backtesting script that calls `place_order` could accidentally execute a live order if wired wrong.
3. Experimental thresholds (leverage=20, zero slippage) silently produce misleading backtest results if they contradict PCC v2 §8.

## Decision

Enforce two-way boundary isolation between validation-safe and experimental code, verified by `tests/test_directory_boundaries.py` on every CI run.

**Validation-safe directories** (may be freely imported by the live trading path):

| Directory | Contents |
|---|---|
| `risk/` | CircuitBreaker, PositionSizer, ExposureTracker, CorrelationAnalyzer |
| `core/` | FixedScorer, RiskGate, MultiTimeframeFilter |
| `scanner/` | VolumeScanner, PatternScanner, FundingRateScanner, OrderBookScanner, LiquidationScanner |
| `signals/` | ConfluenceScorer, EntryExitCalculator, IndicatorEngine, SignalGenerator |
| `data/` | BinanceRESTClient, CacheManager, DataNormalizer |
| `alerts/` | TelegramNotifier, ScaleUpManager |
| `storage/` | TradeJournal, DecisionJournal, HistoricalKlinesStore |
| `monitoring/` | EngineMetrics, MetricsExporter |
| `billing/` | StripeGateway |
| `utils/` | helpers, logger |
| `live/` | MasterOrchestrator, WS clients, TestnetExecutor |
| `config.py` | Settings singleton |
| `api.py` | FastAPI app |

**Experimental files** (must not be imported unconditionally by the live trading path):

| File | Reason |
|---|---|
| `models/price_predictor.py` | PyTorch LSTM — heavy dep, not on hot path |
| `signals/backtester.py` | Async Binance fetch, offline research |
| `validation/walk_forward_validation.py` | ccxt dep, offline research |
| `intelligence/hmm_regime_detector.py` | hmmlearn dep, HMM fallback only |
| `intelligence/finbert_sentiment_filter.py` | Mock/stub, not live-critical |
| `intelligence/whale_signal_filter.py` | External API, not live-critical |
| `intelligence/funding_rate_filter.py` | Supplementary filter |

The following rules are enforced by `test_directory_boundaries.py`:

1. **No top-level experimental imports in hot-path files.** `risk/`, `core/`, `signals/` scorers must not unconditionally import PyTorch, hmmlearn, ccxt, or any experimental module. Lazy imports inside `try/except` or function bodies are acceptable.

2. **No order placement from experimental modules.** `backtester.py`, `validation/`, and `models/price_predictor.py` must not call `place_order`, reference `fapi/v1/order`, or import `TelegramNotifier`. They are read-only tools.

3. **No Notion writes from validation/.** The `validation/` directory is observe-only — no writes to Signal Log, Trade Journal, or Scan History DBs.

4. **Canonical thresholds not overridden in experimental code.** `BacktestConfig` must include `commission_pct` and `slippage_pct`. Hard-coded leverage > 10 is prohibited.

5. **api.py imports experimental code only inside try/except.** The v3 ML classifier, backtester, and price predictor may be loaded optionally — their absence must not prevent engine startup.

6. **This ADR must exist.** `test_boundary_adr_exists` fails CI if ADR-0005 is deleted.

## Alternatives considered

- **Runtime import hooks** — intercept `import` calls and raise if a forbidden module is loaded. Rejected: too fragile, breaks testing and IDE tooling, hard to reason about.
- **Separate Python packages** — move experimental code to a separate installable package. Rejected: significant restructuring cost during P0; adds packaging overhead. Revisit at P2 when the boundary is stable.
- **No enforcement, documentation only** — a README note. Rejected: documentation rots; tests don't. The boundary must be machine-checked.
- **Status quo / do nothing** — rejected: the first time a developer accidentally `import`s `price_predictor` in `confluence_scorer.py`, the VPS will crash at startup because PyTorch is not installed there.

## Consequences

**Positive:**

- CI will fail if a hot-path file accidentally imports an experimental module at the top level
- VPS startup cannot be broken by missing ML dependencies (PyTorch, hmmlearn) that are optional
- Backtesting scripts cannot accidentally place live orders
- Canonical thresholds (leverage=10, commission required) are enforced even in offline tooling
- New developers have a machine-checked map of what is and isn't safe to call from the hot path

**Negative / costs:**

- Some legitimate imports (e.g. `RegimeDetector` used as a fallback) must be wrapped in `try/except` where they aren't already — small refactor cost
- Tests add ~30 seconds to the CI suite (AST parsing, not module loading — fast)
- The boundary is coarse-grained at the file/directory level; a single file cannot be partially safe

**Neutral:**

- `intelligence/` is currently all-experimental. If a new module is added there that is safe for the hot path, it must be explicitly added to `VALIDATION_SAFE_DIRS` in the test file and this ADR updated.
- The `models/` directory contains only experimental files today. Any new model file must be added to `EXPERIMENTAL_FILES` in the test file before merging.

## Revisit when

- When `intelligence/` is split into a live-safe regime module and an experimental research module (likely P1)
- When the LSTM price predictor or HMM classifier is promoted to the hot path (requires explicit ADR revision + CI update)
- When the codebase migrates to separate Python packages (P2+)

## Notes

The test suite is in `tests/test_directory_boundaries.py`. It uses AST parsing (not runtime import) so it never loads experimental modules during CI — it only reads source text. This means the boundary checks work even when PyTorch or hmmlearn are not installed on the CI runner.

Linear: COI-93 (Done)

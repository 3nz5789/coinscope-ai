"""
CoinScopeAI — Offline validation harness.

This package is **experimental / read-only** per ADR-0005 boundaries:

- It must not import from `risk/` or `core/` (boundary-test enforced)
- It must not write to Notion, Telegram, or place orders
- It is imported by no hot-path module; it is a one-off research tool

Modules:

- `_common`: OHLCV fetch via ccxt, scorer wrapper, metrics, trade simulation
- `walk_forward_validation`: sequential walk-forward (3 folds × symbol)
- `cpcv_validation`: combinatorial purged cross-validation (C(N,K) paths × symbol)
"""

# Cleanup — 2026-04-20

Snapshot of files + directories archived when the repo was restructured
for production-grade layout. **Nothing here is load-bearing.** The
running engine + dashboard verified green after these moves.

## What was moved and why

### `engine-duplicates/` (23 Python files)

Files that existed **both** at `coinscope_trading_engine/<name>.py`
**and** inside a proper subpackage (`live/`, `core/`, `alerts/`,
`storage/`, `intelligence/`, `monitoring/`). These were pre-restructure
leftovers from the flat layout. The subpackage copies are active and
imported by `api.py`. Zero external references to the top-level
versions were found at move time (grep across engine + dashboard +
tests + scripts).

| Archived | Canonical location |
|---|---|
| `master_orchestrator.py` | `live/master_orchestrator.py` |
| `pair_monitor.py` | `live/pair_monitor.py` |
| `binance_futures_testnet_client.py` | `live/` |
| `binance_rest_testnet_client.py` | `live/` |
| `binance_testnet_executor.py` | `live/` |
| `binance_websocket_client.py` | `live/` |
| `retrain_scheduler.py` | `alerts/retrain_scheduler.py` |
| `alpha_decay_monitor.py` | `alerts/alpha_decay_monitor.py` |
| `scale_up_manager.py` | `alerts/scale_up_manager.py` |
| `telegram_alerts.py` | `alerts/telegram_alerts.py` |
| `trade_journal.py` | `storage/trade_journal.py` |
| `trade_logger.py` | `storage/trade_logger.py` |
| `notion_simple_integration.py` | `storage/` |
| `notion_sync_config.py` | `storage/` |
| `portfolio_sync.py` | `storage/` |
| `funding_rate_filter.py` | `intelligence/` |
| `hmm_regime_detector.py` | `intelligence/` |
| `kelly_position_sizer.py` | `intelligence/` |
| `whale_signal_filter.py` | `intelligence/` |
| `multi_timeframe_filter.py` | `core/multi_timeframe_filter.py` |
| `risk_gate.py` | `core/risk_gate.py` |
| `scoring_fixed.py` | `core/scoring_fixed.py` |
| `realtime_dashboard.py` | `monitoring/realtime_dashboard.py` |
| `metrics_exporter.py` | `monitoring/metrics_exporter.py` |

### `stray-copies/` (2 files)

OS/editor-generated duplicates with `" (N)"` suffix.

- `trade_journal (2).py`
- `whale_signal_filter (1).py`

### `root-orphan-dirs/` (8 directories)

Top-level directories with no references from active code. Mostly dev
scaffolding from earlier experiments.

- `manus_setup/`, `manus_upload/`, `coinscopeai-skills/` — Manus dev tooling scaffolding
- `market_scanner_skill/`, `skills/` — old skill-format experiments
- `research/` — PDFs + notes
- `tasks/` — old kanban/TODO markdown
- `crypto_futures_dev/` — single-file placeholder

### `apps/`

Vite dashboard skeleton — had only `src/lib/` stubs, no `package.json`.
The real dashboard lives at `coinscopeai-dashboard/` (cloned from the
external repo).

### Empty dirs removed

- `risk_management/` — only `__pycache__/`
- `coinscope_trading_engine/engine/` — empty stub from the PR-11
  restructure on `main` (this branch diverged before it)
- `billing_subscriptions.db{,-journal}` — empty SQLite from initial scaffolding

### `.env` backups

- `.env.bak.20260420-040111` — superseded by current `.env`

## Recovery

If anything breaks because a file was archived here, restore with:

```bash
mv archive/cleanup-2026-04-20/engine-duplicates/<name>.py coinscope_trading_engine/
```

Audit commands used to prove no external references:
```bash
# Top-level Python files that are NOT imported by api.py
grep -r "from <mod>\|import <mod>" --include='*.py' \
  --exclude-dir=__pycache__ --exclude-dir=live --exclude-dir=core \
  --exclude-dir=alerts --exclude-dir=storage --exclude-dir=intelligence \
  --exclude-dir=monitoring coinscope_trading_engine/
```

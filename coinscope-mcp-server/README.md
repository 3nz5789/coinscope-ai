# coinscope-mcp-server

MCP server wrapping the CoinScopeAI Engine API. Exposes read-only engine state and one safe-trigger tool to any MCP-capable client (Claude Code, Cowork, etc.) without requiring callers to deal with HTTP, URL paths, or response shapes.

## Scope (v0.1)

**Included — 14 read-only tools + 1 safe trigger:**

| Tool | Endpoint | Purpose |
| --- | --- | --- |
| `coinscope_health` | `GET /health` | Liveness probe + version |
| `coinscope_config` | `GET /config` | Non-secret config + canonical risk thresholds |
| `coinscope_signals` | `GET /signals` | Latest cached signals + scan loop state |
| `coinscope_scan_status` | `GET /scan/status` | Background scan loop health |
| `coinscope_scan_trigger` | `POST /scan` | Trigger an immediate scan cycle |
| `coinscope_regime` | `GET /regime` | Market regime per symbol (v3 ML or HMM fallback) |
| `coinscope_sentiment` | `GET /sentiment` | Sentiment score for a symbol |
| `coinscope_anomaly` | `GET /anomaly` | Anomaly detection output |
| `coinscope_position_size` | `GET /position-size` | Kelly-fractional position sizing |
| `coinscope_exposure` | `GET /exposure` | Portfolio exposure metrics |
| `coinscope_positions` | `GET /positions` | Open positions with unrealised PnL |
| `coinscope_circuit_breaker` | `GET /circuit-breaker` | Circuit breaker state (read only) |
| `coinscope_journal` | `GET /journal` | Trade journal entries |
| `coinscope_performance` | `GET /performance` | Aggregate performance stats |
| `coinscope_decisions` | `GET /decisions` | Recent decisions log |

**Explicitly excluded** from v0.1: order placement (`POST /orders*`), order cancellation (`DELETE /orders*`), circuit-breaker reset/trip, autotrade enable/disable/config flips, account sync, decision unpause, historical backfill. Those require a separate write-enabled MCP with explicit per-call confirmation gates. v0.1 is "safe-by-default" — no tool can place a trade, move money, or change a canonical risk threshold.

## Configuration

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `COINSCOPE_ENGINE_URL` | `http://localhost:8001` | Base URL of the running engine API |

No auth is required — the engine API is currently unauthenticated and assumed to be accessed over a private network.

## Install

```bash
cd ~/Code/CoinScopeAI/coinscope-mcp-server
npm install
npm run build
```

## Run

### As a subprocess of Claude Code / Cowork (stdio)

Register in your MCP client config. For Claude Code, add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "coinscope": {
      "command": "node",
      "args": ["/Users/mac/Code/CoinScopeAI/coinscope-mcp-server/dist/index.js"],
      "env": {
        "COINSCOPE_ENGINE_URL": "http://localhost:8001"
      }
    }
  }
}
```

For Cowork, the plugin system is the right path (see `memory/feedback_cowork_mcp_servers_stripped.md` — direct `mcpServers` edits in Claude Desktop config get wiped).

### Smoke test with MCP Inspector

```bash
npm run inspect
```

Opens an inspector UI in the browser where you can list tools, call them with sample params, and inspect responses.

## Safety posture

- **Read-only by default.** Every tool except `coinscope_scan_trigger` is annotated `readOnlyHint: true`.
- **No financial actions.** No tool can place an order, modify a position, or flip the autotrade switch.
- **Per the master prompt (`CLAUDE.md`):** validation phase is active through ~2026-05-31. Never "production-ready".
- **Canonical thresholds** (max_leverage=10x, max_open_positions=5, max_drawdown=10%, max_daily_loss=5%) come from the engine's own `/config` — call `coinscope_config` to see what the engine reports vs. the master prompt.

## Drift notes (vs. CLAUDE.md)

CLAUDE.md documents `POST /position-size` and `GET /regime/{symbol}`. The actual `api.py` has `GET /position-size` (with query params) and `GET /regime` (with `symbol` query param). This MCP follows `api.py`. Reconciliation of CLAUDE.md tracked in Linear COI-? (TBD).

## Layout

```
coinscope-mcp-server/
├── package.json
├── tsconfig.json
├── README.md
├── .gitignore
└── src/
    ├── index.ts          # entry point + tool registration
    ├── constants.ts      # ENGINE_URL, timeouts, response format enum
    ├── engineClient.ts   # axios wrapper + error helpers
    └── tools/
        ├── system.ts        # health, config
        ├── signals.ts       # signals, scan_status, scan_trigger
        ├── intelligence.ts  # regime, sentiment, anomaly
        ├── risk.ts          # position_size, exposure, positions, circuit_breaker
        └── journal.ts       # journal, performance, decisions
```

/**
 * System tools: coinscope_health, coinscope_config.
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { engineRequest, handleEngineError } from "../engineClient.js";
import { ResponseFormat } from "../constants.js";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const FormatOnlyShape = {
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe(
      "Output format: 'markdown' for human-readable or 'json' for machine-readable",
    ),
};

// ---------------------------------------------------------------------------
// Types (mirror engine api.py response shapes)
// ---------------------------------------------------------------------------

interface HealthResponse {
  status: string;
  version: string;
  testnet: boolean;
  timestamp: number;
}

interface ConfigResponse {
  testnet_mode: boolean;
  environment: string;
  scan_pairs: string[];
  scan_interval_s: number;
  min_confluence_score: number;
  risk_per_trade_pct: number;
  max_leverage: number;
  max_open_positions: number;
  max_position_size_pct: number;
  max_total_exposure_pct: number;
  max_daily_loss_pct: number;
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatHealthMarkdown(h: HealthResponse): string {
  const ts = new Date(h.timestamp * 1000).toISOString();
  return [
    "# Engine Health",
    "",
    `- **Status**: \`${h.status}\``,
    `- **Version**: ${h.version}`,
    `- **Testnet**: ${h.testnet ? "yes" : "no"}`,
    `- **Timestamp**: ${ts}`,
  ].join("\n");
}

function formatConfigMarkdown(c: ConfigResponse): string {
  return [
    "# Engine Config (non-secret)",
    "",
    `- **Environment**: ${c.environment}${c.testnet_mode ? " (testnet)" : ""}`,
    `- **Scan pairs (${c.scan_pairs.length})**: ${c.scan_pairs.join(", ")}`,
    `- **Scan interval**: ${c.scan_interval_s}s`,
    `- **Min confluence score**: ${c.min_confluence_score}`,
    "",
    "## Risk thresholds (live engine values)",
    "",
    `- **Max leverage**: ${c.max_leverage}x`,
    `- **Max open positions**: ${c.max_open_positions}`,
    `- **Max position size**: ${c.max_position_size_pct}%`,
    `- **Max total exposure**: ${c.max_total_exposure_pct}%`,
    `- **Max daily loss**: ${c.max_daily_loss_pct}%`,
    `- **Risk per trade**: ${c.risk_per_trade_pct}%`,
    "",
    "> Canonical values per PCC v2 §8 (2026-05-01): max_leverage=10x, " +
      "max_open_positions=5, max_daily_loss=5%. If the engine reports something " +
      "different, the engine is running stale config (typically COI-68 pending).",
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export function registerSystemTools(server: McpServer): void {
  server.registerTool(
    "coinscope_health",
    {
      title: "Engine Health",
      description: `Liveness probe for the CoinScopeAI engine. Returns engine status, version, testnet flag, and a Unix timestamp.

Args:
  - response_format ('markdown' | 'json'): Output format (default: 'markdown')

Returns (JSON shape):
  {
    "status": "ok",          // string — 'ok' when engine is responsive
    "version": "2.0.0",      // string — engine semver
    "testnet": true,         // boolean — true if engine is in testnet/demo mode
    "timestamp": 1715000000  // number — Unix epoch seconds
  }

Examples:
  - Use when: verifying the engine is reachable before calling other tools
  - Use when: monitoring engine uptime / version drift

If this tool fails with a connection error, no other coinscope_* tool will succeed — start the engine first (cd coinscope_trading_engine && uvicorn api:app --port 8001).`,
      inputSchema: FormatOnlyShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const data = await engineRequest<HealthResponse>("/health");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatHealthMarkdown(data)
            : JSON.stringify(data, null, 2);
        return {
          content: [{ type: "text", text }],
          structuredContent: data as unknown as Record<string, unknown>,
        };
      } catch (err) {
        return {
          isError: true,
          content: [{ type: "text", text: handleEngineError(err) }],
        };
      }
    },
  );

  server.registerTool(
    "coinscope_config",
    {
      title: "Engine Config",
      description: `Return non-secret engine configuration values, including canonical risk thresholds, scan pairs, and scan interval. Use this to verify the live engine is running with the thresholds you expect.

Args:
  - response_format ('markdown' | 'json'): Output format (default: 'markdown')

Returns (JSON shape):
  {
    "testnet_mode": true,
    "environment": "validation",
    "scan_pairs": ["BTCUSDT", "ETHUSDT", ...],
    "scan_interval_s": 60,
    "min_confluence_score": 7.0,
    "risk_per_trade_pct": 2.0,
    "max_leverage": 10,
    "max_open_positions": 5,
    "max_position_size_pct": 20.0,
    "max_total_exposure_pct": 80.0,
    "max_daily_loss_pct": 5.0
  }

Canonical values per the master prompt (PCC v2 §8, 2026-05-01):
  - max_leverage: 10x
  - max_open_positions: 5
  - max_daily_loss_pct: 5%
  - max_total_exposure_pct: 80% (position heat cap)
  - risk_per_trade_pct: 2% (Kelly hard cap)

If this tool returns values different from those, the engine is running stale config (typically COI-68 still pending — VPS .env patch + docker restart).`,
      inputSchema: FormatOnlyShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const data = await engineRequest<ConfigResponse>("/config");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatConfigMarkdown(data)
            : JSON.stringify(data, null, 2);
        return {
          content: [{ type: "text", text }],
          structuredContent: data as unknown as Record<string, unknown>,
        };
      } catch (err) {
        return {
          isError: true,
          content: [{ type: "text", text: handleEngineError(err) }],
        };
      }
    },
  );
}

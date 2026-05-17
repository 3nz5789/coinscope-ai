#!/usr/bin/env node
/**
 * coinscope-mcp-server — MCP server wrapping the CoinScopeAI Engine API.
 *
 * Scope (v0.1):
 *   - 14 read-only tools covering the engine's documented and undocumented
 *     read endpoints (signals, regime, journal, performance, exposure, ...)
 *   - 1 safe-trigger tool: coinscope_scan_trigger (POST /scan)
 *   - Explicitly NOT included: order placement, circuit-breaker reset/trip,
 *     autotrade enable/disable, account sync. Those require a separate
 *     write-enabled MCP with explicit per-call user confirmation gates.
 *
 * Validation phase active through ~May 31, 2026. Capital preservation first.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { ENGINE_URL, SERVER_NAME, SERVER_VERSION } from "./constants.js";
import { registerSystemTools } from "./tools/system.js";
import { registerSignalsTools } from "./tools/signals.js";
import { registerIntelligenceTools } from "./tools/intelligence.js";
import { registerRiskTools } from "./tools/risk.js";
import { registerJournalTools } from "./tools/journal.js";

const server = new McpServer({
  name: SERVER_NAME,
  version: SERVER_VERSION,
});

// Register all tool groups
registerSystemTools(server);
registerSignalsTools(server);
registerIntelligenceTools(server);
registerRiskTools(server);
registerJournalTools(server);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // stdio servers must NOT log to stdout — use stderr.
  console.error(`[${SERVER_NAME}] running via stdio`);
  console.error(`[${SERVER_NAME}] engine URL: ${ENGINE_URL}`);
}

main().catch((err: unknown) => {
  console.error(`[${SERVER_NAME}] fatal:`, err);
  process.exit(1);
});

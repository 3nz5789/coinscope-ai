/**
 * Risk tools: coinscope_position_size, coinscope_exposure, coinscope_positions,
 * coinscope_circuit_breaker.
 *
 * All read-only. The circuit_breaker tool returns STATE only — to trip or
 * reset the breaker, callers must use the engine API directly with explicit
 * confirmation (deliberately not exposed here).
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
    .describe("Output format"),
};

const PositionSizeShape = {
  symbol: z
    .string()
    .regex(/^[A-Z0-9]+USDT$/i, "Symbol must be a USDT-quoted perpetual (e.g. BTCUSDT)")
    .default("BTCUSDT")
    .describe("USDT-perpetual symbol"),
  entry: z.number().positive().describe("Planned entry price (USDT)"),
  stop_loss: z
    .number()
    .positive()
    .describe(
      "Stop-loss price (USDT). Direction inferred from entry vs stop: LONG if entry > stop, SHORT otherwise.",
    ),
  account_balance: z
    .number()
    .positive()
    .describe("Account balance in USDT used as the sizing base"),
  win_rate: z
    .number()
    .min(0)
    .max(1)
    .optional()
    .describe(
      "Historical win rate [0,1]. If provided WITH avg_rr, Kelly fractional sizing is used.",
    ),
  avg_rr: z
    .number()
    .positive()
    .optional()
    .describe(
      "Average reward/risk ratio. If provided WITH win_rate, Kelly fractional sizing is used.",
    ),
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format"),
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PositionSizeResponse {
  symbol: string;
  direction: string;
  qty: number;
  notional: number;
  risk_usdt: number;
  margin_usdt: number;
  risk_pct: number;
  leverage: number;
  method: string;
  valid: boolean;
  reason: string | null;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatPositionSizeMarkdown(p: PositionSizeResponse): string {
  return [
    `# Position Sizing — ${p.symbol} ${p.direction}`,
    "",
    `- **Valid**: ${p.valid ? "yes" : `no — ${p.reason}`}`,
    `- **Method**: ${p.method}`,
    `- **Qty**: ${p.qty}`,
    `- **Notional**: $${p.notional.toFixed(2)}`,
    `- **Risk**: $${p.risk_usdt.toFixed(2)} (${p.risk_pct.toFixed(2)}% of equity)`,
    `- **Margin**: $${p.margin_usdt.toFixed(2)}`,
    `- **Leverage**: ${p.leverage}x`,
    `- **At**: ${new Date(p.timestamp * 1000).toISOString()}`,
    "",
    p.valid
      ? "> Within canonical caps (max_leverage=10x, risk_per_trade=2% of equity)."
      : "> SIZING REJECTED — see reason. Likely tripped one of: max_leverage cap, daily-loss limit, or position-heat cap.",
  ].join("\n");
}

function formatGenericMarkdown(title: string, data: unknown): string {
  return [
    `# ${title}`,
    "",
    "```json",
    JSON.stringify(data, null, 2),
    "```",
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export function registerRiskTools(server: McpServer): void {
  server.registerTool(
    "coinscope_position_size",
    {
      title: "Calculate Position Size",
      description: `Calculate the recommended position size for a planned trade given entry, stop-loss, and account balance. Optionally uses Kelly-fractional sizing when win_rate and avg_rr are both provided. Output is bounded by the engine's canonical risk caps (max_leverage=10x, risk_per_trade=2%, etc.).

Direction is INFERRED from entry vs. stop_loss:
  - entry > stop_loss → LONG
  - entry < stop_loss → SHORT

Args:
  - symbol (string): USDT-perpetual symbol (default 'BTCUSDT')
  - entry (number): Planned entry price in USDT (required, > 0)
  - stop_loss (number): Stop-loss price in USDT (required, > 0)
  - account_balance (number): Account balance in USDT used as sizing base (required, > 0)
  - win_rate (number, optional): Historical win rate [0,1]; if set WITH avg_rr, Kelly sizing is used
  - avg_rr (number, optional): Average reward/risk; if set WITH win_rate, Kelly sizing is used
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns (JSON shape):
  {
    "symbol": "BTCUSDT", "direction": "LONG",
    "qty": 0.123, "notional": 8000.0,
    "risk_usdt": 200.0, "risk_pct": 2.0,
    "margin_usdt": 800.0, "leverage": 10,
    "method": "fixed" | "kelly_fractional",
    "valid": true, "reason": null,
    "timestamp": 1715000000.0
  }

Examples:
  - Use when: sizing a trade against a known entry/stop pair
  - Use when: comparing fixed-fraction vs. Kelly sizing for a strategy
  - Don't use when: you want to know exposure of CURRENT positions (use coinscope_exposure)

Drift note: CLAUDE.md documents 'POST /position-size' but api.py implements 'GET /position-size' with query params. This tool uses the actual API shape.`,
      inputSchema: PositionSizeShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const queryParams: Record<string, unknown> = {
          symbol: params.symbol.toUpperCase(),
          entry: params.entry,
          stop_loss: params.stop_loss,
          account_balance: params.account_balance,
        };
        if (params.win_rate !== undefined) queryParams.win_rate = params.win_rate;
        if (params.avg_rr !== undefined) queryParams.avg_rr = params.avg_rr;
        const data = await engineRequest<PositionSizeResponse>(
          "/position-size",
          "GET",
          undefined,
          queryParams,
        );
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatPositionSizeMarkdown(data)
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
    "coinscope_exposure",
    {
      title: "Portfolio Exposure",
      description: `Return portfolio exposure metrics: total open notional, gross/net exposure, per-symbol breakdown, and concentration warnings.

Args:
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns: engine-defined exposure snapshot (shape includes totals, per-symbol entries, and any heat-cap warnings).

Examples:
  - Use when: deciding whether a new position would breach the heat cap
  - Use when: checking concentration after a fill
  - For per-position detail use coinscope_positions instead.`,
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
        const data = await engineRequest<Record<string, unknown>>("/exposure");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatGenericMarkdown("Portfolio Exposure", data)
            : JSON.stringify(data, null, 2);
        return {
          content: [{ type: "text", text }],
          structuredContent: data,
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
    "coinscope_positions",
    {
      title: "Open Positions",
      description: `Return all open positions with unrealised PnL.

Args:
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns: engine-defined list of open positions with entry, qty, side, leverage, unrealised_pnl, mark_price.

Examples:
  - Use when: "what's open right now?"
  - Use when: cross-checking the journal against live exchange state.`,
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
        const data = await engineRequest<Record<string, unknown>>("/positions");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatGenericMarkdown("Open Positions", data)
            : JSON.stringify(data, null, 2);
        return {
          content: [{ type: "text", text }],
          structuredContent: data,
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
    "coinscope_circuit_breaker",
    {
      title: "Circuit Breaker State",
      description: `Return the current state of the engine's circuit breaker. READ-ONLY — trip and reset are intentionally NOT exposed via MCP; use the engine API directly with explicit confirmation if you need to act.

Args:
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns: engine-defined breaker state object — typically state ('armed' | 'tripped' | ...), tripped_at, reason, daily PnL counters.

Examples:
  - Use when: investigating why /scan returns 0 actionable signals
  - Use when: confirming the breaker is armed before a session

Out of scope for v0.1 MCP:
  - POST /circuit-breaker/reset (call the engine API directly)
  - POST /circuit-breaker/trip (call the engine API directly)`,
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
        const data = await engineRequest<Record<string, unknown>>("/circuit-breaker");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatGenericMarkdown("Circuit Breaker State", data)
            : JSON.stringify(data, null, 2);
        return {
          content: [{ type: "text", text }],
          structuredContent: data,
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

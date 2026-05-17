/**
 * Journal tools: coinscope_journal, coinscope_performance, coinscope_decisions.
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  engineRequest,
  handleEngineError,
  truncateIfNeeded,
} from "../engineClient.js";
import { ResponseFormat, CHARACTER_LIMIT } from "../constants.js";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const FormatOnlyShape = {
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format"),
};

const JournalShape = {
  days: z
    .number()
    .int()
    .min(1)
    .max(365)
    .default(30)
    .describe("Lookback window in days (1-365)"),
  include_open: z
    .boolean()
    .default(true)
    .describe("Include OPEN entries (true) or only CLOSED ones (false)"),
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format"),
};

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatJournalMarkdown(entries: unknown): string {
  if (!Array.isArray(entries)) {
    return "# Journal\n\n```json\n" + JSON.stringify(entries, null, 2) + "\n```";
  }
  const lines = [
    "# Trade Journal",
    "",
    `- **Entries returned**: ${entries.length}`,
    "",
  ];
  const sample = entries.slice(0, 20);
  for (const e of sample) {
    if (typeof e !== "object" || e === null) continue;
    const r = e as Record<string, unknown>;
    const pnl =
      typeof r.pnl === "number"
        ? `$${r.pnl.toFixed(2)}`
        : r.pnl === null
        ? "open"
        : "—";
    lines.push(
      `- **${r.symbol ?? "?"}** ${r.side ?? "?"} qty=${r.qty ?? r.size ?? "?"} ` +
        `entry=${r.entry_price ?? "?"} pnl=${pnl} ` +
        `[${r.id ?? "no-id"}]`,
    );
  }
  if (entries.length > sample.length) {
    lines.push("", `… (${entries.length - sample.length} more — use response_format='json' for full list)`);
  }
  return lines.join("\n");
}

function formatPerformanceMarkdown(data: Record<string, unknown>): string {
  const winRate = data.win_rate as number | undefined;
  const totalTrades = data.total_trades as number | undefined;
  const totalPnl = data.total_pnl as number | undefined;
  const avgRr = data.avg_rr as number | undefined;
  const sharpe = data.sharpe as number | undefined;
  const maxDd = data.max_drawdown as number | undefined;
  const lines = [
    "# Performance Summary",
    "",
    winRate != null ? `- **Win rate**: ${(winRate * 100).toFixed(1)}%` : null,
    totalTrades != null ? `- **Total trades**: ${totalTrades}` : null,
    totalPnl != null ? `- **Total P&L**: $${totalPnl.toFixed(2)}` : null,
    avgRr != null ? `- **Avg R:R**: ${avgRr.toFixed(2)}` : null,
    sharpe != null ? `- **Sharpe**: ${sharpe.toFixed(2)}` : null,
    maxDd != null ? `- **Max drawdown**: ${(maxDd * 100).toFixed(2)}%` : null,
  ].filter((x): x is string => x !== null);
  lines.push("", "## Full payload", "", "```json", JSON.stringify(data, null, 2), "```");
  return lines.join("\n");
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

export function registerJournalTools(server: McpServer): void {
  server.registerTool(
    "coinscope_journal",
    {
      title: "Trade Journal Entries",
      description: `Return trade journal entries (open + closed) within a lookback window.

Args:
  - days (number, 1-365): Lookback window in days. Default 30.
  - include_open (boolean): Include OPEN entries. Default true.
  - response_format ('markdown' | 'json'): Output format. Default 'markdown'.

Returns: array of journal entries with shape (subset of fields):
  {
    "id": "...",
    "symbol": "BTCUSDT",
    "side": "LONG" | "SHORT",
    "entry_price": 65000.0,
    "exit_price": 66500.0,
    "qty": 0.5,
    "size": 0.5,
    "leverage": 5,
    "pnl": 750.0,            // null for OPEN
    "pnl_pct": 2.3,           // null for OPEN
    "entry_time": "2026-05-01T12:00:00Z",
    "exit_time": "2026-05-01T16:00:00Z",
    "duration_hours": 4.0,
    ...
  }

Examples:
  - Use when: post-trade review, "what closed yesterday?"
  - Use when: computing win rate / avg RR over a window
  - Use coinscope_performance for pre-aggregated stats instead of raw entries.`,
      inputSchema: JournalShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const data = await engineRequest<unknown>("/journal", "GET", undefined, {
          days: params.days,
          include_open: params.include_open,
        });
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatJournalMarkdown(data)
            : JSON.stringify(data, null, 2);
        return {
          content: [
            {
              type: "text",
              text: truncateIfNeeded(
                text,
                CHARACTER_LIMIT,
                "Narrow the lookback window with smaller 'days' or request response_format='json' and process downstream.",
              ),
            },
          ],
          structuredContent: { entries: data } as Record<string, unknown>,
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
    "coinscope_performance",
    {
      title: "Aggregate Performance Stats",
      description: `Aggregate performance stats from the trade journal combined with the current scaling profile. Pre-computed by the engine — cheaper than re-aggregating coinscope_journal client-side.

Args:
  - response_format ('markdown' | 'json'): Output format. Default 'markdown'.

Returns (typical fields, engine-defined):
  {
    "total_trades": 42,
    "win_rate": 0.55,
    "total_pnl": 1234.56,
    "avg_rr": 1.8,
    "sharpe": 1.4,
    "max_drawdown": 0.08,
    "scale_profile": { ... current scale-up tier ... },
    "timestamp": 1715000000.0
  }

Examples:
  - Use when: building a daily P&L digest or weekly review
  - Use when: comparing live performance against the validation-phase gates`,
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
        const data = await engineRequest<Record<string, unknown>>("/performance");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatPerformanceMarkdown(data)
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
    "coinscope_decisions",
    {
      title: "Recent Decisions Log",
      description: `Return recent engine decisions (scan → score → gate → size → arm decisions with rationale).

Args:
  - response_format ('markdown' | 'json'): Output format. Default 'markdown'.

Returns: engine-defined list of decision objects. Each entry typically captures
the symbol, regime, score, gate result (pass/fail with reason), and final action.

Examples:
  - Use when: explaining why a high-score signal wasn't taken
  - Use when: auditing the gate behavior over the last session
  - Use coinscope_journal for FILLED trades; this tool covers the upstream decision flow.`,
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
        const data = await engineRequest<unknown>("/decisions");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatGenericMarkdown("Recent Decisions", data)
            : JSON.stringify(data, null, 2);
        return {
          content: [
            {
              type: "text",
              text: truncateIfNeeded(
                text,
                CHARACTER_LIMIT,
                "Use response_format='json' and process downstream if the list is too large.",
              ),
            },
          ],
          structuredContent: { decisions: data } as Record<string, unknown>,
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

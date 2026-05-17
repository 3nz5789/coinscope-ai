/**
 * Signals tools: coinscope_signals, coinscope_scan_status, coinscope_scan_trigger.
 *
 * Note: coinscope_scan_trigger is the only NON-read-only tool in v0.1.
 * It triggers a scan cycle but does NOT place orders or modify any
 * canonical state. It is safe to call repeatedly.
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { engineRequest, handleEngineError } from "../engineClient.js";
import { ResponseFormat, CHARACTER_LIMIT } from "../constants.js";
import { truncateIfNeeded } from "../engineClient.js";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const FormatOnlyShape = {
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format (default 'markdown')"),
};

const ScanTriggerShape = {
  pairs: z
    .array(z.string().regex(/^[A-Z0-9]+USDT$/i, "Pairs must be USDT-quoted (e.g. BTCUSDT)"))
    .optional()
    .describe(
      "USDT-perpetual symbols to scan. Omit to use engine's configured scan_pairs.",
    ),
  timeframe: z
    .enum(["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"])
    .default("1h")
    .describe("Kline timeframe to scan on. Default '1h'."),
  limit: z
    .number()
    .int()
    .min(30)
    .max(500)
    .default(100)
    .describe("Number of candles per symbol (30-500, default 100)."),
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format (default 'markdown')"),
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SignalsResponse {
  signals: Array<Record<string, unknown>>;
  count: number;
  actionable: number;
  last_scan_at: number | null;
  age_s: number | null;
  loop: {
    running: boolean;
    scans_total: number;
    scans_failed: number;
    last_scan_at: number | null;
    next_scan_at: number | null;
    seconds_to_next: number | null;
    last_duration_ms: number | null;
    last_signals: number;
    last_actionable: number;
    last_error: string | null;
    interval_s: number;
  };
}

interface ScanTriggerResponse {
  scanned: number;
  actionable: number;
  signals: Array<Record<string, unknown>>;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatSignalsMarkdown(s: SignalsResponse): string {
  const ageStr = s.age_s != null ? `${s.age_s.toFixed(1)}s ago` : "never";
  const loop = s.loop;
  const lines = [
    "# Cached Signals",
    "",
    `- **Count**: ${s.count}`,
    `- **Actionable**: ${s.actionable}`,
    `- **Last scan**: ${ageStr}`,
    "",
    "## Scan loop",
    "",
    `- **Running**: ${loop.running ? "yes" : "no"}`,
    `- **Interval**: ${loop.interval_s}s`,
    `- **Scans total / failed**: ${loop.scans_total} / ${loop.scans_failed}`,
    `- **Last duration**: ${loop.last_duration_ms != null ? `${loop.last_duration_ms}ms` : "n/a"}`,
    `- **Next scan in**: ${loop.seconds_to_next != null ? `${loop.seconds_to_next.toFixed(1)}s` : "n/a"}`,
    loop.last_error ? `- **Last error**: ${loop.last_error}` : "- **Last error**: none",
    "",
    "## Sample signals (first 5)",
    "",
    "```json",
    JSON.stringify(s.signals.slice(0, 5), null, 2),
    "```",
  ];
  return lines.join("\n");
}

function formatScanTriggerMarkdown(r: ScanTriggerResponse): string {
  return [
    "# Scan Triggered",
    "",
    `- **Scanned**: ${r.scanned} symbols`,
    `- **Actionable**: ${r.actionable}`,
    `- **At**: ${new Date(r.timestamp * 1000).toISOString()}`,
    "",
    "## Signals (first 5)",
    "",
    "```json",
    JSON.stringify(r.signals.slice(0, 5), null, 2),
    "```",
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

export function registerSignalsTools(server: McpServer): void {
  server.registerTool(
    "coinscope_signals",
    {
      title: "Latest Signals + Scan Loop State",
      description: `Return the most recently cached scored signals plus the state of the background scan loop.

Args:
  - response_format ('markdown' | 'json'): Output format (default: 'markdown')

Returns (JSON shape, abbreviated):
  {
    "signals": [ ... per-symbol signal objects ... ],
    "count": 12,
    "actionable": 3,
    "last_scan_at": 1715000000.0,
    "age_s": 12.4,
    "loop": {
      "running": true,
      "scans_total": 42,
      "scans_failed": 0,
      "last_scan_at": 1715000000.0,
      "next_scan_at": 1715000060.0,
      "seconds_to_next": 47.6,
      "last_duration_ms": 234,
      "last_signals": 12,
      "last_actionable": 3,
      "last_error": null,
      "interval_s": 60
    }
  }

Examples:
  - Use when: "What signals are live right now?"
  - Use when: "Is the scan loop healthy?"
  - Use coinscope_scan_trigger if you want a FRESH scan, not the cached one.

Notes:
  - Signal shape varies by signal type (volume / pattern / funding / orderbook / liquidation).
  - Markdown output truncates to first 5 signals; use response_format='json' for the full set.`,
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
        const data = await engineRequest<SignalsResponse>("/signals");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatSignalsMarkdown(data)
            : JSON.stringify(data, null, 2);
        return {
          content: [
            {
              type: "text",
              text: truncateIfNeeded(
                text,
                CHARACTER_LIMIT,
                "Use response_format='json' or filter by symbol downstream.",
              ),
            },
          ],
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
    "coinscope_scan_status",
    {
      title: "Scan Loop Health",
      description: `Return the background scan loop's health and cadence: running state, total scans, failures, last/next scan timestamps, last duration, last error.

Args:
  - response_format ('markdown' | 'json'): Output format (default: 'markdown')

Returns (JSON shape):
  {
    "running": true,
    "scans_total": 42,
    "scans_failed": 0,
    "last_scan_at": 1715000000.0,
    "next_scan_at": 1715000060.0,
    "seconds_to_next": 47.6,
    "last_duration_ms": 234,
    "last_signals": 12,
    "last_actionable": 3,
    "last_error": null,
    "age_s": 12.4,
    "interval_s": 60
  }

Examples:
  - Use when: troubleshooting why /signals returns stale data
  - Use when: confirming the engine is actively scanning vs. paused`,
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
        const data = await engineRequest<Record<string, unknown>>("/scan/status");
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? "# Scan Loop Status\n\n```json\n" + JSON.stringify(data, null, 2) + "\n```"
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
    "coinscope_scan_trigger",
    {
      title: "Trigger Immediate Scan",
      description: `Trigger an immediate scan of the requested USDT-perpetual pairs. Results are returned directly and also refresh the cache backing coinscope_signals.

This tool DOES NOT place orders, modify positions, or change any canonical state. It only runs a scan cycle. Safe to call repeatedly.

Args:
  - pairs (string[], optional): USDT-perpetual symbols (e.g. ["BTCUSDT", "ETHUSDT"]). Omit to use the engine's configured scan_pairs.
  - timeframe ('1m'|'3m'|'5m'|'15m'|'30m'|'1h'|'2h'|'4h'|'6h'|'12h'|'1d'): Default '1h'.
  - limit (number, 30-500): Candles per symbol. Default 100.
  - response_format ('markdown' | 'json'): Output format. Default 'markdown'.

Returns (JSON shape):
  {
    "scanned": 12,
    "actionable": 3,
    "signals": [ ... per-symbol scored signal objects ... ],
    "timestamp": 1715000000.0
  }

Examples:
  - Use when: user asks "scan right now" or "what's setting up?"
  - Use when: after a regime flip on a key symbol, you want fresh confluence scores
  - Don't use when: the cache (coinscope_signals.age_s) is fresh enough already`,
      inputSchema: ScanTriggerShape,
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const body: Record<string, unknown> = {
          timeframe: params.timeframe,
          limit: params.limit,
        };
        if (params.pairs && params.pairs.length > 0) {
          body.pairs = params.pairs.map((p) => p.toUpperCase());
        }
        const data = await engineRequest<ScanTriggerResponse>(
          "/scan",
          "POST",
          body,
        );
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatScanTriggerMarkdown(data)
            : JSON.stringify(data, null, 2);
        return {
          content: [
            {
              type: "text",
              text: truncateIfNeeded(
                text,
                CHARACTER_LIMIT,
                "Re-query with a narrower pairs list for full detail.",
              ),
            },
          ],
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

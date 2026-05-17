/**
 * Intelligence tools: coinscope_regime, coinscope_sentiment, coinscope_anomaly.
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { engineRequest, handleEngineError } from "../engineClient.js";
import { ResponseFormat } from "../constants.js";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const SymbolOnlyShape = {
  symbol: z
    .string()
    .regex(/^[A-Z0-9]+USDT$/i, "Symbol must be a USDT-quoted perpetual (e.g. BTCUSDT)")
    .default("BTCUSDT")
    .describe("USDT-perpetual symbol (e.g. BTCUSDT, ETHUSDT)"),
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format"),
};

const RegimeShape = {
  symbol: z
    .string()
    .regex(/^[A-Z0-9]+USDT$/i, "Symbol must be a USDT-quoted perpetual (e.g. BTCUSDT)")
    .default("BTCUSDT")
    .describe("USDT-perpetual symbol"),
  timeframe: z
    .enum(["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"])
    .default("1h")
    .describe("Kline timeframe for the regime classifier"),
  limit: z
    .number()
    .int()
    .min(60)
    .max(500)
    .default(150)
    .describe("Number of candles used to compute features (60-500)"),
  response_format: z
    .nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format"),
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RegimeResponse {
  symbol: string;
  timeframe: string;
  regime: string;
  confidence: number;
  probabilities?: Record<string, number>;
  state_probs?: Record<string, number>;
  model: string;
  candles_used: number;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatRegimeMarkdown(r: RegimeResponse): string {
  const probs = r.probabilities ?? r.state_probs ?? {};
  const probLines = Object.entries(probs)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `  - ${k}: ${(v * 100).toFixed(1)}%`);
  return [
    `# Regime — ${r.symbol} (${r.timeframe})`,
    "",
    `- **Regime**: \`${r.regime}\``,
    `- **Confidence**: ${(r.confidence * 100).toFixed(1)}%`,
    `- **Model**: ${r.model}`,
    `- **Candles used**: ${r.candles_used}`,
    `- **As of**: ${new Date(r.timestamp * 1000).toISOString()}`,
    "",
    "## Probability distribution",
    "",
    probLines.join("\n") || "  (no probability distribution returned)",
  ].join("\n");
}

function formatGenericObjectMarkdown(title: string, data: unknown): string {
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

export function registerIntelligenceTools(server: McpServer): void {
  server.registerTool(
    "coinscope_regime",
    {
      title: "Market Regime Classification",
      description: `Detect the current market regime for a USDT-perpetual symbol using the v3 ML classifier (ensemble RF + XGB) with HMM fallback.

Args:
  - symbol (string): USDT-perpetual symbol (default 'BTCUSDT')
  - timeframe (enum): Kline timeframe — '1m','3m','5m','15m','30m','1h','2h','4h','6h','12h','1d' (default '1h')
  - limit (number, 60-500): Candles used for feature computation (default 150)
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns (JSON shape):
  {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "regime": "trending" | "mean_reverting" | "volatile" | "quiet",
    "confidence": 0.78,
    "probabilities": { "trending": 0.78, "mean_reverting": 0.15, ... }  // v3 model
       OR
    "state_probs": { ... },  // HMM fallback
    "model": "v3_ensemble_rf_xgb" | "hmm_fallback",
    "candles_used": 150,
    "timestamp": 1715000000.0
  }

Examples:
  - Use when: explaining why a confluence score dropped or rose
  - Use when: deciding if a setup matches its expected regime (trending vs. mean-reverting)
  - Use coinscope_signals for signal scores, not regime alone.

Drift note: CLAUDE.md documents 'GET /regime/{symbol}' but api.py implements 'GET /regime?symbol=...'. This tool uses the actual API shape.`,
      inputSchema: RegimeShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const data = await engineRequest<RegimeResponse>("/regime", "GET", undefined, {
          symbol: params.symbol.toUpperCase(),
          timeframe: params.timeframe,
          limit: params.limit,
        });
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatRegimeMarkdown(data)
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
    "coinscope_sentiment",
    {
      title: "Sentiment Score",
      description: `Return the latest sentiment score for a symbol. Shape is engine-defined; presented as JSON when markdown is not richer.

Args:
  - symbol (string): USDT-perpetual symbol (default 'BTCUSDT')
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns: engine-defined object with sentiment score, sources, and timestamp.

Examples:
  - Use when: cross-checking a high-conviction signal against sentiment alignment
  - Use when: troubleshooting why a sentiment-weighted score moved`,
      inputSchema: SymbolOnlyShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const data = await engineRequest<Record<string, unknown>>(
          "/sentiment",
          "GET",
          undefined,
          { symbol: params.symbol.toUpperCase() },
        );
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatGenericObjectMarkdown(`Sentiment — ${params.symbol.toUpperCase()}`, data)
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
    "coinscope_anomaly",
    {
      title: "Anomaly Detection",
      description: `Return the engine's anomaly detection output (z-score / isolation-forest style flags on volume, price, OI, funding). Shape is engine-defined.

Args:
  - symbol (string): USDT-perpetual symbol (default 'BTCUSDT')
  - response_format ('markdown' | 'json'): Output format (default 'markdown')

Returns: engine-defined object with anomaly flags + magnitudes per feature.

Examples:
  - Use when: a signal looks too good to be true and you want a sanity check
  - Use when: investigating a sudden P&L move (anomaly might explain a fill outlier)`,
      inputSchema: SymbolOnlyShape,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (params) => {
      try {
        const data = await engineRequest<Record<string, unknown>>(
          "/anomaly",
          "GET",
          undefined,
          { symbol: params.symbol.toUpperCase() },
        );
        const text =
          params.response_format === ResponseFormat.MARKDOWN
            ? formatGenericObjectMarkdown(`Anomaly — ${params.symbol.toUpperCase()}`, data)
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

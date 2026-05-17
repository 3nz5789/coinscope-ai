/**
 * Shared HTTP client for the CoinScopeAI Engine API.
 *
 * - Single axios-backed `engineRequest` function used by every tool
 * - Strict 4xx/5xx → typed error classes
 * - `handleEngineError` turns errors into actionable, agent-friendly strings
 *   per MCP best-practices guidance
 */

import axios, { type AxiosResponse } from "axios";
import { ENGINE_URL, REQUEST_TIMEOUT_MS } from "./constants.js";

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

/** Thrown when the engine responds with HTTP >= 400. */
export class EngineHttpError extends Error {
  constructor(
    public status: number,
    public url: string,
    public body: unknown,
  ) {
    super(
      `Engine API responded ${status} at ${url}: ${
        typeof body === "string" ? body : JSON.stringify(body)
      }`,
    );
    this.name = "EngineHttpError";
  }
}

/** Thrown when the engine cannot be reached at all (refused, timeout, DNS). */
export class EngineConnectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EngineConnectionError";
  }
}

/**
 * Make a request to the engine API and return its decoded JSON body.
 *
 * Throws `EngineHttpError` on 4xx/5xx, `EngineConnectionError` on transport
 * failure, and re-throws unexpected errors.
 */
export async function engineRequest<T = unknown>(
  endpoint: string,
  method: HttpMethod = "GET",
  body?: unknown,
  params?: Record<string, unknown>,
): Promise<T> {
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${ENGINE_URL}${path}`;
  try {
    const response: AxiosResponse<unknown> = await axios({
      method,
      url,
      data: body,
      params,
      timeout: REQUEST_TIMEOUT_MS,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      // Let us inspect 4xx bodies for FastAPI HTTPException details.
      validateStatus: (s) => s >= 200 && s < 600,
    });
    if (response.status >= 400) {
      throw new EngineHttpError(response.status, url, response.data);
    }
    return response.data as T;
  } catch (err) {
    if (err instanceof EngineHttpError) throw err;
    if (axios.isAxiosError(err)) {
      const code = err.code;
      if (code === "ECONNREFUSED") {
        throw new EngineConnectionError(
          `Engine API at ${ENGINE_URL} refused the connection. ` +
            `Is the engine running? Start it locally with: ` +
            `cd coinscope_trading_engine && uvicorn api:app --port 8001`,
        );
      }
      if (code === "ECONNABORTED" || code === "ETIMEDOUT") {
        throw new EngineConnectionError(
          `Engine API request to ${url} timed out after ${REQUEST_TIMEOUT_MS}ms.`,
        );
      }
      if (code === "ENOTFOUND") {
        throw new EngineConnectionError(
          `Engine API host could not be resolved (${ENGINE_URL}). ` +
            `Check COINSCOPE_ENGINE_URL.`,
        );
      }
    }
    throw err;
  }
}

/**
 * Convert any engine-call exception into an agent-actionable message.
 * Never throws.
 */
export function handleEngineError(error: unknown): string {
  if (error instanceof EngineHttpError) {
    if (error.status === 404) {
      return (
        `Error: Engine endpoint not found at ${error.url}. ` +
        `The API surface may have changed — check coinscope_trading_engine/api.py for the current route list.`
      );
    }
    if (error.status === 422) {
      return (
        `Error: Engine rejected the request as malformed (HTTP 422). ` +
        `Validation details: ${JSON.stringify(error.body)}`
      );
    }
    if (error.status >= 500) {
      return (
        `Error: Engine returned HTTP ${error.status} (internal error). ` +
        `Details: ${
          typeof error.body === "string" ? error.body : JSON.stringify(error.body)
        }. ` +
        `Check the engine logs for traceback.`
      );
    }
    return (
      `Error: Engine returned HTTP ${error.status} at ${error.url}. ` +
      `Details: ${
        typeof error.body === "string" ? error.body : JSON.stringify(error.body)
      }`
    );
  }
  if (error instanceof EngineConnectionError) {
    return `Error: ${error.message}`;
  }
  if (error instanceof Error) {
    return `Error: ${error.message}`;
  }
  return `Error: ${String(error)}`;
}

/**
 * Truncate a long text response with a clear note for the agent.
 */
export function truncateIfNeeded(
  text: string,
  limit: number,
  hint?: string,
): string {
  if (text.length <= limit) return text;
  const truncated = text.slice(0, limit);
  const suffix = hint
    ? `\n\n…\n[truncated from ${text.length} to ${limit} characters. ${hint}]`
    : `\n\n…\n[truncated from ${text.length} to ${limit} characters]`;
  return truncated + suffix;
}

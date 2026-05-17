/**
 * Shared constants for the coinscope-mcp-server.
 */

/** Base URL of the running engine API. Override with COINSCOPE_ENGINE_URL. */
export const ENGINE_URL: string =
  process.env.COINSCOPE_ENGINE_URL ?? "http://localhost:8001";

/** Maximum time (ms) to wait for any single engine API call. */
export const REQUEST_TIMEOUT_MS = 30_000;

/** Maximum characters in any tool response before truncation kicks in. */
export const CHARACTER_LIMIT = 25_000;

/** Server identity (must match package.json name + version). */
export const SERVER_NAME = "coinscope-mcp-server";
export const SERVER_VERSION = "0.1.0";

/** Supported response formats for every tool. */
export enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json",
}

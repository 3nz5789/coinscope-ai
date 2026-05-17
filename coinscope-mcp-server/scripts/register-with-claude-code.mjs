#!/usr/bin/env node
/**
 * register-with-claude-code.mjs
 *
 * Idempotently registers the coinscope-mcp-server in ~/.claude.json so
 * Claude Code can discover and connect to it via stdio.
 *
 * - Reads ~/.claude.json (creates a fresh one if missing)
 * - Backs it up as ~/.claude.json.bak.<unix-timestamp>
 * - Sets mcpServers.coinscope = { command, args, env } — preserves every
 *   other key and every other MCP server entry
 * - Writes back as pretty JSON
 *
 * Safe to run multiple times — overwrites only the "coinscope" entry.
 *
 * Usage:
 *   node ~/Code/CoinScopeAI/coinscope-mcp-server/scripts/register-with-claude-code.mjs
 *   node ~/Code/CoinScopeAI/coinscope-mcp-server/scripts/register-with-claude-code.mjs --remove
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const CLAUDE_JSON = path.join(os.homedir(), ".claude.json");
const SERVER_NAME = "coinscope";
const ENTRY_POINT = path.join(
  os.homedir(),
  "Code/CoinScopeAI/coinscope-mcp-server/dist/index.js",
);
const REMOVE = process.argv.includes("--remove");

function loadConfig() {
  if (!fs.existsSync(CLAUDE_JSON)) {
    return {};
  }
  const raw = fs.readFileSync(CLAUDE_JSON, "utf-8");
  if (raw.trim().length === 0) return {};
  try {
    return JSON.parse(raw);
  } catch (err) {
    console.error(
      `[register] ${CLAUDE_JSON} is not valid JSON. Aborting so you don't lose it.`,
    );
    console.error(`[register] Parse error: ${err.message}`);
    process.exit(2);
  }
}

function backup() {
  if (!fs.existsSync(CLAUDE_JSON)) return null;
  const ts = Math.floor(Date.now() / 1000);
  const bak = `${CLAUDE_JSON}.bak.${ts}`;
  fs.copyFileSync(CLAUDE_JSON, bak);
  return bak;
}

function save(cfg) {
  fs.writeFileSync(CLAUDE_JSON, JSON.stringify(cfg, null, 2) + "\n");
}

function main() {
  if (!fs.existsSync(ENTRY_POINT)) {
    console.error(
      `[register] ERROR: ${ENTRY_POINT} does not exist. Run 'npm run build' in the coinscope-mcp-server directory first.`,
    );
    process.exit(1);
  }

  const cfg = loadConfig();
  cfg.mcpServers ??= {};

  if (REMOVE) {
    if (!(SERVER_NAME in cfg.mcpServers)) {
      console.log(`[register] '${SERVER_NAME}' is not in mcpServers — nothing to remove.`);
      return;
    }
    const bak = backup();
    delete cfg.mcpServers[SERVER_NAME];
    save(cfg);
    console.log(`[register] Removed '${SERVER_NAME}' from mcpServers.`);
    if (bak) console.log(`[register] Backup at: ${bak}`);
    return;
  }

  const before = cfg.mcpServers[SERVER_NAME];
  cfg.mcpServers[SERVER_NAME] = {
    command: "node",
    args: [ENTRY_POINT],
    env: {
      COINSCOPE_ENGINE_URL: "http://localhost:8001",
    },
  };

  const bak = backup();
  save(cfg);

  if (before) {
    console.log(`[register] Updated existing '${SERVER_NAME}' entry in mcpServers.`);
  } else {
    console.log(`[register] Added '${SERVER_NAME}' to mcpServers.`);
  }
  if (bak) console.log(`[register] Backup at: ${bak}`);
  console.log(`[register] Entry point: ${ENTRY_POINT}`);
  console.log(`[register] Restart Claude Code (or the relevant client) to pick up the change.`);
  console.log("");
  console.log("Other mcpServers currently registered:");
  for (const name of Object.keys(cfg.mcpServers).sort()) {
    console.log(`  - ${name}${name === SERVER_NAME ? " (just registered)" : ""}`);
  }
}

main();

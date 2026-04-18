# INCIDENT — Binance WebSocket Disconnect Storm

**Incident ID:** `INC-2026-04-18-BINANCE-WS`
**Detected:** 2026-04-18 (UTC+3, Jordan)
**Author:** Scoopy (CoinScopeAI core agent)
**Status:** Draft — pending Mohammed confirmation of live/historical state
**Phase context:** Mid 30-Day Testnet Validation (COI-41). **No engine code changes permitted** unless SEV1 and necessary for capital preservation.
**Severity (proposed):** **SEV2** by default — market data blackout degrades the scanner and can mask risk-gate triggers. Escalate to **SEV1** if the recording daemon is down for > 15 min or if open positions exist and position stream is impaired.

---

## 1. Summary

Binance Futures WebSocket client(s) are dropping and reconnecting in a correlated burst — a "disconnect storm." Symptoms observed in similar prior events:

- `ConnectionClosedError` / `ConnectionClosedOK` spikes in `coinscope_trading_engine/data/market_stream.py`
- `BinanceWebSocketClient` (signed WS API for orders/account, `binance_websocket_client.py`) re-authenticating repeatedly
- Dashboard `https://coinscopedash-tltanhwx.manus.space` flipping to **MOCK DATA** badge intermittently
- EventBus event rate falling below the baseline **133 events/sec** (per project history doc)

Because the engine runs a **single asyncio loop** and launches streams via `BinanceFuturesMultiStreamManager`, a correlated drop of N sub-clients results in a synchronized reconnect wave. That wave itself can trip the **5-connection-per-5-minute per-IP** WS rate limit, extending the outage.

> Validation-phase rule: the engine code is frozen. Everything below is **config, ops, and monitoring work**. No reconnect-logic rewrites until the validation window closes (or SEV1 justification is recorded).

---

## 2. Impact

| Surface | Impact |
|---|---|
| Market scanner (`/scan`) | Stale — regime labels and entry-timing score computed from last good klines |
| `/regime/{symbol}` | Returns last cached value; risk of label drift (Trending ⇄ Volatile) |
| Risk gate | **Still enforces thresholds** (daily loss 5%, max DD 10%) from stored PnL — *not* bypassed. Position sizing continues to read from last-known equity. |
| Order placement | If `binance_websocket_client.py` is the affected client, order WS fails over to REST fallback (if implemented) or blocks — **validate on the box** |
| Telegram alerts (`@ScoopyAI_bot`, chat 7296767446) | No dedicated `ws_disconnect` handler in `alerts/telegram_alerts.py` — drops are silent unless logs are tailed |
| Dashboard MOCK DATA badge | Correctly flips when `localhost:8001` health check fails — user-visible signal |
| Recording daemon (133 ev/s baseline) | Data gaps in MemPalace; replay consistency test (`QA_WS_REPLAY_CONSISTENCY_2026-04-16.md`) validated integrity **on clean input**, not through disconnect gaps |

**Capital-preservation posture:** risk gate + kill switch logic is independent of the WS stream. Existing positions are not force-liquidated by a stream outage, but new entries should be paused until streams recover.

---

## 3. Triage + Mitigation Playbook (run in order)

### Step 0 — Severity assessment (30 sec)

```bash
# On the DO droplet (once provisioned — if pre-deploy, run locally in docker compose)
curl -s http://localhost:8001/health | jq .
curl -s http://localhost:8001/risk-gate | jq .
docker compose logs --tail=200 api | grep -iE "ConnectionClosed|reconnect|auth failed"
```

- Any `"status": "degraded"` + open positions → **SEV1**
- Stream drops > 1/min sustained → **SEV2**
- Single isolated drop that auto-recovered → **SEV3**, just log

### Step 1 — Stop the bleed: pause new entries

The engine must keep risk gate evaluation running, but new entry signals should be suppressed while data is stale. Two supported mechanisms:

**Option A — flip the kill-switch flag** (preferred; preserves open positions):
```bash
# Inside the api container (or wherever the kill switch state is read)
# See /CoinScopeAI/RISK_KillSwitch_DecisionTree.docx for state table
curl -X POST http://localhost:8001/risk-gate -d '{"action":"pause_new_entries","reason":"WS_STORM"}'
```
(If that endpoint doesn't accept `action`, set the env flag and restart the scanner task only — *not* the whole stack.)

**Option B — widen scan interval to starve the retry loop:**
```bash
# Temporary ops knob — does NOT touch engine logic
# .env override (on the VPS)
SCAN_INTERVAL_SECONDS=900        # from 14400=4h, raise to 15min only if scanner is storming
```

### Step 2 — Check if this is Binance-side

Binance does not always publish incidents in real time. Check in this order:

1. `curl -s -o /dev/null -w "%{http_code}\n" https://fstream.binance.com` (expect 4xx, not 5xx/timeout)
2. `websocat wss://stream.binancefuture.com/ws/btcusdt@kline_1m` — raw probe, no engine involvement
3. https://www.binance.com/en/support/announcement (futures WS maintenance windows)
4. Binance API Telegram channel / `@binance_api` on X

> **2026-04-23 Binance WS migration (5 days out):** your `.env.template` already carries `BINANCE_WS_PUBLIC_PATH=/public`, `/market`, `/private`. If any service on the VPS is pinned to the **old** endpoints while Binance is staging the cutover early, you will see exactly this pattern: random drops with clean reconnects. Confirm the engine is using `BINANCE_WS_TESTNET_URL + /ws/<stream>` (old path) vs the new migration paths. **Do not migrate early** without Mohammed's signoff — wait for the 2026-04-23 cutover announcement.

### Step 3 — Check if this is client-side (DO SGP1 → testnet.binancefuture.com)

```bash
# Latency + packet loss to the testnet stream edge
mtr -rwc 50 stream.binancefuture.com
# DNS — rare but fatal
dig stream.binancefuture.com +short
# IPv6 silent failure (common on DO): force v4
curl -4 -I https://stream.binancefuture.com
```

Singapore → `stream.binancefuture.com` routes through different PoPs than `fstream.binance.com` (mainnet) — testnet is intrinsically flakier. Not a "fix," but relevant context for expectation-setting.

### Step 4 — Failover *within Binance*, not to other exchanges

Memory says "multi-exchange streams (Binance, Bybit, OKX, Hyperliquid)" exist in GitHub, but the workspace audit shows **only Binance is wired into the live engine** — whale filter mentions other exchanges as data sources only. **Do not rely on cross-exchange failover mid-incident.** Failover options that actually exist:

- `WS_BACKEND=python-binance` has built-in keepalive — per `TROUBLESHOOTING.md §4`, this is the documented switch for repeated drops
- Fall back to REST polling via `binance_rest.py` with a slowed scan interval (Step 1, Option B)

### Step 5 — Alerting (temporary while validation is frozen)

There is **no dedicated WS-disconnect handler** in `alerts/telegram_alerts.py`. Short-term fix that does **not** touch engine code:

- Tail `docker compose logs api` and pipe `ConnectionClosed` matches into `scripts/telegram_report.py` (the script memory notes as "in GitHub, not in local workspace")
- Or: set up a cron/systemd-timer that curls `/health` every 60s and `send_critical`s on non-200

---

## 4. Root-Cause Analysis — ranked hypotheses

Ranked by likelihood against the CoinScopeAI stack as it exists **today (pre-VPS, local docker compose only — COI-40 still open)**.

| # | Hypothesis | Why it's likely | How to confirm |
|---|---|---|---|
| **1** | **Binance 24-hour connection TTL** | `binance_websocket_client.py` docstring explicitly calls it out: "24-hour connection TTL with auto-reconnect 60s before expiry." If N streams all came up at `docker compose up` time, they all hit TTL within seconds of each other. Classic disconnect storm. | `grep "Connecting to" logs` — cluster of reconnect timestamps ~24h after startup. |
| **2** | **2026-04-23 Binance WS endpoint migration staging** | `.env.template` has the new `/public` `/market` `/private` paths. Binance often stages migrations 3–7 days before the cutover. You are 5 days out. | Compare actual URL being connected (`logger.info("Stream connected → %s", self.url)`) to the announcement. |
| **3** | **Reconnect thundering herd — no jitter** | `market_stream.py` has pure exponential backoff, no jitter. `BinanceFuturesMultiStreamManager` spawns parallel clients that all use the **same** `RECONNECT_INITIAL_S = 1`. When one global event drops them, they re-handshake in lockstep and can trip the 5-conns/5-min IP limit. | Count distinct reconnect timestamps in logs — if they cluster inside a 1s window, it's thundering-herd. |
| **4** | **Network path — DO SGP1 ↔ testnet.binancefuture.com** | Testnet has fewer PoPs than mainnet. Memory shows the droplet is not yet provisioned, but the symptom is identical when it is. | `mtr` + `curl -4` from the droplet once up. Pre-provision: can't confirm. |
| **5** | **Client ping/pong too aggressive** | Both clients use `ping_interval=20, ping_timeout=10`. Binance sends its own ping every 3 min; the `websockets` library ping layer is independent. On a jittery network, a 10s pong timeout drops the connection before Binance would have. | Try `ping_interval=30, ping_timeout=30` on a **single stream** in a throwaway container. Not a code change to the engine — only the `.env` overrides. |
| **6** | **Testnet API key rotation / auth drift** | Affects `binance_websocket_client.py` (signed WS API) only, not `market_stream.py`. `Auth failed` errors cluster with reconnects. | `grep "Auth failed" logs` in the signed WS client. |

### 5-Whys applied to Hypothesis #1 (most likely)

1. **Why did the streams all drop together?** Binance closed them on its 24-hour TTL.
2. **Why did they all hit TTL at the same time?** They all connected at the same `docker compose up` event.
3. **Why didn't we stagger them?** Because `BinanceFuturesMultiStreamManager.start()` creates all sub-client tasks with `asyncio.gather` at t=0.
4. **Why didn't the reconnect loop smooth the recovery?** Because there's no jitter in `RECONNECT_INITIAL_S=1`, so all sub-clients retry in lockstep and potentially trip the per-IP connection rate limit.
5. **Why didn't we know immediately?** No `ws_disconnect` path in the Telegram alerter; the MOCK DATA badge only flips when the **HTTP API** is unreachable, not when streams are degraded.

→ **Root cause candidate:** synchronized connection lifecycle + no reconnect jitter + no stream-level alerting.

---

## 5. Action Items (post-validation, do not implement during freeze)

| # | Action | Owner | Priority | Earliest |
|---|---|---|---|---|
| AI-1 | Add reconnect jitter (`backoff * (0.5 + random())`) in `market_stream.py` and `binance_websocket_client.py` | Mohammed | P1 | Post-COI-41 |
| AI-2 | Stagger sub-client starts in `BinanceFuturesMultiStreamManager` by 1–3s each | Mohammed | P1 | Post-COI-41 |
| AI-3 | Add `send_ws_disconnect` handler to `alerts/telegram_alerts.py` with 5-min debounce | Mohammed | P1 | Post-COI-41 |
| AI-4 | Pre-cutover dry run of Binance 2026-04-23 WS migration paths on a branch | Mohammed | P0 | **Before 2026-04-23** |
| AI-5 | Widen default `ping_timeout` to 30s after benchmarking against testnet from SGP1 | Mohammed | P2 | Post-COI-41 |
| AI-6 | Add stream-health widget to dashboard (distinct from API health / MOCK DATA badge) | Mohammed | P2 | Post-COI-41 |
| AI-7 | Document this runbook in `docs/OPS_WS_Disconnect_Storm_Runbook.md` (companion to `OPS_Daily_Market_Scan_Runbook.md`) | Scoopy | P1 | This week |

> AI-4 is the **only** pre-freeze-expiry action — it's about testing, not changing, engine code. Given the 2026-04-23 cutover, treat it as validation-phase-compatible.

---

## 6. Dashboard / Telegram Alert Verification

### 6a. MOCK DATA badge
- Trigger: dashboard cannot reach `/health` on `localhost:8001` (or the deployed VPS IP once COI-40 lands)
- **Does NOT trigger on WS stream degradation** — this is a gap. The `/scan` and `/regime` endpoints will return stale data without flipping the badge.
- Verified behavior per `TROUBLESHOOTING.md`: "MOCK DATA badge still showing → Engine API not reachable from dashboard — check IP/port and CORS config"

### 6b. Telegram (`@ScoopyAI_bot`, chat 7296767446)
`alerts/telegram_alerts.py` exposes: `send_signal`, `send_trade_closed`, `send_alert(level, message)`, `send_heartbeat(stats)`, `send_info`, `send_critical`. **No `send_ws_disconnect` or `send_stream_gap`.** During this incident:

- Use `send_critical("WS storm — market data stale for Xs, new entries paused")` manually from ops
- Or invoke `send_alert("ERROR", ...)` from a log-tailing cron (zero engine code change)

### 6c. Recording daemon (133 ev/s baseline)
`QA_WS_REPLAY_CONSISTENCY_2026-04-16.md` validated determinism and float-precision stability **on clean input**. It did **not** cover disconnect-gap handling. Expected behavior during a storm: FIFO queue keeps filling from the surviving streams; dropped streams produce **gaps, not corruption** — safe, but visible in EventBus rate drop.

---

## 7. Timeline skeleton (fill in with real times)

| Time (UTC+3) | Event |
|---|---|
| `HH:MM` | First `ConnectionClosedError` in market_stream logs |
| `HH:MM` | MOCK DATA badge appears on dashboard |
| `HH:MM` | Scoopy/ops acknowledges |
| `HH:MM` | Triage Step 1 applied — new entries paused |
| `HH:MM` | Binance status page checked (no announcement / announcement at HH:MM) |
| `HH:MM` | Reconnect sequence stabilizes — continuous frames for 5 min |
| `HH:MM` | MOCK DATA badge clears |
| `HH:MM` | Incident closed, postmortem due within 48h |

---

## 8. What I need from you

To finalize this from **template** into a proper postmortem, please paste or upload:

1. **A 200–500 line chunk of `docker compose logs api`** from around the storm window — specifically `grep -E "Connecting|Stream connected|ConnectionClosed|Auth"`
2. **First and last timestamp** of the disconnect burst (so I can compute duration + candidate 24h TTL rollover)
3. **Whether the droplet is provisioned yet** (COI-40 blocker memory says "not yet" — if still local docker, some of Step 3's checks are moot)
4. **Whether any open testnet positions exist** right now (drives SEV1 vs SEV2)

With those, I'll write the timeline, compute exact MTTD/MTTR, promote the ranked RCA to a single confirmed root cause, and turn Section 5 into Linear tickets linked to COI-41.

---

## References (internal)

- Code: `coinscope_trading_engine/data/market_stream.py`, `coinscope_trading_engine/binance_websocket_client.py`, `coinscope_trading_engine/data/binance_stream_adapter.py`
- Docs: `TROUBLESHOOTING.md §4 WebSocket Issues`, `docs/QA_WS_REPLAY_CONSISTENCY_2026-04-16.md`, `RISK_KillSwitch_DecisionTree.docx`
- Config: `.env.template` — see `BINANCE_WS_*_PATH` migration block, effective 2026-04-23
- Deployment: `DO_DEPLOYMENT_GUIDE.md`, engine API on port 8001
- Linear: link this incident to **COI-41** (validation phase). Do **not** open a new engine-code-change issue until the validation window closes.

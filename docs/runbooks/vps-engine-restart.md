# VPS Engine Restart Runbook

**Purpose:** Apply patched `.env` values to the running engine on `api.coinscope.ai` and verify `/config` reflects the new canonical thresholds.

**When to run:**
- Bundled with **COI-40** (VPS deploy finalization).
- Any time `MAX_OPEN_POSITIONS`, `MAX_LEVERAGE`, `MAX_DRAWDOWN_PCT`, `MAX_DAILY_LOSS_PCT`, or `POSITION_HEAT_CAP_PCT` changes in canonical docs.

**Pre-flight:**
- Local docs reconciled and `scripts/risk_threshold_guardrail.py` returns clean.
- Cowork `project_instructions` paste current with `CLAUDE.md`.
- Linear issue (COI-67 or successor) open and ready for closure.

---

## Steps

### 1. SSH to VPS

```bash
ssh root@api.coinscope.ai
cd /opt/coinscope-ai          # or wherever the compose file lives — verify with `docker compose ps`
```

### 2. Sync `.env` with canonical

The canonical `.env` lives in the repo at `coinscope_trading_engine/.env`. Pull and overwrite:

```bash
git fetch origin
git checkout main
git pull origin main
# review the diff before overwriting the running .env
diff -u .env coinscope_trading_engine/.env || true
cp coinscope_trading_engine/.env .env
```

Confirm canonical values:

```bash
grep -E '^(MAX_OPEN_POSITIONS|MAX_LEVERAGE|MAX_DRAWDOWN_PCT|MAX_DAILY_LOSS_PCT|POSITION_HEAT_CAP_PCT)=' .env
```

Expected (as of 2026-05-03):
```
MAX_OPEN_POSITIONS=5
MAX_LEVERAGE=10
MAX_DRAWDOWN_PCT=10.0
MAX_DAILY_LOSS_PCT=5.0
POSITION_HEAT_CAP_PCT=80
```

### 3. Restart with force-recreate

```bash
docker compose down
docker compose pull
docker compose up -d --force-recreate
docker compose ps
```

Wait ~15s for the API to come up, then tail logs to confirm clean boot:

```bash
docker compose logs --tail=100 engine | grep -Ei 'error|exception|risk|config' || true
```

### 4. Verify `/config` reflects canonical

```bash
curl -s https://api.coinscope.ai/config | python3 -m json.tool
```

Spot-check fields:
- `max_open_positions` → `5`
- `max_leverage` → `10`
- `max_drawdown_pct` → `10.0`
- `max_daily_loss_pct` → `5.0`
- `position_heat_cap_pct` → `80`

### 5. Smoke-test `/risk-gate`

```bash
curl -s https://api.coinscope.ai/risk-gate | python3 -m json.tool
```

Expected: `kill_switch: false`, `daily_loss_pct < 5`, `drawdown_pct < 10`, `open_positions < 5`.

### 6. Close Linear

If the running config matches canonical and `/risk-gate` is healthy, close the relevant issue (COI-67 / COI-40) with the curl outputs pasted as confirmation.

---

## Rollback

If `/config` shows wrong values or the engine fails to come up:

```bash
git checkout HEAD~1 -- coinscope_trading_engine/.env
cp coinscope_trading_engine/.env .env
docker compose up -d --force-recreate
```

Then open an incident report under `incidents/` and tag `@scoopy` in the relevant Linear issue.

---

## Notes

- **Testnet only.** This entire procedure runs against Binance Testnet. No real capital.
- Engine logs go to `/var/log/coinscope/engine-*.log` on VPS (rotation: daily, 14 days).
- If `docker compose pull` introduces an unintended image change, pin the tag in `docker-compose.yml` and retry.
- Last canonical-token revision: `max_open_positions` 3 → 5 on 2026-05-03 (decision-log entry `max-open-positions-revised-3-to-5`).

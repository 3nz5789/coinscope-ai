# CoinScopeAI Decision Log

Append-only record of canonical decisions for CoinScopeAI. New entries at the bottom. Each entry is timestamped and signed off by the founder before being treated as canonical.

This file is referenced by `CLAUDE.md` (§ BUSINESS PLAN STATUS, § OPERATING RULES) as the source of truth for every locked decision.

---

## 2026-05-18 — CLAUDE.md v3.1 drift correction after first prod-VPS audit

**Context.** First operator session against the live prod VPS (intended to execute COI-68 + COI-77 per CLAUDE.md v3.1 pending actions) surfaced multiple discrepancies between the doc and the actual deployment. Both items in the v3.1 pending list turned out to be either already-complete or not-applicable.

**Corrections made to CLAUDE.md (bumped to v3.2):**

1. **VPS host identity.** v3.1 said "VPS (DigitalOcean SGP1)". Actual: AWS EC2, public `34.228.111.66`, private `172.31.29.28`. SSH: `ssh -i ~/.ssh/coinscopeai-key.pem ubuntu@34.228.111.66`.

2. **Engine API endpoint list.** v3.1 listed `GET /risk-gate` and `POST /position-size` as canonical. Neither exists on the running build. Canonical list from live `/openapi.json` on 2026-05-18:
   - `GET /health`
   - `GET /scan`
   - `GET /performance`
   - `GET /performance/daily`
   - `GET /journal`
   - `GET /regime/{symbol}`
   - `GET /scale`
   - `POST /scale/check`
   - `GET /validate`

3. **Deployment topology.** Engine runs in Docker via compose at `/opt/coinscopeai/infra/docker/docker-compose.prod.yml`. Six services declared (`engine`, `db`, `redis`, `recorder`, `dashboard`, `telegram-bot`); four currently running (`dashboard` and `telegram-bot` not started). `env_file:` resolves to `/opt/coinscopeai/.env`. Engine container WORKDIR is `/app`, runs as `root`, no bind mounts (`.Mounts == []`).

4. **COI-68 status: already closed before session start.** Container has been up ~17 hours with canonical thresholds. Triple-verified:
   - Host `/opt/coinscopeai/.env` — all 5 target keys at canonical values
   - Engine container `Config.Env` — matches host `.env` exactly
   - Live `GET /health` returns `{"status":"ok","version":"1.0.0"}`
   No `.env` patch and no restart was performed in this session.

5. **COI-77 status: migration not applicable.** Probed inside the engine container — no `scale_up_state.json` exists at `/app/`, at `/root/.coinscopeai/`, or anywhere else. Engine is at `S0_SEED` (`account_usd=1000`, `position_pct=0.01`) — `ScaleUpManager` has never had to persist. When state is first written, the post-COI-77 code in the image will land it at `/root/.coinscopeai/scale_up_state.json` inside the container (HOME=/root, `CSAI_SCALE_UP_STATE_PATH` not set). No migration was performed; nothing to migrate.

**New finding logged as a separate issue:** Engine container has zero bind mounts. State written to `/root/.coinscopeai/scale_up_state.json` lives only in the container's writable layer and will be lost on `docker compose down` or container recreate. The COI-77 path canonicalization is correct, but durable persistence across container lifecycle requires a named volume or bind mount in `docker-compose.prod.yml`. Filed as a new Linear issue (see related issues below).

**Other observations (non-blocking, separately tracked):**
- `coinscopeai-recorder` container has been "unhealthy" for the full 17h uptime — root cause unknown; filed separately.
- `coinscopeai-dashboard` and `coinscopeai-bot` services are declared in compose but not running on the prod VPS.
- `git` is not installed inside the engine container, so in-container code-version checks aren't possible. Recommend a `VERSION` file or build-time label on the image.
- The decision-log path referenced by CLAUDE.md (`_decisions/decision-log.md`) did not exist in the repo until this entry. Active decision-tracking has been via ADRs at `docs/decisions/adr-NNNN-*.md`. This file restores the path CLAUDE.md prescribes; ADRs remain valid for design-level decisions. Reconciliation of the two patterns is open.

**Sources verified (commands run in this session):**
- `sudo docker inspect coinscopeai-engine --format '{{json .Config.Env}}'`
- `sudo docker inspect coinscopeai-engine --format '{{json .Mounts}}'`
- `sudo docker exec coinscopeai-engine sh -c 'ls -la /app/scale_up_state.json; ls -la /root/.coinscopeai/scale_up_state.json; echo HOME=$HOME'`
- `sudo grep -E '^(MAX_OPEN_POSITIONS|MAX_LEVERAGE|NOTION_…)=' /opt/coinscopeai/.env`
- `curl -s http://localhost:8001/openapi.json`
- `curl -s http://localhost:8001/scale` (returned `current=S0_SEED`)
- `curl -s http://localhost:8001/health` (returned `status=ok`)

**Closed by this entry:** COI-68 (canonical .env patched + restarted), COI-69 (post-restart verify).

**Filed by this entry:** new issues for (a) engine container missing volume mount for `/root/.coinscopeai/`, (b) `coinscopeai-recorder` unhealthy investigation, (c) `dashboard`/`telegram-bot` services declared but not running, (d) `_decisions/` vs `docs/decisions/` path reconciliation.

**Signed off:** pending founder review.

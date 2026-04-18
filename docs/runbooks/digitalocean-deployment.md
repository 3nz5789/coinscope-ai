# CoinScopeAI — DigitalOcean Deployment Guide
**Version:** 1.1 | **Date:** April 16, 2026 | **Replaces:** Hetzner CPX32 plan (COI-40)
**Target:** DigitalOcean Basic Droplet — 2 vCPU / 4 GB RAM — Singapore (SGP1)
**Upgrade path:** Resize to 8 GB with one click if validation phase demands it

---

## Why DigitalOcean (vs. Hetzner)

Hetzner was the original recommendation (~$20/mo) but sign-up for non-EU accounts hits a VAT ID
validation wall that blocked deployment. DigitalOcean has **no such restriction**, supports
credit/debit card from Jordan with no issues, and provisions in under 60 seconds.

| | DO Basic 4GB | DO Premium 8GB | Hetzner CPX32 |
|---|---|---|---|
| Monthly cost | ~$24 | ~$48 | ~$20 |
| RAM | 4 GB | 8 GB | 8 GB |
| vCPU | 2 | 4 | 4 |
| Singapore datacenter | ✅ SGP1 | ✅ SGP1 | ✅ SIN |
| No VAT ID required | ✅ | ✅ | ❌ (blocked us) |
| Managed console | ✅ | ✅ | ✅ |
| One-click resize | ✅ → 8GB | — | N/A |

**Start with 4 GB for validation phase.** The 4 GB plan runs the engine, Redis, and core services
comfortably with 4 GB swap as a safety net. If LightGBM models cause OOM pressure during the
30-day testnet run, resize to 8 GB in the DO console (zero data loss, ~5 min downtime).

> ⚠️ **Swap is mandatory on 4 GB.** Step 4.1 below configures 4 GB swap — do not skip it.

---

## Pre-Flight Checklist (do these BEFORE provisioning)

- [ ] DigitalOcean account created at https://cloud.digitalocean.com
- [ ] Payment method added (credit/debit card or PayPal)
- [ ] SSH key generated locally: `ssh-keygen -t ed25519 -C "coinscope-vps"`
- [ ] Public key ready to paste: `cat ~/.ssh/id_ed25519.pub`
- [ ] GitHub repo access confirmed: https://github.com/3nz5789/coinscope-ai
- [ ] `.env` values ready (Binance Testnet API key/secret, Telegram bot token)

---

## Phase 1 — Provision the Droplet

1. Log in to [DigitalOcean Cloud Console](https://cloud.digitalocean.com)
2. Click **Create → Droplets**
3. Configure as follows:

| Setting | Value |
|---------|-------|
| **Region** | Singapore — SGP1 |
| **Datacenter** | SGP1 (only one — select it) |
| **OS** | Ubuntu 22.04 (LTS) x64 |
| **Droplet type** | Basic (Regular Intel or Premium Intel) |
| **Plan** | **2 vCPU / 4 GB RAM / 80 GB SSD (~$24/mo)** |
| **Authentication** | SSH Key — paste your `id_ed25519.pub` |
| **Hostname** | `coinscopeai-prod` |
| **Backups** | Enable (adds ~$9.60/mo — recommended) |
| **Monitoring** | Enable (free — gives DO agent metrics) |

4. Click **Create Droplet** — provisioning takes under 60 seconds.
5. **Note the public IPv4 address** from the dashboard.

> **No domain yet?** That's fine. The engine API runs on the IP directly. SSL/domain is optional
> and covered in Phase 9.

> **To upgrade later:** DO console → Droplet → Resize → select 8 GB plan → Resize Disk & vCPU.
> Takes ~5 minutes. All data, IP address, and config are preserved.

---

## Phase 2 — Server Security & Base Setup

SSH in as root (DO provisions as root by default):

```bash
ssh root@YOUR_DROPLET_IP
```

### 2.1 Create a non-root user

```bash
adduser ubuntu
usermod -aG sudo ubuntu

# Copy SSH key to new user
rsync --archive --chown=ubuntu:ubuntu ~/.ssh /home/ubuntu

# Switch to ubuntu user for all remaining steps
su - ubuntu
```

### 2.2 Update system packages

```bash
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y
```

### 2.3 Install base utilities

```bash
sudo apt install -y curl wget git build-essential htop unzip \
    ufw fail2ban nginx certbot python3-certbot-nginx python3.11 \
    python3.11-venv python3.11-dev python3-pip
```

### 2.4 Configure UFW firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw allow 8001/tcp comment 'CoinScopeAI API'
sudo ufw --force enable
sudo ufw status verbose
```

> Port 8001 is opened so the dashboard at `coinscopedash-tltanhwx.manus.space` can reach the
> engine API directly via IP. Once Nginx + SSL is configured (Phase 6), you can close 8001 and
> proxy through 443 instead.

### 2.5 Fail2ban (SSH brute-force protection)

```bash
sudo tee /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port = 22
maxretry = 5
bantime = 3600
findtime = 600
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## Phase 3 — Install Docker & Node.js

### 3.1 Docker

```bash
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sudo sh /tmp/get-docker.sh
sudo usermod -aG docker ubuntu
sudo apt install -y docker-compose-plugin

# Activate docker group without logout
newgrp docker

# Verify
docker --version
docker compose version
```

### 3.2 Node.js 22 + PM2

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

node --version   # should be v22.x
pm2 --version
```

---

## Phase 4 — Configure Swap (MANDATORY on 4 GB plan)

On the 4 GB plan, LightGBM + Redis + Docker overhead can approach the RAM ceiling under load.
4 GB of swap is the safety net that prevents OOM kills during model loading or scan spikes.

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Verify
free -h
```

---

## Phase 5 — Clone Repo & Configure Environment

### 5.1 Clone

```bash
cd /home/ubuntu
git clone https://github.com/3nz5789/coinscope-ai.git CoinScopeAI
cd CoinScopeAI
```

### 5.2 Create `.env`

```bash
# Navigate into the engine subdirectory (where .env lives)
cd coinscope_trading_engine

cat << 'EOF' > .env
# ============================================================
# CoinScopeAI — Production Environment
# ============================================================
APP_ENV=TESTNET
TZ=UTC

# ── Binance Testnet ──────────────────────────────────────────
BINANCE_TESTNET=true
BINANCE_TESTNET_API_KEY=YOUR_TESTNET_API_KEY_HERE
BINANCE_TESTNET_API_SECRET=YOUR_TESTNET_SECRET_HERE

# ── Telegram Alerts ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=7296767446

# ── Notion Integration ───────────────────────────────────────
NOTION_API_KEY=YOUR_NOTION_KEY_HERE
NOTION_SIGNAL_LOG_DB=ed9457ff-78f7-4008-bc28-ef3046506039
NOTION_TRADE_JOURNAL_DB=1430e3fb-d21b-49e7-b260-9dfa4adcb5f0
NOTION_SCAN_HISTORY_DB=c008175e-cfc0-4553-ab37-c47c3825f2e3

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_HOST=redis
REDIS_PORT=6379

# ── Security ─────────────────────────────────────────────────
SECRET_KEY=$(openssl rand -hex 32)
EOF

chmod 600 .env
cd ..
```

> **Fill in** `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_API_SECRET`, `TELEGRAM_BOT_TOKEN`,
> and `NOTION_API_KEY` before starting services.

### 5.3 Create logs directory

```bash
mkdir -p logs
```

---

## Phase 6 — Start Services via Docker Compose

The project's `docker-compose.yml` defines: Redis, FastAPI engine (port 8001), API layer,
Celery workers (default / ML / alerts / beat), Flower monitor (5555), Prometheus (9090),
and Grafana (3000).

### 6.1 Core startup (engine + API + Redis only — minimum viable)

> On the 4 GB plan, start **only core services first**. The full stack (Celery × 4, Flower,
> Prometheus, Grafana) adds ~1.5 GB RAM. Validate the engine responds before bringing the rest up.

```bash
cd /home/ubuntu/CoinScopeAI

# Start core services first — validate before adding Celery/monitoring
docker compose up -d redis api

# Watch logs for 60 seconds
docker compose logs -f api redis
```

### 6.2 Verify engine is responding

```bash
# Should return {"status":"success",...} or mock data
curl -s http://localhost:8001/health
curl -s http://localhost:8001/risk-gate
curl -s http://localhost:8001/performance
curl -s http://localhost:8001/scan
```

### 6.3 Start full stack (once core is verified)

On 4 GB, skip Grafana + Prometheus initially to conserve RAM (~400 MB saved):

```bash
# Lean full stack — Celery workers + Flower, skip monitoring
docker compose up -d redis api engine celery-default celery-ml celery-alerts celery-beat flower

# Check RAM usage — should be under 3.5 GB
free -h
docker stats --no-stream

# Only start Prometheus + Grafana if you have RAM headroom (>1 GB free)
# docker compose up -d prometheus grafana

docker compose ps   # all started services should show "healthy" or "running"
```

---

## Phase 7 — Python Venv (for standalone scripts / cron)

```bash
cd /home/ubuntu/CoinScopeAI
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify
python -c "import lightgbm; print('LightGBM OK')" 2>/dev/null || \
python -c "import ccxt; print('ccxt OK')"
deactivate
```

---

## Phase 8 — Telegram Daily Cron

```bash
crontab -e
```

Add:
```cron
# CoinScopeAI Daily Telegram Report — 00:00 UTC (03:00 Jordan)
0 0 * * * /home/ubuntu/CoinScopeAI/venv/bin/python \
    /home/ubuntu/CoinScopeAI/scripts/telegram_report.py \
    >> /home/ubuntu/CoinScopeAI/logs/cron.log 2>&1

# CoinScopeAI Daily Health Check — 00:05 UTC
5 0 * * * bash /home/ubuntu/CoinScopeAI/scripts/health_check.sh \
    http://localhost:8001 \
    >> /home/ubuntu/CoinScopeAI/logs/health.log 2>&1
```

Verify:
```bash
crontab -l
```

---

## Phase 9 — Nginx Reverse Proxy (Optional — for SSL/domain)

Skip this phase if you're accessing the API directly via IP for now.

### 9.1 Nginx config

```bash
sudo tee /etc/nginx/sites-available/coinscope << 'EOF'
# CoinScopeAI API
server {
    listen 80;
    server_name api.coinscopeai.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/coinscope /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 9.2 SSL (requires domain pointed at droplet IP)

```bash
sudo certbot --nginx \
    -d api.coinscopeai.com \
    --non-interactive --agree-tos \
    --email abu3anzeh@gmail.com

sudo certbot renew --dry-run
```

---

## Phase 10 — Connect Dashboard to Live Engine

Once the engine is up and responding on `http://YOUR_DROPLET_IP:8001`:

1. Open the primary dashboard: https://coinscopedash-tltanhwx.manus.space
2. If there's an API URL config, point it to `http://YOUR_DROPLET_IP:8001`
3. The **MOCK DATA** amber badge should disappear once live data flows

> If the dashboard URL is hardcoded to `localhost:8001`, update the frontend env var
> (`VITE_API_BASE_URL` or similar) in the React build and redeploy via Manus.

---

## Post-Deployment Verification Checklist

Run these after Phase 6 is complete:

```bash
# 1. All containers healthy
docker compose ps

# 2. API endpoints responding
curl -s http://localhost:8001/risk-gate | python3 -m json.tool
curl -s http://localhost:8001/performance | python3 -m json.tool
curl -s http://localhost:8001/scan | python3 -m json.tool
curl -s http://localhost:8001/regime/BTCUSDT | python3 -m json.tool

# 3. Redis alive
docker exec coinscopeai-redis redis-cli ping   # → PONG

# 4. Resource usage
free -h          # RAM: should have >2 GB free
df -h /          # Disk: should have >100 GB free
htop             # CPU: should be <50% at idle

# 5. Telegram bot
# Send a test message manually via curl:
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id=7296767446 \
    -d text="🟢 CoinScopeAI VPS online — $(date -u)"
```

---

## Cost Summary

| Item | 4 GB plan | 8 GB plan (if upgraded) |
|------|-----------|------------------------|
| Droplet (2 vCPU / 4 GB / 80 GB SSD) | ~$24/mo | ~$48/mo |
| Backups (20% of droplet) | ~$4.80/mo | ~$9.60/mo |
| Bandwidth (1 TB included free) | $0 | $0 |
| **Total** | **~$28.80/mo** | **~$57.60/mo** |

> Start at $28.80/mo for the 30-day validation phase. If LightGBM OOMs or performance degrades,
> resize to 8 GB — the IP, data, and config all stay intact. Hetzner was ~$20/mo but the signup
> blocker made it a non-starter.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `docker compose up` fails: permission denied | Run `newgrp docker` or log out/in |
| Port 8001 unreachable from outside | `sudo ufw allow 8001/tcp` |
| Engine OOM killed (4GB plan) | First: check `free -h` — if swap is being hit heavily, resize droplet to 8 GB via DO console. Quick fix: reduce `--concurrency=1` on celery-ml worker in docker-compose.yml |
| Redis `NOAUTH` error | Check `REDIS_URL` in `.env` has no password set (default config has none) |
| Telegram alerts not firing | Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID=7296767446` in `.env` |
| MOCK DATA badge still showing | Engine API not reachable from dashboard — check IP/port and CORS config |

---

*Generated by Scoopy · CoinScopeAI · April 15, 2026*

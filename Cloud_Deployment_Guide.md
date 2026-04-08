# CoinScopeAI — Cloud Deployment Guide

**Version:** 1.0 | **Date:** April 2026 | **Author:** Manus AI

---

This document provides a comprehensive cloud deployment recommendation and step-by-step setup guide for the CoinScopeAI crypto futures trading system. The system requires 24/7 reliability, low latency to major crypto exchanges (Binance, Bybit, OKX), and sufficient RAM to support machine learning models (LightGBM) alongside real-time data processing — all within a founder-friendly budget.

---

## Table of Contents

1. [System Requirements Analysis](#1-system-requirements-analysis)
2. [Exchange Server Locations and Latency Strategy](#2-exchange-server-locations-and-latency-strategy)
3. [Cloud Provider Comparison](#3-cloud-provider-comparison)
4. [Final Recommendation](#4-final-recommendation)
5. [Step-by-Step Deployment Guide](#5-step-by-step-deployment-guide)
   - 5.1 [Provision the Server on Hetzner](#51-provision-the-server-on-hetzner)
   - 5.2 [Initial Server Setup and Security Hardening](#52-initial-server-setup-and-security-hardening)
   - 5.3 [Install System Dependencies](#53-install-system-dependencies)
   - 5.4 [Configure Swap Space](#54-configure-swap-space)
   - 5.5 [Clone Repository and Configure Environment](#55-clone-repository-and-configure-environment)
   - 5.6 [Start Databases via Docker Compose](#56-start-databases-via-docker-compose)
   - 5.7 [Set Up Python Virtual Environment](#57-set-up-python-virtual-environment)
   - 5.8 [Install systemd Services](#58-install-systemd-services)
   - 5.9 [Build and Serve the React Dashboard](#59-build-and-serve-the-react-dashboard)
   - 5.10 [Configure the Telegram Cron Job](#510-configure-the-telegram-cron-job)
   - 5.11 [SSL and Domain Setup with Nginx](#511-ssl-and-domain-setup-with-nginx)
   - 5.12 [Monitoring and Maintenance](#512-monitoring-and-maintenance)
6. [References](#6-references)

---

## 1. System Requirements Analysis

The CoinScopeAI architecture consists of several resource-intensive components that collectively dictate the minimum hardware specifications for stable, production-grade operation.

The **FastAPI paper trading engine** is a Python process that handles API requests, runs the trading logic, and serves the `/scan`, `/performance`, `/journal`, `/risk-gate`, `/position-size`, and `/regime` endpoints. At idle it consumes roughly 200–400 MB of RAM, but this figure rises significantly when LightGBM models are loaded into memory for inference. The **WebSocket recording daemon** maintains persistent connections to Binance, Bybit, and OKX simultaneously, processing approximately 133 events per second. This is a CPU-bound task that benefits from dedicated cores and a stable, low-jitter network connection. The **React dashboard** (Vite, port 3000) is a lightweight Node.js process that serves the compiled frontend; its memory footprint is small (~100 MB), but it must be co-located with the backend to avoid cross-origin complexity. The **PostgreSQL database** and **Redis cache** are the most memory-hungry infrastructure components: PostgreSQL typically requires 500 MB to 1 GB of shared buffers for a trading workload of this scale, and Redis holds the hot market data cache in memory.

The **LightGBM models** are the deciding factor in the RAM requirement. A single trained LightGBM model for a futures market can occupy 200–800 MB of RAM depending on the number of trees and features. With multiple models loaded simultaneously (one per symbol or regime), total ML memory consumption can easily reach 2–3 GB. This is the primary reason a 4 GB instance is insufficient and an **8 GB minimum** is required.

The table below summarises the estimated memory footprint of each component:

| Component | Estimated RAM Usage |
| :--- | :--- |
| FastAPI engine (base) | 200–400 MB |
| LightGBM models (multiple) | 1,500–3,000 MB |
| WebSocket daemon | 300–500 MB |
| PostgreSQL (shared_buffers) | 500–1,000 MB |
| Redis cache | 200–500 MB |
| React/Node.js dashboard | 100–200 MB |
| OS and system processes | 300–500 MB |
| **Total (estimated)** | **3,100–6,100 MB** |

An 8 GB server provides a comfortable headroom above the estimated peak, ensuring the system does not OOM-kill critical processes during high-volatility market events when all components are under simultaneous load.

---

## 2. Exchange Server Locations and Latency Strategy

For algorithmic crypto trading, the physical distance between your server and the exchange's matching engine is the single most important infrastructure decision. Every millisecond of round-trip latency represents a potential slippage event or a missed signal.

The server locations of the three target exchanges are well-documented:

*   **Bybit** hosts its primary WebSocket and REST API infrastructure in **AWS `ap-southeast-1` (Singapore)**, specifically in availability zones `apse1-az2` and `apse1-az3` [1].
*   **OKX** also operates its primary trading infrastructure in **AWS `ap-southeast-1` (Singapore)** [2].
*   **Binance** has historically been associated with AWS Tokyo (`ap-northeast-1`), but independent latency analysis shows that Singapore-based servers also achieve excellent round-trip times to Binance, typically in the range of 5–15 ms [3]. Binance also maintains infrastructure in Singapore.

> "From the results, it's evident that the Asia region outperforms the rest... the winner was not Tokyo but Osaka. In general, Seoul sometimes showed better results than Tokyo as well." — Viktoria Tsybko, *A Latency Analysis of Binance Exchange Across AWS Regions* [3]

The practical implication is clear: **Singapore is the optimal datacenter location for this system**. It provides the best possible latency to Bybit and OKX (both on AWS Singapore), while delivering competitive latency to Binance. A server in Tokyo would improve Binance latency marginally but would increase Bybit and OKX latency significantly — a poor trade-off given that the WebSocket daemon connects to all three exchanges simultaneously.

---

## 3. Cloud Provider Comparison

The following analysis evaluates six cloud providers against the requirements: 4 vCPUs, 8 GB RAM, Singapore datacenter, 24/7 reliability, and a budget of $5–20 per month.

### Scoring Methodology

Each provider is scored on a 1–10 scale across five dimensions:

| Dimension | Weight | Rationale |
| :--- | :--- | :--- |
| Price-to-specs ratio | 30% | Budget is a primary constraint |
| Network latency to exchanges | 25% | Core performance requirement |
| Reliability and uptime | 25% | 24/7 trading cannot tolerate downtime |
| Ease of setup and maintenance | 10% | Founder-led project, minimal DevOps overhead |
| Ecosystem and support | 10% | Documentation, community, and support quality |

### Provider Profiles

**1. Hetzner Cloud — CPX32 in Singapore**

Hetzner entered the Singapore market in 2024, deploying cloud instances in the Equinix SG3 datacenter. The CPX32 plan offers 4 AMD vCPUs, 8 GB RAM, and 160 GB SSD storage. Following the April 2026 price adjustment, the plan costs approximately $18.49 per month in EUR-denominated pricing, or roughly $20 per month [4]. Hetzner includes 20 TB of outbound traffic per month — an extraordinarily generous allowance that means the WebSocket daemon's continuous data streams will never generate bandwidth overage charges. The 99.9% uptime SLA is backed by a well-regarded infrastructure operation. The primary limitation is that Hetzner's Singapore datacenter is not within the AWS network, meaning there is a small inter-datacenter hop to reach Bybit and OKX on AWS Singapore. In practice, this adds approximately 1–3 ms of latency — negligible for a strategy operating on minute or hour timeframes.

**2. Contabo — Cloud VPS 10 in Singapore**

Contabo offers the most aggressive pricing in the market: 4 vCPUs, 8 GB RAM, and 75 GB NVMe storage for approximately €3.60 per month on a 12-month term (roughly $4–5 per month) [5]. The unlimited traffic policy is a genuine advantage. However, Contabo's business model relies on heavy resource overbooking, and community reports consistently describe "noisy neighbor" effects — CPU steal time and network jitter during peak hours. For a trading system where the WebSocket daemon must process 133 events per second without interruption, unpredictable CPU performance is a meaningful risk. Contabo is an excellent choice for development and staging environments, but carries operational risk for production trading.

**3. DigitalOcean — Premium Droplet in Singapore**

DigitalOcean's Premium Droplets (SGP1 region) offer excellent network performance and a polished developer experience. However, reaching 8 GB of RAM requires the $48/month plan (4 vCPU, 8 GB, 160 GB SSD) [6], which is 2.4× the target budget. DigitalOcean's 99.99% uptime SLA and 24/7 support make it the most reliable option in this comparison, but the price premium is difficult to justify for a founder-led project when Hetzner offers equivalent specifications at less than half the cost.

**4. Vultr — Optimized Cloud Compute in Singapore**

Vultr's Singapore datacenter offers competitive latency and NVMe storage. The closest plan to the requirements is the 2 vCPU / 8 GB General Purpose instance at approximately $43 per month [7]. Vultr's High Frequency plans offer better single-core performance due to higher clock speeds, which can benefit the WebSocket event processing loop. However, the pricing gap versus Hetzner is substantial, and Vultr's Singapore network has received occasional reports of latency spikes during peak Asian market hours.

**5. AWS Lightsail — Large in Singapore**

AWS Lightsail's Large plan (2 vCPU, 8 GB RAM, 160 GB SSD) is priced at $44 per month in the Singapore region [8]. The AWS ecosystem advantage is real: a Lightsail instance in `ap-southeast-1` is physically co-located with Bybit and OKX's matching engines, which could provide a marginal latency advantage. However, Lightsail has two significant drawbacks for this use case. First, the Asia Pacific region receives only half the data transfer allowance compared to US regions — the $44 plan includes just 2.5 TB of transfer rather than 5 TB. Second, stopped instances continue to accrue charges at the full plan rate, meaning there is no cost-saving mechanism during maintenance windows. The price is also more than double the Hetzner equivalent.

**6. Oracle Cloud Free Tier — Ampere A1 in Singapore**

Oracle's Always Free tier offers the most impressive raw specifications: 4 OCPUs and 24 GB of RAM at no cost [9]. On paper, this is the perfect solution. In practice, it is entirely unsuitable for a production trading system. Oracle has a well-documented pattern of terminating free tier accounts without warning, without providing a reason, and without offering a data recovery path [10]. Community forums contain hundreds of reports of accounts terminated within days or weeks of creation, particularly for workloads that run automated scripts, maintain persistent connections, or are associated with crypto trading. The risk of losing a live trading system to an arbitrary account termination — with no recourse and no support — makes Oracle Cloud Free Tier a non-starter for any production workload.

### Comparison Summary

| Provider | Plan | Monthly Cost | RAM | Singapore | Latency Score | Reliability Score | **Weighted Score** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Hetzner** | CPX32 | ~$20 | 8 GB | Yes | 8/10 | 8/10 | **8.2/10** |
| Contabo | VPS 10 | ~$5 | 8 GB | Yes | 7/10 | 5/10 | **6.1/10** |
| DigitalOcean | Premium 8GB | $48 | 8 GB | Yes | 9/10 | 9/10 | **7.4/10** |
| Vultr | GP 8GB | ~$43 | 8 GB | Yes | 8/10 | 8/10 | **6.8/10** |
| AWS Lightsail | Large | $44 | 8 GB | Yes | 9/10 | 9/10 | **7.0/10** |
| Oracle Free | ARM A1 | $0 | 24 GB | Yes | 9/10 | 1/10 | **4.5/10** |

*Note: Weighted score incorporates the price-to-specs ratio dimension, which heavily penalises providers above the $20 budget target.*

---

## 4. Final Recommendation

### Primary Recommendation: Hetzner CPX32 in Singapore (~$20/month)

Hetzner is the clear winner for this use case. It is the only provider that simultaneously satisfies all three hard requirements: 8 GB of RAM, a Singapore datacenter, and a monthly cost within the $5–20 budget. The 20 TB traffic allowance eliminates any concern about bandwidth costs from the WebSocket daemon's continuous data streams. The AMD EPYC processors in the CPX32 deliver consistent, predictable performance without the CPU steal time that plagues budget providers like Contabo.

The Equinix SG3 datacenter where Hetzner Singapore is hosted is one of the premier carrier-neutral facilities in Southeast Asia, with direct peering to AWS, Google Cloud, and major regional ISPs. This means the 1–3 ms inter-datacenter hop to Bybit and OKX on AWS Singapore is a fixed, stable overhead — not a variable that fluctuates with internet routing.

### Budget Alternative: Contabo Cloud VPS 10 in Singapore (~$5/month)

If the $20 monthly cost is genuinely prohibitive, Contabo's Cloud VPS 10 is the only other provider that meets the RAM requirement within a tight budget. The trade-off is accepting variable CPU performance and occasional network jitter. For a paper trading system (as opposed to live execution), this trade-off may be acceptable — missed WebSocket events affect the quality of the recorded dataset but do not result in financial loss. For live trading, the Hetzner recommendation stands firmly.

### When to Consider DigitalOcean or AWS Lightsail

These providers become the right choice when the project scales beyond the founder stage and reliability guarantees become more important than cost. DigitalOcean's 99.99% SLA and 24/7 support, or AWS Lightsail's intra-network proximity to exchange infrastructure, justify the premium for a fund or institutional deployment.

---

## 5. Step-by-Step Deployment Guide

This guide covers the complete deployment of CoinScopeAI on a freshly provisioned Hetzner CPX32 instance running Ubuntu 22.04 LTS in Singapore. All commands are intended to be run as the `ubuntu` user with `sudo` privileges.

---

### 5.1 Provision the Server on Hetzner

1. Log in to the [Hetzner Cloud Console](https://console.hetzner.cloud/).
2. Click **New Project** and name it `CoinScopeAI`.
3. Click **Add Server** and configure as follows:

| Setting | Value |
| :--- | :--- |
| Location | Singapore (SIN) |
| Image | Ubuntu 22.04 |
| Type | Shared vCPU → AMD → **CPX32** |
| Networking | Enable both IPv4 and IPv6 |
| SSH Keys | Upload your public key |
| Backups | Enable (adds ~20% to monthly cost, recommended) |

4. Click **Create & Buy Now**. The server will be provisioned in under 30 seconds.
5. Note the server's public IPv4 address from the dashboard.

---

### 5.2 Initial Server Setup and Security Hardening

Connect to the server and perform the initial security configuration.

```bash
# Connect via SSH
ssh ubuntu@YOUR_SERVER_IP

# Update all system packages
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y

# Install essential utilities
sudo apt install -y curl wget git build-essential htop unzip \
    ufw fail2ban nginx certbot python3-certbot-nginx

# Configure the UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw --force enable

# Verify firewall status
sudo ufw status verbose
```

Configure `fail2ban` to automatically block brute-force SSH attempts:

```bash
# Create a local jail configuration
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

Configure automatic security updates to keep the system patched without manual intervention:

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

### 5.3 Install System Dependencies

Install Docker, Docker Compose, Python 3.11, and Node.js 22.

```bash
# --- Docker ---
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sudo sh /tmp/get-docker.sh

# Add the ubuntu user to the docker group
sudo usermod -aG docker ubuntu

# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Verify Docker installation
docker --version
docker compose version

# --- Python 3.11 ---
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# --- Node.js 22 (LTS) ---
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Verify Node installation
node --version
npm --version

# Install PM2 globally for process management
sudo npm install -g pm2
```

> **Important:** Log out and back in after adding yourself to the `docker` group, or run `newgrp docker` in the current session, to activate the group membership without a full re-login.

---

### 5.4 Configure Swap Space

Even with 8 GB of RAM, configuring a swap file provides a safety net against OOM kills during unexpected memory spikes (e.g., when LightGBM reloads models after a signal). This is especially important on a VPS where there is no physical swap partition.

```bash
# Create a 4 GB swap file
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap permanent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Tune swappiness (lower value = prefer RAM over swap)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Verify swap is active
free -h
```

---

### 5.5 Clone Repository and Configure Environment

```bash
# Clone the CoinScopeAI repository
cd /home/ubuntu
git clone https://github.com/YOUR_USERNAME/CoinScopeAI.git
cd CoinScopeAI

# Create the production environment file
cat << 'EOF' > .env
# ============================================================
# CoinScopeAI Production Environment Configuration
# ============================================================
APP_ENV=PROD
TZ=UTC

# Service URLs (internal)
COINSCOPEAI_BASE_URL=http://localhost:8001

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# OpenAI / LLM Integration
OPENAI_API_KEY=your_openai_api_key_here

# Database
DATABASE_URL=postgresql://coinscope:CHANGE_THIS_PASSWORD@localhost:5432/coinscope

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=generate_a_random_64_char_string_here
EOF

# Secure the .env file — only the owner can read it
chmod 600 .env

# Create the logs directory
mkdir -p logs
```

> **Security Note:** Replace all placeholder values before starting any services. Generate a strong `SECRET_KEY` using `openssl rand -hex 32`.

---

### 5.6 Start Databases via Docker Compose

Create a `docker-compose.yml` file that defines the PostgreSQL and Redis services. If the repository already contains one, review it to ensure the configuration matches the environment variables above.

```yaml
# docker-compose.yml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    container_name: coinscope_postgres
    restart: always
    environment:
      POSTGRES_USER: coinscope
      POSTGRES_PASSWORD: CHANGE_THIS_PASSWORD
      POSTGRES_DB: coinscope
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U coinscope"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: coinscope_redis
    restart: always
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

Start the database services:

```bash
# Start PostgreSQL and Redis in detached mode
docker compose up -d

# Verify both containers are healthy
docker compose ps

# Check logs if a container fails to start
docker compose logs postgres
docker compose logs redis
```

---

### 5.7 Set Up Python Virtual Environment

```bash
cd /home/ubuntu/CoinScopeAI

# Create the virtual environment using Python 3.11
python3.11 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip and install all dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify LightGBM installed correctly
python -c "import lightgbm; print('LightGBM version:', lightgbm.__version__)"

# Deactivate the virtual environment
deactivate
```

---

### 5.8 Install systemd Services

Using systemd ensures that the FastAPI engine and WebSocket daemon start automatically on server boot, restart immediately after any crash, and integrate with the system's logging infrastructure.

**Create the FastAPI Engine Service**

```bash
sudo tee /etc/systemd/system/coinscope-api.service << 'EOF'
[Unit]
Description=CoinScopeAI FastAPI Trading Engine
Documentation=https://github.com/YOUR_USERNAME/CoinScopeAI
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/CoinScopeAI
EnvironmentFile=/home/ubuntu/CoinScopeAI/.env
ExecStart=/home/ubuntu/CoinScopeAI/venv/bin/uvicorn main:app \
    --host 127.0.0.1 \
    --port 8001 \
    --workers 2 \
    --log-level info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=coinscope-api

# Resource limits
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
```

**Create the WebSocket Daemon Service**

```bash
sudo tee /etc/systemd/system/coinscope-ws.service << 'EOF'
[Unit]
Description=CoinScopeAI WebSocket Recording Daemon
Documentation=https://github.com/YOUR_USERNAME/CoinScopeAI
After=network-online.target coinscope-api.service
Wants=network-online.target
Requires=coinscope-api.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/CoinScopeAI
EnvironmentFile=/home/ubuntu/CoinScopeAI/.env
ExecStart=/home/ubuntu/CoinScopeAI/venv/bin/python ws_daemon.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=coinscope-ws

# Resource limits
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
```

**Enable and Start Both Services**

```bash
# Reload systemd to recognise the new unit files
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable coinscope-api coinscope-ws

# Start the services
sudo systemctl start coinscope-api
sudo systemctl start coinscope-ws

# Verify both services are running
sudo systemctl status coinscope-api
sudo systemctl status coinscope-ws

# Follow live logs for the API
journalctl -u coinscope-api -f
```

---

### 5.9 Build and Serve the React Dashboard

```bash
# Navigate to the frontend directory
cd /home/ubuntu/CoinScopeAI/frontend

# Install Node dependencies
npm install

# Build the production bundle
npm run build

# Return to the project root
cd /home/ubuntu/CoinScopeAI

# Start the dashboard with PM2 (serves the Vite preview on port 3000)
pm2 start npm --name "coinscope-dashboard" -- run preview -- \
    --port 3000 \
    --host 127.0.0.1

# Save the PM2 process list so it persists across reboots
pm2 save

# Configure PM2 to start on system boot
pm2 startup
# Run the command that PM2 outputs (it will look like: sudo env PATH=... pm2 startup ...)
```

---

### 5.10 Configure the Telegram Cron Job

The daily Telegram status report is managed by a cron job running as the `ubuntu` user.

```bash
# Create the logs directory if it doesn't exist
mkdir -p /home/ubuntu/CoinScopeAI/logs

# Open the crontab editor
crontab -e
```

Add the following line to run the report script every day at 00:00 UTC:

```cron
# CoinScopeAI Daily Telegram Status Report
0 0 * * * /home/ubuntu/CoinScopeAI/venv/bin/python \
    /home/ubuntu/CoinScopeAI/scripts/telegram_report.py \
    >> /home/ubuntu/CoinScopeAI/logs/cron.log 2>&1
```

Verify the cron job is registered:

```bash
crontab -l
```

---

### 5.11 SSL and Domain Setup with Nginx

This step is optional but strongly recommended if the dashboard is accessed over the public internet. It requires a domain name pointed at the server's IP address.

**Configure DNS Records**

In your DNS provider's control panel, create two A records:

| Record | Value |
| :--- | :--- |
| `dashboard.yourdomain.com` | `YOUR_SERVER_IP` |
| `api.yourdomain.com` | `YOUR_SERVER_IP` |

Wait for DNS propagation (typically 5–30 minutes) before proceeding.

**Create the Nginx Configuration**

```bash
sudo tee /etc/nginx/sites-available/coinscope << 'EOF'
# CoinScopeAI Dashboard
server {
    listen 80;
    server_name dashboard.yourdomain.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}

# CoinScopeAI API
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/coinscope /etc/nginx/sites-enabled/

# Test the Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

**Obtain Let's Encrypt SSL Certificates**

```bash
# Obtain and install SSL certificates for both subdomains
sudo certbot --nginx \
    -d dashboard.yourdomain.com \
    -d api.yourdomain.com \
    --non-interactive \
    --agree-tos \
    --email your@email.com

# Verify automatic renewal is configured
sudo certbot renew --dry-run
```

Certbot automatically modifies the Nginx configuration to redirect HTTP to HTTPS and installs a systemd timer for automatic certificate renewal every 60 days.

---

### 5.12 Monitoring and Maintenance

**Service Health Checks**

The following commands are the primary tools for day-to-day monitoring:

```bash
# Check the status of all CoinScopeAI services
sudo systemctl status coinscope-api coinscope-ws
pm2 status
docker compose ps

# Follow live logs for each component
journalctl -u coinscope-api -f          # FastAPI engine
journalctl -u coinscope-ws -f           # WebSocket daemon
docker compose logs -f postgres          # PostgreSQL
docker compose logs -f redis             # Redis
pm2 logs coinscope-dashboard             # React dashboard
```

**System Resource Monitoring**

Install `netdata` for a real-time, web-based system dashboard:

```bash
bash <(curl -Ss https://my-netdata.io/kickstart.sh) --dont-wait

# Netdata runs on port 19999 by default
# Add a firewall rule to access it (restrict to your IP for security)
sudo ufw allow from YOUR_HOME_IP to any port 19999
```

**PostgreSQL Backup**

Create a daily automated backup of the PostgreSQL database:

```bash
# Create a backup directory
mkdir -p /home/ubuntu/backups/postgres

# Add a daily backup cron job (runs at 01:00 UTC)
crontab -e
```

Add the following cron entry:

```cron
# Daily PostgreSQL backup
0 1 * * * docker exec coinscope_postgres pg_dump -U coinscope coinscope \
    | gzip > /home/ubuntu/backups/postgres/coinscope_$(date +\%Y\%m\%d).sql.gz \
    && find /home/ubuntu/backups/postgres -name "*.sql.gz" -mtime +7 -delete
```

This creates a compressed daily backup and automatically deletes backups older than 7 days to manage disk space.

**Updating the Application**

```bash
cd /home/ubuntu/CoinScopeAI

# Pull the latest code
git pull origin main

# Activate the virtual environment and update dependencies
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Rebuild the frontend if it changed
cd frontend && npm install && npm run build && cd ..

# Restart the backend services
sudo systemctl restart coinscope-api coinscope-ws

# Reload the dashboard
pm2 reload coinscope-dashboard
```

**Maintenance Checklist (Monthly)**

The following tasks should be performed on a monthly basis to keep the system healthy:

| Task | Command |
| :--- | :--- |
| Update system packages | `sudo apt update && sudo apt upgrade -y` |
| Check disk usage | `df -h` and `du -sh /home/ubuntu/CoinScopeAI/logs/*` |
| Review fail2ban bans | `sudo fail2ban-client status sshd` |
| Verify SSL certificate expiry | `sudo certbot certificates` |
| Check Docker image updates | `docker compose pull && docker compose up -d` |
| Review PostgreSQL backup integrity | `ls -lh /home/ubuntu/backups/postgres/` |
| Check swap usage trends | `free -h` and `vmstat -s` |

---

## 6. References

[1] Bybit API Documentation. "Frequently Asked Questions: Where are Bybit's servers located?" Available at: https://bybit-exchange.github.io/docs/faq

[2] Laostjen. "High-Frequency Trading in Crypto: Latency, Infrastructure, and Reality." *Medium*, December 14, 2025. Available at: https://medium.com/@laostjen/high-frequency-trading-in-crypto-latency-infrastructure-and-reality-594e994132fd

[3] Tsybko, Viktoria. "A Latency Analysis of Binance Exchange Across AWS Regions." *Substack*, October 5, 2023. Available at: https://viktoriatsybko.substack.com/p/an-analysis-of-binance-exchange-across

[4] Hetzner Online GmbH. "Hetzner Price Adjustment." *Hetzner Docs*, last updated February 25, 2026. Available at: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/

[5] Contabo GmbH. "Affordable Singapore VPS Hosting." Available at: https://contabo.com/en/vps-singapore/

[6] DigitalOcean, Inc. "Droplet Pricing." Available at: https://www.digitalocean.com/pricing/droplets

[7] Vultr Holdings LLC. "Cloud Compute Pricing." Available at: https://www.vultr.com/pricing/

[8] Hinman, Danny. "Amazon Lightsail Pricing: 2026 Guide to True Total Cost." *Cloud Burn*, April 7, 2026. Available at: https://cloudburn.io/blog/amazon-lightsail-pricing

[9] Oracle Corporation. "Oracle Cloud Free Tier." Available at: https://www.oracle.com/cloud/free/

[10] Reddit community. "Oracle terminated by account, no notice." *r/oraclecloud*, March 22, 2025. Available at: https://www.reddit.com/r/oraclecloud/comments/1jgt313/oracle_terminated_by_account_no_notice/

---

*This document was prepared by Manus AI on April 8, 2026. Pricing figures reflect publicly available information as of that date and are subject to change. Always verify current pricing on the provider's official website before provisioning.*

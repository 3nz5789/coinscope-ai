# CoinScopeAI: systemd Production Deployment Guide

This directory contains production-grade systemd service files and an automated installer for the CoinScopeAI trading stack. These services are designed to ensure high availability, automatic recovery, and security hardening for the core engine, recording daemon, and production dashboard.

---

## 1. Service Overview

| Service | Port | Description |
| :--- | :--- | :--- |
| `coinscopeai-engine.service` | 8001 | Core FastAPI paper-trading engine. |
| `coinscopeai-recorder.service` | N/A | WebSocket market data ingestion daemon. |
| `coinscopeai-dashboard.service` | 3000 | Production React/Vite dashboard. |

---

## 2. Installation

### Prerequisites

1.  **Environment File:** Ensure `/home/ubuntu/coinscope.env` exists and contains the required API keys and configuration. See `coinscope.env.example` in the repository root for a template.
2.  **Dependencies:** Ensure `python3`, `npm`, and `npx` are installed on the system.

### Automated Install

The `install.sh` script handles copying the service files to `/etc/systemd/system`, reloading the daemon, and enabling the services to start on boot.

```bash
cd deploy/systemd/
chmod +x install.sh
sudo ./install.sh --start
```

---

## 3. Management

A `Makefile` is provided for convenient management of the services.

| Command | Action |
| :--- | :--- |
| `make status` | Show the current status of all three services. |
| `make start` | Start all services in the correct dependency order. |
| `make stop` | Stop all services. |
| `make restart` | Restart all services. |
| `make logs` | Tail the combined logs from all services via `journalctl`. |
| `make uninstall` | Stop, disable, and remove all service files. |

---

## 4. Security & Hardening

Each service file is configured with modern systemd security features:

*   **`NoNewPrivileges=yes`**: Prevents the service and its children from gaining new privileges via `execve()`.
*   **`ProtectSystem=strict`**: Mounts the entire file system as read-only for the service, except for specified `ReadWritePaths`.
*   **`PrivateTmp=yes`**: Provides a private `/tmp` and `/var/tmp` directory for the service.
*   **`OOMScoreAdjust`**: Prioritizes the engine (`-500`) to ensure it is the last process killed under memory pressure, while the dashboard (`200`) is the first.
*   **`Restart=on-failure`**: Automatically restarts the service with a backoff if it crashes.
*   **`WatchdogSec=30s`**: (Engine only) systemd will restart the engine if it becomes unresponsive and fails to ping the watchdog.

---

## 5. Troubleshooting

If a service fails to start, check the logs for specific error messages:

```bash
# View logs for a specific service
sudo journalctl -u coinscopeai-engine -n 50 --no-pager

# Check for environment file issues
ls -l /home/ubuntu/coinscope.env
```

Ensure that the `WorkingDirectory` and `ExecStart` paths in the `.service` files match your actual installation paths if they differ from the default `/home/ubuntu/coinscope-ai`.

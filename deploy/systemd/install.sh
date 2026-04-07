#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  CoinScopeAI — systemd Service Installer
#  Usage:
#    ./install.sh              # Install and enable services (no auto-start)
#    ./install.sh --start      # Install, enable, and start all services
#    ./install.sh --dry-run    # Preview actions without making any changes
#    ./install.sh --uninstall  # Stop, disable, and remove all service files
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"
ENV_FILE="/home/ubuntu/coinscope.env"

SERVICES=(
    "coinscopeai-engine.service"
    "coinscopeai-recorder.service"
    "coinscopeai-dashboard.service"
)

# ── Argument parsing ──────────────────────────────────────────────────────────
DRY_RUN=false
AUTO_START=false
UNINSTALL=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)   DRY_RUN=true ;;
        --start)     AUTO_START=true ;;
        --uninstall) UNINSTALL=true ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--start] [--dry-run] [--uninstall]"
            exit 1
            ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
run() {
    if $DRY_RUN; then
        echo "[DRY-RUN] $*"
    else
        echo "[RUN] $*"
        "$@"
    fi
}

info()  { echo -e "\033[36m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[32m[ OK ]\033[0m  $*"; }
warn()  { echo -e "\033[33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[31m[ERR ]\033[0m  $*" >&2; }

# ── Preflight checks ──────────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]] && ! $DRY_RUN; then
    error "This script must be run as root (or with sudo) unless --dry-run is specified."
    exit 1
fi

if ! command -v systemctl &>/dev/null; then
    error "systemd is not available on this system."
    exit 1
fi

# ── Uninstall path ────────────────────────────────────────────────────────────
if $UNINSTALL; then
    info "Uninstalling CoinScopeAI systemd services..."
    for svc in "${SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            run systemctl stop "$svc"
        fi
        if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
            run systemctl disable "$svc"
        fi
        if [[ -f "${SYSTEMD_DIR}/${svc}" ]]; then
            run rm -f "${SYSTEMD_DIR}/${svc}"
            ok "Removed ${SYSTEMD_DIR}/${svc}"
        fi
    done
    run systemctl daemon-reload
    ok "Uninstall complete."
    exit 0
fi

# ── Install path ──────────────────────────────────────────────────────────────
info "Installing CoinScopeAI systemd services..."
$DRY_RUN && warn "DRY-RUN mode — no changes will be made."

# Validate environment file
if [[ ! -f "$ENV_FILE" ]]; then
    warn "Environment file not found: $ENV_FILE"
    warn "Services will fail to start until it is created."
    warn "See coinscope.env.example for the required variables."
fi

# Copy service files
for svc in "${SERVICES[@]}"; do
    src="${SCRIPT_DIR}/${svc}"
    dst="${SYSTEMD_DIR}/${svc}"
    if [[ ! -f "$src" ]]; then
        error "Service file not found: $src"
        exit 1
    fi
    run install -m 644 "$src" "$dst"
    ok "Installed $dst"
done

# Reload systemd and enable services
run systemctl daemon-reload
for svc in "${SERVICES[@]}"; do
    run systemctl enable "$svc"
    ok "Enabled $svc"
done

# Optionally start services
if $AUTO_START; then
    info "Starting services in dependency order..."
    # Engine first, then recorder and dashboard
    run systemctl start coinscopeai-engine.service
    ok "Started coinscopeai-engine.service"
    sleep 5
    run systemctl start coinscopeai-recorder.service
    ok "Started coinscopeai-recorder.service"
    run systemctl start coinscopeai-dashboard.service
    ok "Started coinscopeai-dashboard.service"
    echo ""
    info "Service status:"
    for svc in "${SERVICES[@]}"; do
        $DRY_RUN || systemctl status "$svc" --no-pager --lines=3 || true
    done
else
    info "Services installed and enabled but NOT started."
    info "To start all services, run:  sudo systemctl start coinscopeai-engine coinscopeai-recorder coinscopeai-dashboard"
    info "Or re-run this script with:  sudo ./install.sh --start"
fi

echo ""
ok "Installation complete."

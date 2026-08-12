#!/usr/bin/env bash
# =============================================================================
# scripts/install_service.sh
# One-command installer for the Swine Health Monitor systemd service.
#
# Run this ONCE on the Raspberry Pi after copying the project files:
#   chmod +x scripts/install_service.sh
#   sudo ./scripts/install_service.sh
#
# What it does:
#   1. Verifies prerequisites (venv, model file)
#   2. Copies swine-monitor.service to /etc/systemd/system/
#   3. Enables + starts the service
#   4. Prints status and log tail
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Must run as root ──────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "This script must be run as root: sudo $0"

# ── Locate project root (script lives in scripts/) ────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_SRC="$SCRIPT_DIR/swine-monitor.service"
SERVICE_DEST="/etc/systemd/system/swine-monitor.service"
SERVICE_NAME="swine-monitor"

info "Project root: $PROJECT_ROOT"

# ── Detect running user (the non-root user who owns the project) ──────────────
# Prefer SUDO_USER if available, else default to pi
PROJECT_USER="${SUDO_USER:-pi}"
info "Service will run as user: $PROJECT_USER"

# ── Prerequisite checks ───────────────────────────────────────────────────────
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"
if [[ ! -f "$VENV_PYTHON" ]]; then
    warn "Virtual environment not found at $VENV_PYTHON"
    warn "Create it first:  python3 -m venv $PROJECT_ROOT/.venv"
    warn "                  $PROJECT_ROOT/.venv/bin/pip install -r $PROJECT_ROOT/requirements-pi.txt"
    error "Aborting — venv required before installing service."
fi
info "Virtual environment: OK"

MODEL_PATH="$PROJECT_ROOT/models/best.onnx"
if [[ ! -f "$MODEL_PATH" ]]; then
    warn "ONNX model not found at $MODEL_PATH"
    warn "Copy it from your training PC:  scp models/best.onnx pi@<PI_IP>:~/Pig_Tracking/models/"
    error "Aborting — model file required for the service to start."
fi
info "ONNX model: OK"

# ── Patch service file with correct paths and user ───────────────────────────
info "Generating service file for user='$PROJECT_USER', root='$PROJECT_ROOT'..."

cat > "$SERVICE_DEST" <<EOF
[Unit]
Description=Swine Health Monitor — Offline AI Pig Health Monitoring System
Documentation=file://$PROJECT_ROOT/README.md
After=network.target
Wants=network.target

[Service]
Type=simple
User=$PROJECT_USER
Group=$PROJECT_USER
WorkingDirectory=$PROJECT_ROOT
ExecStart=$VENV_PYTHON src/main.py
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=120
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=swine-monitor
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF

info "Service file written to $SERVICE_DEST"

# ── Enable and start ──────────────────────────────────────────────────────────
systemctl daemon-reload
info "systemd daemon reloaded."

systemctl enable "$SERVICE_NAME"
info "Service enabled (will start on every boot)."

systemctl restart "$SERVICE_NAME"
info "Service started."

sleep 2  # Brief pause for service to initialize

echo ""
echo "─────────────────────────────────────────────"
systemctl status "$SERVICE_NAME" --no-pager --lines=5 || true
echo "─────────────────────────────────────────────"
echo ""
info "Installation complete!"
echo ""
echo -e "  ${GREEN}View live logs:${NC}   journalctl -u $SERVICE_NAME -f"
echo -e "  ${GREEN}Stop service:${NC}     sudo systemctl stop $SERVICE_NAME"
echo -e "  ${GREEN}Disable autostart:${NC} sudo systemctl disable $SERVICE_NAME"
echo ""

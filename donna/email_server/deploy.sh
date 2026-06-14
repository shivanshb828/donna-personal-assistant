#!/usr/bin/env bash
# Donna Email Server — deploy on Dell GBIO (GB10 Grace Blackwell)
#
# Run AFTER M2's deploy.sh has already been executed (venv exists at /gbio/donna/.venv).
# Usage:
#   bash donna/email_server/deploy.sh
#
# What this does:
#   1. Installs email server Python deps into the shared venv
#   2. Creates required directories
#   3. Copies .env.example → .env (if .env does not exist yet)
#   4. Installs a systemd service for auto-start on boot
#   5. Runs the test suite to verify everything is wired up
#   6. Starts the service

set -euo pipefail

DONNA_DIR="/gbio/donna"
VENV="$DONNA_DIR/.venv"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EMAIL_DIR="$REPO_ROOT/donna/email_server"
SERVICE_NAME="donna-email"

# ── colour helpers ────────────────────────────────────────────────────────────
green() { echo -e "\033[0;32m$*\033[0m"; }
yellow() { echo -e "\033[0;33m$*\033[0m"; }
red() { echo -e "\033[0;31m$*\033[0m"; }

# ── preflight ─────────────────────────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
  red "ERROR: $VENV not found."
  echo "Run M2's deploy.sh first: bash deploy.sh"
  exit 1
fi

green "==> [1/6] Installing email server dependencies into shared venv..."
source "$VENV/bin/activate"
pip install --quiet -r "$REPO_ROOT/donna/requirements.txt"

green "==> [2/6] Creating document storage directories..."
mkdir -p "$DONNA_DIR/documents"
mkdir -p "$DONNA_DIR/documents/unmatched"

green "==> [3/6] Setting up .env..."
ENV_FILE="$DONNA_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$REPO_ROOT/donna/.env.example" "$ENV_FILE"
  yellow "    Created $ENV_FILE from .env.example."
  yellow "    IMPORTANT: Edit $ENV_FILE and fill in real values before starting."
  yellow "    Especially: DONNA_EMAIL_USER, DONNA_EMAIL_PASS, DONNA_SESSION_ROUTER_URL"
else
  echo "    $ENV_FILE already exists — skipping (not overwriting)."
fi

green "==> [4/6] Installing systemd service..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Detect mode from .env or default to smtp
EMAIL_MODE=$(grep -E "^DONNA_EMAIL_MODE=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "smtp")
EMAIL_MODE="${EMAIL_MODE:-smtp}"

cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=Donna Email Inbound Server (${EMAIL_MODE} mode)
After=network.target openclaw.service

[Service]
Type=simple
User=donna
WorkingDirectory=$DONNA_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python -m donna.email_server.server --mode ${EMAIL_MODE}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=donna-email

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/${SERVICE_NAME}.service "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

green "==> [5/6] Running test suite..."
cd "$REPO_ROOT"
python -m pytest donna/email_server/tests/ -q --tb=short
echo ""

green "==> [6/6] Starting donna-email service..."
sudo systemctl restart "$SERVICE_NAME"
sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
green "✓ Donna email server deployed."
echo "   Mode      : $EMAIL_MODE"
echo "   Logs      : journalctl -u $SERVICE_NAME -f"
echo "   Status    : systemctl status $SERVICE_NAME"
echo "   Stop      : systemctl stop $SERVICE_NAME"
echo ""
if [[ "$EMAIL_MODE" == "smtp" ]]; then
  echo "   SMTP listener on localhost:1025"
  echo "   Point your mail relay / MX forward at port 1025 on this machine."
else
  echo "   IMAP polling ${EMAIL_MODE} every 30s"
  echo "   Polling: $(grep DONNA_EMAIL_USER "$ENV_FILE" | cut -d= -f2)"
fi

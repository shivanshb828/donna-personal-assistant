#!/usr/bin/env bash
# Start full Donna dashboard stack on Dell GB10.
# Usage: bash scripts/run_dashboard_stack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.venv"
LOG_DIR="${ROOT}/.context/logs"
mkdir -p "$LOG_DIR" /gbio/donna/drafts /gbio/donna/sent /gbio/donna/documents 2>/dev/null || true

if [[ ! -d "$VENV" ]]; then
  echo "Missing .venv — run: bash scripts/setup_venv.sh"
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js required for dashboard — install Node 18+"
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
cd "$ROOT"

export PYTHONPATH="$ROOT"
export DONNA_DRAFTS_DIR="${DONNA_DRAFTS_DIR:-/gbio/donna/drafts}"
export DONNA_SENT_DIR="${DONNA_SENT_DIR:-/gbio/donna/sent}"
export DONNA_ATTACHMENT_DIR="${DONNA_ATTACHMENT_DIR:-/gbio/donna/documents}"
export DONNA_DASHBOARD_BIND="${DONNA_DASHBOARD_BIND:-0.0.0.0}"

if [[ ! -f data/donna_m3_context.sqlite ]]; then
  echo "→ Seeding M3 SQLite databases…"
  python3 scripts/init_m3_test_db.py
fi

if [[ ! -f data/donna_telephony.sqlite ]]; then
  echo "→ Initializing telephony SQLite…"
  python3 -c "from donna.telephony.db import init_telephony_db; from pathlib import Path; init_telephony_db(Path('data/donna_telephony.sqlite'))"
fi

free_port() {
  local port="$1"
  local pid
  pid="$(ss -tlnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p { if (match($0, /pid=([0-9]+)/, m)) print m[1] }' | head -1)"
  if [[ -z "$pid" ]] && command -v lsof >/dev/null 2>&1; then
    pid="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  fi
  if [[ -n "$pid" ]]; then
    echo "→ Freeing port $port (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
}

start_bg() {
  local name="$1"
  shift
  echo "→ Starting $name…"
  nohup "$@" >"${LOG_DIR}/${name}.log" 2>&1 &
  echo "$!" > "${LOG_DIR}/${name}.pid"
}

free_port 3001
free_port 3002
free_port 8000
free_port 7777

start_bg "ws-relay" python -m donna.integration.dashboard_events
start_bg "ipc" python -m uvicorn donna.ipc.server:app --host 0.0.0.0 --port 8000
start_bg "telephony" python -m uvicorn donna.telephony.server:app --host 0.0.0.0 --port 3002

sleep 3

if ! curl -sf http://127.0.0.1:3002/health >/dev/null; then
  echo "✗ Telephony API failed — see ${LOG_DIR}/telephony.log"
  tail -30 "${LOG_DIR}/telephony.log" || true
  exit 1
fi

echo "→ Starting React dashboard on port 7777"
cd "${ROOT}/dashboard"
if [[ ! -d node_modules ]]; then
  npm install --silent
fi

DELL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
export VITE_WS_URL="ws://${DELL_IP:-localhost}:3001"
nohup npm run dev -- --host 0.0.0.0 --port 7777 >"${LOG_DIR}/dashboard.log" 2>&1 &
echo "$!" > "${LOG_DIR}/dashboard.pid"

sleep 3

cat <<EOF

Donna dashboard stack is running on Dell GB10:

  Dashboard UI   http://${DELL_IP:-localhost}:7777
  WebSocket      ws://${DELL_IP:-localhost}:3001
  Telephony API  http://${DELL_IP:-localhost}:3002
  IPC server     http://${DELL_IP:-localhost}:8000

Logs: ${LOG_DIR}/

Live voice (push-to-talk):
  bash scripts/run_voice.sh

Stop:
  bash scripts/stop_dashboard_stack.sh
EOF

#!/usr/bin/env bash
# start.sh — Boot the full Donna stack for demo.
#
# Starts (in order):
#   1. WS relay hub       :3001  (donna/integration/dashboard_events.py)
#   2. Telephony server   :3002  (donna/telephony/server.py via uvicorn)
#   3. React dashboard    :5173  (dashboard/ via npm)
#
# Voice push-to-talk: run separately in a 4th terminal:
#   bash scripts/run_voice.sh
#
# Twilio phone demo: set PUBLIC_URL + Twilio vars in .env first, then:
#   ngrok http 3002   (in a separate terminal)
#   Update PUBLIC_URL in .env to the ngrok URL, then re-run this script.
#
# Usage:
#   cd ~/dell-hack
#   bash scripts/start.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"
DASHBOARD_DIR="${ROOT}/dashboard"
LOG_DIR="${ROOT}/logs"

# ── Preflight ─────────────────────────────────────────────────────────────────

if [[ ! -d "${VENV}" ]]; then
  echo "ERROR: .venv not found. Run first: bash scripts/setup_venv.sh"
  exit 1
fi

if [[ ! -f "${ROOT}/donna/.env" ]]; then
  echo "WARN: donna/.env not found. Copy donna/.env.example → donna/.env and fill in values."
  echo "      Continuing with defaults (localhost ports, no Twilio)."
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "WARN: npm not found — React dashboard will not start."
  SKIP_DASHBOARD=1
else
  SKIP_DASHBOARD=0
fi

mkdir -p "${LOG_DIR}"

# ── Activate venv ─────────────────────────────────────────────────────────────

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
cd "${ROOT}"

# ── Init databases ────────────────────────────────────────────────────────────

echo "[1/5] Initializing SQLite databases..."
python3 scripts/init_m3_test_db.py
echo "      OK — data/donna_m3_context.sqlite + data/donna_m3_calendar.sqlite"

# ── Start WS relay hub ────────────────────────────────────────────────────────

echo "[2/5] Starting WebSocket relay hub on :3001..."
python -m donna.integration.dashboard_events > "${LOG_DIR}/ws_hub.log" 2>&1 &
WS_HUB_PID=$!
echo "      PID ${WS_HUB_PID} — logs: logs/ws_hub.log"
sleep 1

# ── Start telephony server ────────────────────────────────────────────────────

echo "[3/5] Starting telephony server on :3002..."
DONNA_TELEPHONY_PORT="${DONNA_TELEPHONY_PORT:-3002}"
python -m uvicorn donna.telephony.server:app \
  --host 0.0.0.0 \
  --port "${DONNA_TELEPHONY_PORT}" \
  > "${LOG_DIR}/telephony.log" 2>&1 &
TELEPHONY_PID=$!
echo "      PID ${TELEPHONY_PID} — logs: logs/telephony.log"
sleep 2

# ── Start React dashboard ─────────────────────────────────────────────────────

if [[ "${SKIP_DASHBOARD}" -eq 0 ]]; then
  echo "[4/5] Starting React dashboard on :5173..."
  if [[ ! -d "${DASHBOARD_DIR}/node_modules" ]]; then
    echo "      Installing npm dependencies..."
    npm --prefix "${DASHBOARD_DIR}" install --silent
  fi
  VITE_API_URL="http://localhost:${DONNA_TELEPHONY_PORT}" \
  VITE_WS_URL="ws://localhost:3001" \
  npm --prefix "${DASHBOARD_DIR}" run dev -- --port 5173 \
    > "${LOG_DIR}/dashboard.log" 2>&1 &
  DASHBOARD_PID=$!
  echo "      PID ${DASHBOARD_PID} — logs: logs/dashboard.log"
else
  echo "[4/5] Skipping React dashboard (npm not found)"
  DASHBOARD_PID=""
fi

# ── Verify services ───────────────────────────────────────────────────────────

echo "[5/5] Checking services..."
sleep 2
bash "${ROOT}/scripts/check_services.sh" localhost || true

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           DONNA is running                           ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  WS hub        ws://localhost:3001                   ║"
echo "║  Telephony     http://localhost:${DONNA_TELEPHONY_PORT}                ║"
echo "║  Dashboard     http://localhost:5173                 ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Voice (push-to-talk):                               ║"
echo "║    bash scripts/run_voice.sh  (separate terminal)    ║"
echo "║                                                      ║"
echo "║  Phone demo (Twilio):                                ║"
echo "║    1. ngrok http ${DONNA_TELEPHONY_PORT}  (separate terminal)   ║"
echo "║    2. Set PUBLIC_URL= in donna/.env                  ║"
echo "║    3. Point Twilio webhook → PUBLIC_URL/voice        ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Logs: logs/ws_hub.log  logs/telephony.log           ║"
echo "║        logs/dashboard.log                            ║"
echo "║  Stop: Ctrl+C                                        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Wait and cleanup on Ctrl+C ────────────────────────────────────────────────

cleanup() {
  echo ""
  echo "Stopping Donna..."
  kill "${WS_HUB_PID}" 2>/dev/null || true
  kill "${TELEPHONY_PID}" 2>/dev/null || true
  [[ -n "${DASHBOARD_PID}" ]] && kill "${DASHBOARD_PID}" 2>/dev/null || true
  echo "Done."
}

trap cleanup EXIT INT TERM

wait "${WS_HUB_PID}" "${TELEPHONY_PID}" 2>/dev/null || true

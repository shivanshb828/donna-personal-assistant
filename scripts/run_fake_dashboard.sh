#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"

if [[ ! -f "${ROOT}/donna/integration/dashboard_events.py" ]]; then
  echo "Run from the dell-hack repo root:"
  echo "  cd ~/dell-hack && bash scripts/run_fake_dashboard.sh"
  exit 1
fi

if [[ ! -d "${VENV}" ]]; then
  echo "Missing .venv — run from repo root:"
  echo "  cd ~/dell-hack && bash scripts/setup_venv.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
cd "${ROOT}"
echo "Starting dashboard WebSocket relay on ws://localhost:3001"
echo "  (React dashboard + voice/telephony pushers share this hub)"
echo "  Debug printer: python donna/fake_dashboard.py"
exec python -m donna.integration.dashboard_events "$@"

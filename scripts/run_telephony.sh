#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi
exec python -m uvicorn donna.telephony.server:app --host 0.0.0.0 --port "${DONNA_TELEPHONY_PORT:-3002}" --reload

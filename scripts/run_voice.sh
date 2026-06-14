#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"

if [[ ! -d "${VENV}" ]]; then
  echo "Missing .venv — run: bash scripts/setup_venv.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
cd "${ROOT}/donna"
exec python -m voice.pipeline "$@"

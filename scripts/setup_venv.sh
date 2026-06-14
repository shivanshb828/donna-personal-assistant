#!/usr/bin/env bash
# Create a repo-local venv and install Donna Python deps.
# Ubuntu 24.04 blocks system pip (PEP 668) — always use this on the Dell GB10.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"

echo "Donna venv setup — ${ROOT}"

missing=()
for pkg in python3 python3-venv portaudio19-dev; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing+=("$pkg")
  fi
done

if ((${#missing[@]})); then
  echo "Installing system packages: ${missing[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
fi

if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "${ROOT}/donna/requirements.txt"

echo
echo "Done. Activate before running voice or fake_dashboard:"
echo "  source ${VENV}/bin/activate"
echo
echo "Or use wrappers:"
echo "  bash scripts/run_voice.sh"
echo "  bash scripts/run_fake_dashboard.sh"

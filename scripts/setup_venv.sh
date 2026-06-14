#!/usr/bin/env bash
# Create a repo-local venv and install Donna Python deps.
# Ubuntu 24.04 blocks system pip (PEP 668) — use apt + venv on the Dell GB10.
# Hackathon Wi-Fi often breaks pip's PyPI JSON fetch — avoid "pip install --upgrade pip".

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/.venv"

echo "Donna venv setup — ${ROOT}"

APT_PACKAGES=(
  python3
  python3-venv
  python3-full
  python3-pip
  portaudio19-dev
  python3-pyaudio
  python3-numpy
  python3-httpx
  python3-websockets
  python3-pytest
)

missing=()
for pkg in "${APT_PACKAGES[@]}"; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    missing+=("$pkg")
  fi
done

if ((${#missing[@]})); then
  echo "Installing apt packages: ${missing[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
fi

if [[ ! -d "${VENV}" ]]; then
  # Reuse apt-installed modules — avoids flaky pip/PyPI on event network
  python3 -m venv --system-site-packages "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

pip_install_pinned() {
  # Pinned versions = smaller PyPI responses; no resolver upgrade dance
  local packages=(
    "httpx==0.27.2"
    "websockets==12.0"
    "numpy==1.26.4"
  )
  for spec in "${packages[@]}"; do
    if python -c "import ${spec%%==*}" 2>/dev/null; then
      echo "  skip ${spec%%==*} (already available)"
      continue
    fi
    echo "  pip → $spec"
    python -m pip install --no-cache-dir "$spec" || {
      echo "WARN: pip install failed for $spec — may still work via apt/system-site-packages"
    }
  done

  if ! python -c "import pyaudio" 2>/dev/null; then
    echo "  pip → pyaudio==0.2.14"
    python -m pip install --no-cache-dir "pyaudio==0.2.14" || true
  fi
}

echo "Checking Python imports..."
if ! python -c "import pyaudio, httpx, websockets, numpy"; then
  echo "Some imports missing — trying pinned pip installs (no pip self-upgrade)..."
  pip_install_pinned
fi

python -c "import pyaudio, httpx, websockets, numpy; print('OK: pyaudio httpx websockets numpy')"

echo
echo "Done. Run voice from repo root:"
echo "  cd ${ROOT} && bash scripts/run_voice.sh"

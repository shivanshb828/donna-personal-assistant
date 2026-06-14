#!/usr/bin/env bash
# Full verification suite for Dell GB10 — run from repo root via SSH or on-box.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

fail=0
pass() { echo "PASS  $*"; }
fail_msg() { echo "FAIL  $*"; fail=1; }

echo "=== Donna Dell verification ==="
echo "host: $(hostname)  repo: ${ROOT}"
echo

echo "--- Services ---"
if bash scripts/check_services.sh; then
  pass "check_services.sh"
else
  fail_msg "check_services.sh"
fi
echo

echo "--- Unit tests ---"
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
if python3 -m unittest discover -s tests -q; then
  pass "unittest (tests/)"
else
  fail_msg "unittest (tests/)"
fi
echo

echo "--- Voice unit tests ---"
if python3 -m pytest donna/voice/tests/ -q 2>/dev/null; then
  pass "pytest (donna/voice/tests/)"
else
  fail_msg "pytest (donna/voice/tests/) — run: sudo apt install python3-pytest"
fi
echo

echo "--- M3 context ---"
if python3 scripts/context_lookup.py Maria | grep -q case-2026-001; then
  pass "context_lookup Maria"
else
  fail_msg "context_lookup Maria"
fi
echo

echo "--- Ollama text query (no mic) ---"
if PYTHONPATH="${ROOT}" python3 -m donna.voice.pipeline --text "How is Maria Lopez doing?" 2>&1 | grep -qi "donna:"; then
  pass "pipeline --text Ollama"
else
  fail_msg "pipeline --text Ollama"
fi
echo

echo "--- Audio devices ---"
if arecord -l 2>/dev/null | grep -q "card"; then
  pass "microphone detected"
else
  echo "WARN  no capture device (USB mic needed for live voice demo)"
fi
echo

if (( fail )); then
  echo "=== RESULT: FAIL ==="
  exit 1
fi
echo "=== RESULT: PASS ==="

#!/usr/bin/env bash
# Quick health check for Donna service dependencies.
# Usage: bash scripts/check_services.sh [host]
# Default host is localhost (run on Dell or via SSH).

set -euo pipefail

HOST="${1:-localhost}"
MODEL="${DONNA_MODEL:-qwen2.5:14b}"

check_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 "$url" || echo "000")"
  if [[ "$code" =~ ^(200|204|404|405)$ ]]; then
    echo "OK   $name ($url)"
  else
    echo "FAIL $name ($url) HTTP $code"
  fi
}

check_tcp() {
  local name="$1"
  local host="$2"
  local port="$3"
  if (echo >/dev/tcp/"$host"/"$port") 2>/dev/null; then
    echo "OK   $name ($host:$port)"
  else
    echo "FAIL $name ($host:$port)"
  fi
}

echo "Donna service check — host=$HOST model=$MODEL"
echo "---"

check_http "STT active (port 9000)" "http://${HOST}:9000/health"
check_http "STT Speaches sidecar" "http://${HOST}:9001/health"
check_http "TTS (Kokoro)" "http://${HOST}:8880/"
check_http "Ollama" "http://${HOST}:11434/api/tags"
check_tcp "Dashboard WS" "$HOST" 3001
check_tcp "Telephony (optional)" "$HOST" 3002

echo "---"
if curl -sf "http://${HOST}:11434/api/tags" 2>/dev/null | grep -qi "${MODEL}"; then
  echo "OK   Ollama model '${MODEL}' in tag list"
else
  echo "FAIL Ollama model '${MODEL}' not found — run: ollama list && ollama pull ${MODEL}"
fi

if [[ "$HOST" == "localhost" || "$HOST" == "127.0.0.1" ]]; then
  if bash "$(dirname "$0")/verify_ollama_model.sh" "$MODEL" 2>/dev/null; then
    echo "OK   Ollama model smoke test passed"
  else
    echo "WARN Ollama model smoke test failed — run: bash scripts/verify_ollama_model.sh"
  fi
fi

echo "---"
if command -v gbrain >/dev/null 2>&1; then
  echo "OK   gbrain CLI ($(gbrain --version 2>/dev/null | head -1 || echo installed))"
else
  echo "SKIP gbrain CLI — optional"
fi

if command -v openclaw >/dev/null 2>&1; then
  echo "OK   openclaw CLI (voice bypasses this — direct Ollama)"
else
  echo "SKIP openclaw CLI — optional; voice uses Ollama direct"
fi

if command -v nemoclaw >/dev/null 2>&1 || command -v nemo-claw >/dev/null 2>&1; then
  echo "OK   NemoClaw CLI present"
else
  echo "SKIP NemoClaw CLI — not required for voice; OpenClaw model wiring in progress"
fi

echo "---"
echo "M3 local files (run from repo root):"
if [[ -f data/donna_m3_context.sqlite ]]; then
  echo "OK   data/donna_m3_context.sqlite"
else
  echo "FAIL data/donna_m3_context.sqlite — run: python3 scripts/init_m3_test_db.py"
fi

if [[ -f data/donna_m3_calendar.sqlite ]]; then
  echo "OK   data/donna_m3_calendar.sqlite"
else
  echo "FAIL data/donna_m3_calendar.sqlite — run: python3 scripts/init_m3_test_db.py"
fi

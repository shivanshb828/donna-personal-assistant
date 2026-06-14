#!/usr/bin/env bash
# Quick health check for Donna service dependencies.
# Usage: bash scripts/check_services.sh [host]
# Default host is localhost (run on Dell or via SSH).

set -euo pipefail

HOST="${1:-localhost}"

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

echo "Donna service check — host=$HOST"
echo "---"

check_http "STT (faster-whisper)" "http://${HOST}:9000/"
check_http "TTS (Kokoro)" "http://${HOST}:8880/"
check_http "Ollama" "http://${HOST}:11434/api/tags"
check_tcp "Dashboard WS" "$HOST" 3001

echo "---"
if command -v gbrain >/dev/null 2>&1; then
  echo "OK   gbrain CLI ($(gbrain --version 2>/dev/null | head -1 || echo installed))"
else
  echo "FAIL gbrain CLI — install: bun install -g github:garrytan/gbrain"
fi

if command -v openclaw >/dev/null 2>&1; then
  echo "OK   openclaw CLI"
else
  echo "FAIL openclaw CLI — M2 agent not on PATH"
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

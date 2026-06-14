#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${ROOT}/.context/logs"

stop_pid_file() {
  local name="$1"
  local file="${LOG_DIR}/${name}.pid"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "→ Stopping $name (pid $pid)"
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

for svc in dashboard telephony ipc ws-relay; do
  stop_pid_file "$svc"
done

echo "Done."

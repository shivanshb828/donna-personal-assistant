#!/usr/bin/env bash
# Tunnel Donna dashboard from Dell GB10 to your Mac via SSH.
# The hackathon Wi-Fi often blocks direct access to port 7777 between laptops.
#
# Usage: bash scripts/tunnel_dashboard.sh
# Then open: http://localhost:7777

set -euo pipefail

DELL_HOST="${DELL_HOST:-dell@10.104.77.67}"
DELL_PASS="${DELL_PASS:-123456}"

echo "Opening SSH tunnel to Dell dashboard…"
echo "  http://localhost:7777  →  Dell :7777 (UI)"
echo "  ws://localhost:3001    →  Dell :3001 (live events)"
echo "  http://localhost:3002  →  Dell :3002 (API)"
echo ""
echo "Keep this terminal open. Ctrl+C to stop."
echo ""

if command -v sshpass >/dev/null 2>&1; then
  exec sshpass -p "$DELL_PASS" ssh -N \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=30 \
    -L 7777:127.0.0.1:7777 \
    -L 3001:127.0.0.1:3001 \
    -L 3002:127.0.0.1:3002 \
    "$DELL_HOST"
fi

exec ssh -N \
  -o ServerAliveInterval=30 \
  -L 7777:127.0.0.1:7777 \
  -L 3001:127.0.0.1:3001 \
  -L 3002:127.0.0.1:3002 \
  "$DELL_HOST"

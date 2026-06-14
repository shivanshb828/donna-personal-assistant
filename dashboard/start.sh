#!/usr/bin/env bash
# Start the Donna dashboard
# Usage: bash start.sh
# Requires: Node.js 18+

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         Donna — AI Legal Secretary       ║"
echo "║            Dashboard Launcher            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check node
if ! command -v node &>/dev/null; then
  echo "✗ Node.js not found. Install from https://nodejs.org (v18+)"
  exit 1
fi

NODE_VER=$(node --version | sed 's/v//')
NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "✗ Node.js v18+ required (found v$NODE_VER)"
  exit 1
fi

# Install deps if needed
if [ ! -d "node_modules" ]; then
  echo "→ Installing dependencies…"
  npm install --silent
fi

echo "→ Starting dashboard on http://localhost:7777"
echo ""
echo "  Backend endpoints expected:"
echo "    WebSocket  ws://localhost:3001  (Donna pipeline events)"
echo "    REST API   http://localhost:3002  (telephony server)"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

npm run dev

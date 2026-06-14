#!/usr/bin/env bash
# Donna — one-shot deploy on Dell GBIO (GB10)
# Run as: bash deploy.sh
# Assumes M1 has already run: nemoclaw install && ollama pull nemotron3-super-120b

set -euo pipefail

DONNA_DIR="/gbio/donna"
GBRAIN_DATA="$DONNA_DIR/gbrain"
VENV="$DONNA_DIR/.venv"

echo "==> [1/6] Creating Donna workspace on GBIO..."
mkdir -p "$DONNA_DIR" "$GBRAIN_DATA" "$DONNA_DIR/cases" "$DONNA_DIR/documents"

echo "==> [2/6] Pulling embedding model..."
ollama pull nomic-embed-text

echo "==> [3/6] Registering Donna with Ollama (Modelfile)..."
ollama create donna -f agent/Modelfile

echo "==> [4/6] Installing Python dependencies..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --quiet psycopg[binary] httpx gbrain

echo "==> [5/6] Starting GBrain (PGLite mode)..."
# GBrain exposes a Postgres wire protocol on port 7700 and MCP on 7701
export GBRAIN_DATA_DIR="$GBRAIN_DATA"
export GBRAIN_EMBEDDING_PROVIDER=ollama
export GBRAIN_EMBEDDING_MODEL=nomic-embed-text
export GBRAIN_EMBEDDING_URL=http://localhost:11434
gbrain start --mode pglite --port 7700 --mcp-port 7701 --data-dir "$GBRAIN_DATA" &
GBRAIN_PID=$!
echo "GBrain PID: $GBRAIN_PID"

echo "    Waiting for GBrain to be ready..."
until psql "postgresql://donna@localhost:7700/donna" -c "SELECT 1" &>/dev/null 2>&1; do
  sleep 1
done

echo "==> [6/6] Initialising database schema..."
export GBRAIN_DSN="postgresql://donna@localhost:7700/donna"
psql "$GBRAIN_DSN" -f gbrain/schema.sql

echo ""
echo "✓ Donna is ready."
echo "  GBrain DSN : $GBRAIN_DSN"
echo "  GBrain MCP : http://localhost:7701"
echo "  Ollama     : http://localhost:11434"
echo ""
echo "Next: run 'openclaw start agent/donna.yaml' to launch the agent."

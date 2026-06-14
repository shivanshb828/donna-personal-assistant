#!/bin/bash
# Start Donna — AI Legal Secretary
# Run this on the Dell GBIO (GB10) machine.

set -e

echo "============================================"
echo "  DONNA — AI Legal Secretary"
echo "  Local-first. Privacy-guaranteed. Always-on."
echo "============================================"
echo ""

# Step 1: Start Ollama (if not already running)
if ! pgrep -x "ollama" > /dev/null; then
    echo "[1/5] Starting Ollama..."
    ollama serve &
    sleep 3
else
    echo "[1/5] Ollama already running."
fi

# Step 2: Check/pull model
MODEL=${DONNA_LLM_MODEL:-"qwen2.5:14b"}
echo "[2/5] Checking model: $MODEL"
if ! ollama list | grep -q "$MODEL"; then
    echo "  Pulling $MODEL (this may take a while for 120B)..."
    ollama pull "$MODEL"
fi
echo "  Model ready."

# Step 3: Start Docker services (Whisper, Kokoro, ChromaDB)
echo "[3/5] Starting Docker services..."
cd "$(dirname "$0")/.."
docker compose up -d
echo "  Waiting for services to be ready..."
sleep 5

# Health checks
echo "  Checking STT..."
until curl -sf http://localhost:9000/health > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ STT ready"

echo "  Checking ChromaDB..."
until curl -sf http://localhost:8001/api/v1/heartbeat > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ ChromaDB ready"

echo "  Checking Kokoro TTS..."
until curl -sf http://localhost:8880/health > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ Kokoro TTS ready"

# Step 4: Apply OpenShell policy
echo "[4/5] Applying OpenShell security policy..."
if command -v openshell &> /dev/null; then
    openshell policy set donna-policy --policy config/openshell-policy.yaml
    echo "  ✓ OpenShell policy active — all outbound blocked"
else
    echo "  ⚠ OpenShell not found. Install NemoClaw first:"
    echo "    curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"
fi

# Step 5: Seed demo data (if DB doesn't exist)
if [ ! -f "knowledge/donna.db" ]; then
    echo "[5/5] Seeding demo data..."
    python3 knowledge/seed_demo.py
else
    echo "[5/5] Database exists. Skipping seed."
fi

echo ""
echo "============================================"
echo "  DONNA IS LIVE"
echo ""
echo "  Say 'Hey Donna' to start talking."
echo ""
echo "  Services:"
echo "    Ollama:    http://localhost:11434"
echo "    Whisper:   http://localhost:9000"
echo "    Kokoro:    http://localhost:8880"
echo "    ChromaDB:  http://localhost:8001"
echo "    Dashboard: http://localhost:3000"
echo ""
echo "  To prove local-only: openshell term"
echo "============================================"
echo ""

# Start the voice pipeline
python3 voice/pipeline.py

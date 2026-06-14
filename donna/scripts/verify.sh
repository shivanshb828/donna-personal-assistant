#!/bin/bash
# Verify all Donna services are running and healthy.

echo "Donna Health Check"
echo "=================="

PASS=0
FAIL=0
MODEL="${DONNA_MODEL:-qwen2.5:14b}"

check() {
    if eval "$2" > /dev/null 2>&1; then
        echo "  ✓ $1"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $1"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "Services:"
check "Ollama running" "pgrep -x ollama"
MODEL="${DONNA_MODEL:-qwen2.5:14b}"
check "Ollama model loaded" "ollama ps | grep -qi '${MODEL}' || curl -sf http://localhost:11434/api/tags | grep -qi '${MODEL}'"
check "STT active (port 9000)" "curl -sf http://localhost:9000/health"
check "STT Speaches sidecar (port 9001)" "curl -sf http://localhost:9001/health"
check "Kokoro TTS (port 8880)" "curl -sf http://localhost:8880/health"
check "ChromaDB (port 8001)" "curl -sf http://localhost:8001/api/v2/heartbeat"

echo ""
echo "Database:"
check "SQLite DB exists" "test -f knowledge/donna.db"
check "Clients seeded" "sqlite3 knowledge/donna.db 'SELECT COUNT(*) FROM clients' | grep -v '^0$'"
check "Cases seeded" "sqlite3 knowledge/donna.db 'SELECT COUNT(*) FROM cases' | grep -v '^0$'"

echo ""
echo "Security (optional — NemoClaw/OpenShell):"
if command -v openshell &> /dev/null; then
    check "OpenShell installed" "openshell --version"
    check "Policy applied" "openshell status | grep -q donna-policy"
else
    echo "  ⚠ OpenShell not installed (optional for voice demo)"
fi

echo ""
echo "Python deps (required for voice):"
check "pyaudio" "python3 -c 'import pyaudio'"
check "httpx" "python3 -c 'import httpx'"
check "numpy" "python3 -c 'import numpy'"
check "pyyaml" "python3 -c 'import yaml'"

echo ""
echo "Python deps (optional — telephony/RAG stack):"
if python3 -c 'import chromadb' 2>/dev/null; then
    echo "  ✓ chromadb"
    PASS=$((PASS + 1))
else
    echo "  ⚠ chromadb (ChromaDB server OK without Python client)"
fi
if python3 -c 'import torch' 2>/dev/null; then
    echo "  ✓ torch"
    PASS=$((PASS + 1))
else
    echo "  ⚠ torch (not needed for voice pipeline on Dell)"
fi

echo ""
echo "=================="
echo "Results: $PASS passed, $FAIL failed"
if [ $FAIL -eq 0 ]; then
    echo "All checks passed. Donna is ready for demo."
else
    echo "Fix failures above before demo."
fi

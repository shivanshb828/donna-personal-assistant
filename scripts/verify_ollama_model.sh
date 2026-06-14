#!/usr/bin/env bash
# Verify the Donna Ollama model is pulled, responds, and supports tool calling.
# Usage: bash scripts/verify_ollama_model.sh [model_name]
# Run on Dell (or via SSH): cd ~/dell-hack && bash scripts/verify_ollama_model.sh

set -euo pipefail

MODEL="${1:-${DONNA_MODEL:-qwen2.5:14b}}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"

echo "Donna Ollama model verification"
echo "  model=$MODEL"
echo "  host=$OLLAMA_HOST"
echo "---"

if ! curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null; then
  echo "FAIL Ollama not reachable at ${OLLAMA_HOST}"
  exit 1
fi
echo "OK   Ollama reachable"

if ! curl -sf "${OLLAMA_HOST}/api/tags" | grep -qi "${MODEL}"; then
  echo "FAIL Model '${MODEL}' not in ollama list"
  echo "     Run: ollama list"
  echo "     Pull: ollama pull ${MODEL}"
  exit 1
fi
echo "OK   Model '${MODEL}' present in ollama list"

echo "     Warming model (short generate)..."
GEN=$(curl -sf "${OLLAMA_HOST}/api/generate" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL}\",\"prompt\":\"Say OK in one word.\",\"stream\":false}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('response','').strip())" 2>/dev/null || echo "")
if [[ -z "$GEN" ]]; then
  echo "FAIL Generate returned empty response"
  exit 1
fi
echo "OK   Generate: ${GEN:0:40}"

echo "     Testing tool calling (/api/chat with tools)..."
TOOL_RESP=$(curl -sf "${OLLAMA_HOST}/api/chat" \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"${MODEL}\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Record that the caller consented to recording. Use the tool.\"}],
    \"tools\": [{
      \"type\": \"function\",
      \"function\": {
        \"name\": \"record_consent\",
        \"description\": \"Record caller consent\",
        \"parameters\": {
          \"type\": \"object\",
          \"properties\": {
            \"consent_type\": {\"type\": \"string\", \"enum\": [\"recording\"]},
            \"granted\": {\"type\": \"boolean\"}
          },
          \"required\": [\"consent_type\", \"granted\"]
        }
      }
    }],
    \"stream\": false
  }" 2>/dev/null || echo "{}")

HAS_TOOL=$(echo "$TOOL_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tc = d.get('message', {}).get('tool_calls') or []
    print('yes' if tc else 'no')
except Exception:
    print('error')
" 2>/dev/null || echo "error")

if [[ "$HAS_TOOL" == "yes" ]]; then
  echo "OK   Tool calling: model returned tool_calls"
elif [[ "$HAS_TOOL" == "no" ]]; then
  echo "WARN Tool calling: no tool_calls in response (Nano may need prompt tuning; voice fallbacks still work)"
else
  echo "FAIL Tool calling: chat request failed"
  exit 1
fi

echo "---"
echo "Model verification complete."

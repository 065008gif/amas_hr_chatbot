#!/usr/bin/env bash
# Phase 1 connectivity test for the Ollama CLOUD chat API.
# Reads OLLAMA_API_KEY from ~/hrbot/.env without printing it.
# Usage: bash scripts/test_ollama.sh [model]   (default: gpt-oss:120b)
set -u
cd "$(dirname "$0")/.." || exit 2
MODEL="${1:-gpt-oss:120b}"
KEY=$(grep -E '^OLLAMA_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
if [ -z "$KEY" ]; then echo "OLLAMA_API_KEY is empty or missing in .env"; exit 1; fi
echo "Key found in .env (length ${#KEY}, value hidden). Model: $MODEL"

BODY=$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply with exactly: ready"}],"stream":false,"options":{"temperature":0}}' "$MODEL")
START=$(date +%s.%N)
RESP=$(curl -sS --max-time 60 -w '\n%{http_code}' https://ollama.com/api/chat \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$BODY")
END=$(date +%s.%N)
CODE=$(echo "$RESP" | tail -1); JSON=$(echo "$RESP" | sed '$d')
echo "HTTP status: $CODE    time: $(echo "$END - $START" | bc) s"
echo "--- raw response:"; echo "$JSON"
echo "--- content only (what users would see):"
echo "$JSON" | python -c 'import sys,json; d=json.load(sys.stdin); m=d.get("message",{}); print(repr(m.get("content"))); print("thinking field present:", bool(m.get("thinking"))); print("tokens in/out:", d.get("prompt_eval_count"), d.get("eval_count"))' 2>/dev/null || echo "(response was not valid chat JSON)"

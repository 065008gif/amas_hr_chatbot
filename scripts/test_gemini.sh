#!/usr/bin/env bash
# Phase 1 connectivity test for Google Gemini (AI Studio free tier).
# Reads GEMINI_API_KEY from ~/hrbot/.env without printing it; sends it in a header, not the URL.
# Usage: bash scripts/test_gemini.sh [model]   (default: gemini-3.1-flash-lite)
set -u
cd "$(dirname "$0")/.." || exit 2
MODEL="${1:-gemini-3.1-flash-lite}"
KEY=$(grep -E '^GEMINI_API_KEY=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')
if [ -z "$KEY" ]; then echo "GEMINI_API_KEY is empty or missing in .env"; exit 1; fi
echo "Key found in .env (length ${#KEY}, value hidden)."
BASE=https://generativelanguage.googleapis.com/v1beta

echo "--- models this key can use for chat (flash/pro only):"
curl -sS --max-time 30 "$BASE/models?pageSize=200" -H "x-goog-api-key: $KEY" | python -c '
import sys,json
d=json.load(sys.stdin)
if "error" in d: print("ERROR:", d["error"].get("code"), d["error"].get("message")); sys.exit()
for m in d.get("models",[]):
    n=m["name"].split("/")[-1]
    if "generateContent" in m.get("supportedGenerationMethods",[]) and ("flash" in n or "pro" in n): print("  ", n)
'

echo "--- chat test with model: $MODEL"
BODY='{"contents":[{"role":"user","parts":[{"text":"Reply with exactly: ready"}]}],"generationConfig":{"temperature":0}}'
RESP=$(curl -sS --max-time 60 -w '\n%{http_code} %{time_total}' "$BASE/models/$MODEL:generateContent" \
  -H "x-goog-api-key: $KEY" -H "Content-Type: application/json" -d "$BODY")
META=$(echo "$RESP" | tail -1); JSON=$(echo "$RESP" | sed '$d')
echo "HTTP status: ${META% *}    time: ${META#* } s"
echo "$JSON" | python -c '
import sys,json
d=json.load(sys.stdin)
if "error" in d: print("ERROR:", d["error"].get("code"), d["error"].get("status"), d["error"].get("message")); sys.exit(1)
parts=d["candidates"][0]["content"]["parts"]
print("content:", repr("".join(p.get("text","") for p in parts if not p.get("thought"))))
u=d.get("usageMetadata",{}); print("tokens in/out/thinking:", u.get("promptTokenCount"), u.get("candidatesTokenCount"), u.get("thoughtsTokenCount"))
'

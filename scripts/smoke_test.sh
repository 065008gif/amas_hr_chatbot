#!/usr/bin/env bash
# Smoke test of a running Nia backend: /health, then three sample questions.
# Usage: bash scripts/smoke_test.sh [BASE_URL]
#   default BASE_URL = https://akshit065008-nia-hr-assistant.hf.space
set -u
BASE="${1:-https://akshit065008-nia-hr-assistant.hf.space}"
EMP="NXR100056"   # demo employee (fictional)
echo "== Smoke test against $BASE"
echo "-- /health (waits up to 4 minutes for a sleeping Space to wake)"
ok=0
for i in $(seq 1 48); do
  H=$(curl -s --max-time 20 "$BASE/health")
  if echo "$H" | grep -q '"ready":true'; then ok=1; break; fi
  printf "   waiting (%s)...\n" "$(echo "$H" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("status"))
except Exception: print("not reachable yet")' 2>/dev/null)"
  sleep 5
done
[ $ok = 1 ] || { echo "FAIL: backend not ready"; exit 1; }
echo "$H" | python3 -c 'import sys,json; h=json.load(sys.stdin); print("   status:", h["status"], "| chunks:", h["index"]["chunks"], "| providers:", h["providers"]["order"])'
fail=0
for Q in "How many days of paternity leave do I get for a baby born in August 2025?" \
         "What is the notice period if I resign at L5?" \
         "Does Nexora pay for egg freezing?"; do
  echo "-- Q: $Q"
  R=$(curl -s --max-time 90 -X POST "$BASE/chat" -H 'Content-Type: application/json' -H "X-Employee-Id: $EMP" \
      -d "$(python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1], "history": []}))' "$Q")")
  echo "$R" | python3 -c 'import sys,json
r=json.load(sys.stdin)
assert r.get("route") in ("answer","not_found","clarify","escalate","tool","refused"), r
print("   route:", r.get("route"), "| provider:", r.get("provider"), "| latency:", r.get("latency_ms"), "ms")
print("   answer:", (r.get("answer") or "")[:220].replace("\n"," "))
for c in r.get("citations", []): print("   cite:", c["label"], "(page verified)" if c["verified"] else "(NOT verified)")' || fail=1
done
[ $fail = 0 ] && echo "== SMOKE TEST PASSED" || { echo "== SMOKE TEST FAILED"; exit 1; }

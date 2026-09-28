#!/usr/bin/env bash
# Smoke test of a running Nia backend: /health, then three sample questions.
# Usage: bash scripts/smoke_test.sh BASE_URL
#   deployed: bash scripts/smoke_test.sh https://nexora-hr-portal.vercel.app
#   local:    bash scripts/smoke_test.sh http://localhost:8000     (uvicorn api.index:app --port 8000)
set -u
SITE="${1:?give the site address, e.g. https://nexora-hr-portal.vercel.app}"
BASE="${SITE%/}/api"
EMP="NXR100056"   # demo employee (fictional)
echo "== Smoke test against $BASE"
echo "-- /api/health (waits up to 4 minutes; the first call after a quiet period starts a cold instance)"
T0=$(date +%s.%N)
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
echo "   first health response after $(python3 -c "print(round($(date +%s.%N)-$T0,1))") s"
echo "$H" | python3 -c 'import sys,json; h=json.load(sys.stdin); print("   status:", h["status"], "| chunks:", h["index"]["chunks"], "| warm-up:", h["warm_seconds"], "s | storage:", h.get("storage"), "| platform:", h.get("platform"))'
echo "-- site pages"
for P in / /chat /library; do printf "   %-9s HTTP %s\n" "$P" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${SITE%/}$P")"; done
printf "   %-9s HTTP %s\n" "pdf 001" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$BASE/pdf/001")"
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

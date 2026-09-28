"""Phase 7 latency of the LIVE site (D-048). Measured from the college PC over the internet.

  python tests/latency.py --cold          # one cold-start probe: time until /api/health is ready
  python tests/latency.py --warm          # 20 questions (cache misses), then 5 repeats (cache hits), + page loads
  python tests/latency.py --report        # summarise tests/results/latency_runs.jsonl -> latency.{json,md}

Cold vs warm is decided from the server, not guessed: /api/health returns the instance's uptime_seconds, so
a probe whose instance is younger than the probe itself started a fresh instance (a cold start). Chat
requests are paced at one every 4 s to stay under the per-IP limit of 20 a minute. The live answer cache is
on (as for real users), so each response's cache_hit flag is recorded and hits and misses are reported
separately. Questions come from tests/eval_set.yaml.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evalkit import RESULTS, load_set  # noqa: E402

SITE = "https://nexora-hr-portal.vercel.app"
RUNS = RESULTS / "latency_runs.jsonl"
EMP = {"X-Employee-Id": "NXR100056"}         # demo employee (fictional)
WARM_IDS = ["Q02", "Q05", "Q10", "Q11", "Q16", "Q17", "Q23", "Q24", "Q26", "Q31", "Q33", "Q38",
            "Q40", "Q41", "Q45", "Q46", "Q49", "Q53", "Q57", "Q61"]


def log(rec):
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    with RUNS.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def dns_seconds():
    """Time one DNS lookup of the site (the college network has shown 5-15 s DNS stalls, D-011/D-015)."""
    import socket
    t = time.time()
    try:
        socket.getaddrinfo(SITE.split("//")[1], 443)
    except OSError:
        return None
    return round(time.time() - t, 2)


def cold(client, idle_note):
    dns = dns_seconds()
    t0 = time.time()
    attempts, h = 0, None
    while time.time() - t0 < 240:
        attempts += 1
        try:
            r = client.get(f"{SITE}/api/health", timeout=60)
            h = r.json()
            if h.get("ready"):
                break
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(2)
    total = time.time() - t0
    fresh = bool(h) and h.get("uptime_seconds", 1e9) <= total + 2
    rec = {"kind": "cold_probe", "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "idle_note": idle_note,
           "seconds_to_ready": round(total, 2), "dns_s": dns, "attempts": attempts, "fresh_instance": fresh,
           "server_uptime_s": h and h.get("uptime_seconds"), "server_warm_s": h and h.get("warm_seconds")}
    log(rec)
    print(json.dumps(rec))


def warm(client):
    items = {i["id"]: i for i in load_set()["singles"]}
    h = client.get(f"{SITE}/api/health", timeout=60).json()
    print(f"instance uptime {h.get('uptime_seconds')} s")
    for path in ["/", "/chat", "/library"]:
        t = time.time()
        r = client.get(SITE + path, timeout=30)
        log({"kind": "page", "path": path, "status": r.status_code, "seconds": round(time.time() - t, 3)})
    t = time.time()
    r = client.get(f"{SITE}/api/pdf/001", timeout=60)
    log({"kind": "pdf", "status": r.status_code, "bytes": len(r.content), "seconds": round(time.time() - t, 3)})
    plan = [(i, "first") for i in WARM_IDS] + [(i, "repeat") for i in WARM_IDS[:5]]
    for n, (iid, phase) in enumerate(plan, 1):
        q = items[iid]["q"]
        t = time.time()
        try:
            r = client.post(f"{SITE}/api/chat", json={"message": q, "history": []}, headers=EMP, timeout=90)
            d = r.json() if r.status_code == 200 else {}
            status = r.status_code
        except httpx.HTTPError as e:
            d, status = {}, f"error {type(e).__name__}"
        wall = round(time.time() - t, 3)
        rec = {"kind": "chat", "phase": phase, "id": iid, "status": status, "wall_s": wall, "server_ms": d.get("latency_ms"),
               "cache_hit": d.get("cache_hit"), "route": d.get("route"), "provider": d.get("provider"), "usage": d.get("usage")}
        log(rec)
        print(f"[{n}/{len(plan)}] {iid} {phase:6} {status} wall {wall:.2f}s server {d.get('latency_ms')} ms cache {d.get('cache_hit')} {d.get('route')}")
        time.sleep(4)


def report():
    rows = [json.loads(line) for line in RUNS.read_text().splitlines() if line.strip()]
    colds = [r for r in rows if r["kind"] == "cold_probe"]
    chats = [r for r in rows if r["kind"] == "chat" and r["status"] == 200]
    miss = [r for r in chats if not r["cache_hit"]]
    hit = [r for r in chats if r["cache_hit"]]
    pages = [r for r in rows if r["kind"] in ("page", "pdf")]

    def stats(v):
        v = sorted(v)
        return {"n": len(v), "median": round(statistics.median(v), 2), "p95": round(v[min(len(v) - 1, round(0.95 * (len(v) - 1)))], 2),
                "max": round(max(v), 2)} if v else None
    s = {"cold_fresh_instance_s": stats([c["seconds_to_ready"] for c in colds if c["fresh_instance"]]),
         "probes_that_found_a_warm_instance_s": stats([c["seconds_to_ready"] for c in colds if not c["fresh_instance"]]),
         "chat_cache_miss_wall_s": stats([r["wall_s"] for r in miss]),
         "chat_cache_miss_server_s": stats([r["server_ms"] / 1000 for r in miss if r.get("server_ms") is not None]),
         "chat_cache_hit_wall_s": stats([r["wall_s"] for r in hit]),
         "chat_errors": sum(1 for r in rows if r["kind"] == "chat" and r["status"] != 200),
         "page_load_s": stats([r["seconds"] for r in pages]),
         "cold_probes": colds}
    (RESULTS / "latency.json").write_text(json.dumps(s, indent=1))
    f = lambda x: f"median {x['median']} s, p95 {x['p95']} s, max {x['max']} s (n={x['n']})" if x else "n/a"  # noqa: E731
    L = ["# Live-site latency (https://nexora-hr-portal.vercel.app, measured from the college PC)", "",
         "| Measurement | Result |", "|---|---|",
         f"| Cold start: first request until the backend is ready (fresh instance confirmed by server uptime) | {f(s['cold_fresh_instance_s'])} |",
         f"| Probes whose instance had started before the probe (see notes below) | {f(s['probes_that_found_a_warm_instance_s'])} |",
         f"| Chat answer, cache miss, as the user waits (network included) | {f(s['chat_cache_miss_wall_s'])} |",
         f"| Chat answer, cache miss, server time only | {f(s['chat_cache_miss_server_s'])} |",
         f"| Chat answer, repeated question (cache hit) | {f(s['chat_cache_hit_wall_s'])} |",
         f"| Page and PDF loads | {f(s['page_load_s'])} |",
         f"| Chat requests that failed | {s['chat_errors']} |", "", "Cold probes:", ""]
    L += [f"- {c['at']}: {c['seconds_to_ready']} s, fresh instance: {c['fresh_instance']} (server uptime {c['server_uptime_s']} s, "
          f"in-function warm-up {c['server_warm_s']} s, separate DNS lookup " + (f"{c['dns_s']} s" if c.get('dns_s') is not None else "not timed") + f"); idle before: {c['idle_note']}" for c in colds]
    L += ["", "The first probe waited 65 s in a single request although its instance had been up for 122 s, so it was not a "
          "cold start of that instance; the cause (a second instance starting, or the network) could not be determined, and "
          "DNS was not yet timed. The two controlled probes after 20 and 40 idle minutes both reached fresh instances and "
          "took about 46 s, of which about 4 s is the backend loading its index and models; the rest is Vercel starting the "
          "instance (the Python bundle is 287 MB), before any of our code runs. The portal's waking-up screen waits up to "
          "60 s per attempt, so a first visitor after a quiet period waits about 46 s."]
    (RESULTS / "latency.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cold", action="store_true")
    ap.add_argument("--idle-note", default="unknown")
    ap.add_argument("--warm", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    with httpx.Client(headers={"User-Agent": "nia-latency-eval"}) as client:
        if a.cold:
            cold(client, a.idle_note)
        if a.warm:
            warm(client)
    if a.report:
        report()


if __name__ == "__main__":
    main()

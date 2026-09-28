"""Check both storage backends behave the same (tickets, ownership, cache, logs, insights).

Run from ~/hrbot:   python tests/check_store_backends.py

The Upstash backend is exercised against an in-memory fake of Upstash's REST API (a JSON
command array POSTed to the URL, or a list of them to /pipeline), so no real database is needed.
"""
import json
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config, store  # noqa: E402


class FakeUpstash:
    def __init__(self):
        self.data, self.calls = {}, 0

    def run(self, c):
        self.calls += 1
        op, *a = c
        d = self.data
        if op == "SET":
            if "NX" in a and a[0] in d:
                return None
            d[a[0]] = a[1]
            return "OK"
        if op == "SETNX":
            if a[0] in d:
                return 0
            d[a[0]] = a[1]
            return 1
        if op == "GET":
            return d.get(a[0])
        if op == "INCR":
            d[a[0]] = str(int(d.get(a[0], 0)) + 1)
            return int(d[a[0]])
        if op == "LPUSH":
            d.setdefault(a[0], []).insert(0, a[1])
            return len(d[a[0]])
        if op == "LRANGE":
            lst = d.get(a[0], [])
            return lst[int(a[1]): int(a[2]) + 1]
        if op == "LTRIM":
            d[a[0]] = d.get(a[0], [])[int(a[1]): int(a[2]) + 1]
            return "OK"
        if op == "MGET":
            return [d.get(k) for k in a]
        if op == "HINCRBY":
            h = d.setdefault(a[0], {})
            h[a[1]] = h.get(a[1], 0) + int(a[2])
            return h[a[1]]
        if op == "HGETALL":
            return [x for k, v in d.get(a[0], {}).items() for x in (k, str(v))]
        raise ValueError(op)

    def handler(self, request):
        body = json.loads(request.content)
        if request.url.path.endswith("/pipeline"):
            return httpx.Response(200, json=[{"result": self.run(c)} for c in body])
        return httpx.Response(200, json={"result": self.run(body)})


def exercise(label):
    b = store.backend()
    demo = store.demo_accounts()[0]["employee_id"]
    other = store.demo_accounts()[1]["employee_id"]
    seeded = len(store.list_tickets(demo))
    t = store.create_ticket(demo, "Leave", "Test ticket from the check script", source="chat")
    checks = {
        "seeded 3 demo tickets": seeded == 3,
        "new ticket listed first": store.list_tickets(demo)[0]["id"] == t["id"],
        "owner can read ticket": store.get_ticket(t["id"], demo) is not None,
        "other employee cannot": store.get_ticket(t["id"], other) is None,
        "ticket ids increase": store.create_ticket(demo, "Other", "second")["id"] > t["id"],
    }
    store.cache_put("k1", {"answer": "cached"})
    checks["cache round-trip"] = store.cache_get("k1") == {"answer": "cached"}
    store.log_turn("answer", "Leave", 1200, "ollama", {"in": 10, "out": 5}, 0.9, False, "What is my leave?", 2)
    store.log_turn("answer", "Leave", 5, None, None, 0.9, True, "What is my leave?", 2)
    ins = store.insights()
    checks["insights aggregate"] = ins["total_questions"] == 2 and ins["repeat_questions"] == 1 and ins["cache_hit_rate"] == 0.5
    checks["no message text in logs"] = "What is my leave" not in json.dumps(b.logs())
    checks["chat ticket categories"] = {"category": "Leave", "n": 1} in ins["tickets_by_category"]
    for k, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {k}")
    return all(checks.values())


def main():
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        config.DB_PATH = Path(tmp) / "t.sqlite"
        store._backend = None
        ok &= exercise("sqlite")
    fake = FakeUpstash()
    rb = store.RedisBackend("https://fake-upstash.example", "token")
    rb.http = httpx.Client(transport=httpx.MockTransport(fake.handler))
    store._backend = rb
    store._seed_demo_tickets(rb)
    ok &= exercise("upstash (fake REST)")
    print(f"Upstash REST commands used by this run: {fake.calls}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

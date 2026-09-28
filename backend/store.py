"""Storage for tickets, the answer cache and anonymised logs; plus the DEMO employee file.

Two interchangeable backends, chosen at start-up:
  - Upstash Redis (REST API) when KV_REST_API_URL/KV_REST_API_TOKEN or UPSTASH_REDIS_REST_URL/
    UPSTASH_REDIS_REST_TOKEN are set (added by the Vercel Marketplace integration): data persists.
  - SQLite otherwise (this PC, or /tmp on Vercel without Redis: data resets when an instance stops).

Privacy (brief Part F, Phase 5): full user messages are NOT stored. A log record keeps only the
route, topic, latency, provider, token counts, confidence, cache hit, citation count and a
SHA-256 prefix of the normalised question (so repeats can be counted without keeping the text).
"""
import csv
import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx

from backend import config

IST = timezone(timedelta(hours=5, minutes=30))
_lock = threading.RLock()   # re-entrant: seeding creates tickets while backend() holds it
LOG_KEEP = 5000             # most recent log records kept
CACHE_TTL = 7 * 24 * 3600   # seconds an answer stays cached in Redis


def now_iso():
    return datetime.now(IST).isoformat(timespec="seconds")


# ================================================================ backends
class RedisBackend:
    name = "upstash-redis"
    persistent = True

    def __init__(self, url, token):
        self.url = url.rstrip("/")
        self.http = httpx.Client(timeout=httpx.Timeout(8.0, connect=5.0), headers={"Authorization": f"Bearer {token}"})

    def cmd(self, *args):
        r = self.http.post(self.url, json=[str(a) for a in args])
        r.raise_for_status()
        return r.json().get("result")

    def pipe(self, *cmds):
        r = self.http.post(f"{self.url}/pipeline", json=[[str(a) for a in c] for c in cmds])
        r.raise_for_status()
        return [x.get("result") for x in r.json()]

    def next_ticket_number(self):
        return int(self.pipe(["SETNX", "nia:ticket:counter", 122], ["INCR", "nia:ticket:counter"])[1])

    def save_ticket(self, t, new):
        cmds = [["SET", f"nia:ticket:{t['id']}", json.dumps(t)]]
        if new:
            cmds.append(["LPUSH", f"nia:tickets:{t['employee_id']}", t["id"]])
        self.pipe(*cmds)

    def load_ticket(self, tid):
        v = self.cmd("GET", f"nia:ticket:{tid}")
        return json.loads(v) if v else None

    def employee_tickets(self, emp):
        ids = self.cmd("LRANGE", f"nia:tickets:{emp}", 0, 199) or []
        vals = self.cmd("MGET", *[f"nia:ticket:{i}" for i in ids]) if ids else []
        return [json.loads(v) for v in vals if v]

    def claim_seed(self):
        return bool(self.cmd("SET", "nia:seeded", "1", "NX"))

    def cache_get(self, key):
        v = self.cmd("GET", f"nia:cache:{key}")
        return json.loads(v) if v else None

    def cache_put(self, key, value):
        self.cmd("SET", f"nia:cache:{key}", json.dumps(value), "EX", CACHE_TTL)

    def add_log(self, rec):
        self.pipe(["LPUSH", "nia:logs", json.dumps(rec)], ["LTRIM", "nia:logs", 0, LOG_KEEP - 1])

    def logs(self):
        return [json.loads(x) for x in (self.cmd("LRANGE", "nia:logs", 0, LOG_KEEP - 1) or [])]

    def chat_ticket_categories(self):
        flat = self.cmd("HGETALL", "nia:chat-ticket-categories") or []
        return {flat[i]: int(flat[i + 1]) for i in range(0, len(flat), 2)}

    def count_chat_ticket(self, category):
        self.cmd("HINCRBY", "nia:chat-ticket-categories", category, 1)


class SQLiteBackend:
    name = "sqlite"
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS logs (ts REAL NOT NULL, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS kv (name TEXT PRIMARY KEY, value TEXT NOT NULL);
    """

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.persistent = not str(path).startswith("/tmp")
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.executescript(self.SCHEMA)

    def _kv(self, name, default=None):
        row = self.conn.execute("SELECT value FROM kv WHERE name=?", (name,)).fetchone()
        return row[0] if row else default

    def _set_kv(self, name, value):
        self.conn.execute("INSERT OR REPLACE INTO kv VALUES(?, ?)", (name, value))
        self.conn.commit()

    def next_ticket_number(self):
        n = int(self._kv("ticket", 122)) + 1
        self._set_kv("ticket", str(n))
        return n

    def save_ticket(self, t, new):
        self.conn.execute("INSERT OR REPLACE INTO tickets VALUES (?,?,?,?)", (t["id"], t["employee_id"], json.dumps(t), t["created_at"]))
        self.conn.commit()

    def load_ticket(self, tid):
        row = self.conn.execute("SELECT data FROM tickets WHERE id=?", (tid,)).fetchone()
        return json.loads(row[0]) if row else None

    def employee_tickets(self, emp):
        return [json.loads(r[0]) for r in self.conn.execute(
            "SELECT data FROM tickets WHERE employee_id=? ORDER BY created_at DESC", (emp,)).fetchall()]

    def claim_seed(self):
        if self._kv("seeded"):
            return False
        self._set_kv("seeded", "1")
        return True

    def cache_get(self, key):
        row = self.conn.execute("SELECT response FROM cache WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def cache_put(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, json.dumps(value), time.time()))
        self.conn.commit()

    def add_log(self, rec):
        self.conn.execute("INSERT INTO logs VALUES (?,?)", (rec["ts"], json.dumps(rec)))
        self.conn.commit()

    def logs(self):
        return [json.loads(r[0]) for r in self.conn.execute("SELECT data FROM logs ORDER BY ts DESC LIMIT ?", (LOG_KEEP,)).fetchall()]

    def chat_ticket_categories(self):
        return json.loads(self._kv("chat_ticket_categories", "{}"))

    def count_chat_ticket(self, category):
        c = self.chat_ticket_categories()
        c[category] = c.get(category, 0) + 1
        self._set_kv("chat_ticket_categories", json.dumps(c))


_backend = None


def backend():
    global _backend
    with _lock:
        if _backend is None:
            url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
            token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
            _backend = RedisBackend(url, token) if url and token else SQLiteBackend(config.DB_PATH)
            _seed_demo_tickets(_backend)   # _backend is already set, so create_ticket() can use it
        return _backend


def db():
    """Initialise storage (used by the warm-up)."""
    return backend()


def storage_info():
    b = backend()
    return {"backend": b.name, "persistent": b.persistent}


# ================================================================ employees (DEMO data)
_employees = None


def employees():
    global _employees
    if _employees is None:
        with open(config.EMPLOYEES_CSV, newline="") as f:
            rows = csv.DictReader(line for line in f if not line.startswith("#"))
            _employees = {r["employee_id"]: r for r in rows}
    return _employees


def employee(emp_id):
    return employees().get((emp_id or "").upper())


def demo_accounts():
    return [{k: e[k] for k in ("employee_id", "name", "grade", "designation", "location")}
            for e in employees().values() if e["demo_account"] == "yes"]


def leave_balance(emp_id):
    e = employee(emp_id)
    if not e:
        return None
    f = lambda k: float(e[k])  # noqa: E731
    return {
        "employee_id": e["employee_id"], "name": e["name"], "grade": e["grade"], "location": e["location"],
        "as_of": e["as_of"], "demo_data": True,
        "balances": [
            {"type": "Earned Leave", "code": "EL", "balance": f("el_balance"), "total": f("el_opening") + f("el_accrued"), "taken": f("el_taken"),
             "detail": f"{f('el_opening')} carried forward + {f('el_accrued')} credited this Leave Year - {f('el_taken')} taken"},
            {"type": "Casual Leave", "code": "CL", "balance": f("cl_balance"), "total": f("cl_credited"), "taken": f("cl_taken"),
             "detail": f"{f('cl_credited')} credited on 1 April - {f('cl_taken')} taken; lapses on 31 March"},
            {"type": "Sick Leave", "code": "SL", "balance": f("sl_balance"), "total": f("sl_opening") + f("sl_credited"), "taken": f("sl_taken"),
             "detail": f"{f('sl_opening')} carried forward + {f('sl_credited')} credited - {f('sl_taken')} taken"},
            {"type": "Restricted Holidays", "code": "RH", "balance": f("rh_balance"), "total": 2.0, "taken": 2.0 - f("rh_balance"),
             "detail": "Choose from the restricted holiday list (Leave Policy, Annexure B)"},
        ],
        "source": "Computed from the Leave Policy (NTL/HR/POL/001) Table 1 and accrual rules; demo employee file.",
    }


# ================================================================ tickets
def create_ticket(employee_id, category, summary, priority="Normal", source="chat", status="Open", created=None):
    if category not in config.TICKET_CATEGORIES:
        category = "Other"
    if priority not in ("Low", "Normal", "High", "Urgent"):
        priority = "Normal"
    summary = re.sub(r"\s+", " ", summary).strip()[:300] or "HR query"
    b = backend()
    with _lock:
        n = b.next_ticket_number()
    ts = created or now_iso()
    hist = [{"status": "Open", "at": ts, "note": "Ticket created" + (" from chat with Nia" if source == "chat" else "")}]
    if status != "Open":
        hist.append({"status": status, "at": ts, "note": "Updated by HR Operations (demo)"})
    t = {"id": f"{config.TICKET_PREFIX}-{datetime.now(IST).year}-{n:06d}", "employee_id": employee_id, "category": category,
         "summary": summary, "priority": priority, "status": status, "created_at": ts, "updated_at": ts,
         "source": source, "history": hist}
    b.save_ticket(t, new=True)
    if source == "chat":
        b.count_chat_ticket(category)
    return t


def get_ticket(tid, employee_id):
    """A ticket is returned only to the employee who owns it."""
    t = backend().load_ticket(tid.upper())
    return t if t and t["employee_id"] == employee_id else None


def list_tickets(employee_id):
    return sorted(backend().employee_tickets(employee_id), key=lambda t: t["created_at"], reverse=True)


def _seed_demo_tickets(b):
    """Each demo account starts with a few past tickets in different states (DEMO data)."""
    if not b.claim_seed():
        return
    samples = [("Leave", "EL credit for August not reflected on NPP", "Resolved"),
               ("Payroll", "Query on professional tax deduction in payslip", "In Progress"),
               ("Benefits", "Add spouse to group medical insurance after marriage", "Awaiting Employee"),
               ("IT Access", "Access to client VDI for new project", "Closed"),
               ("Policy Clarification", "Is Holi a declared holiday at my location?", "Resolved")]
    rng = random.Random(7)
    for acc in sorted(demo_accounts(), key=lambda a: a["employee_id"]):
        for j in rng.sample(range(len(samples)), 3):
            cat, summ, status = samples[j]
            created = (datetime.now(IST) - timedelta(days=rng.randint(3, 60))).isoformat(timespec="seconds")
            create_ticket(acc["employee_id"], cat, summ, source="portal", status=status, created=created)


# ================================================================ answer cache
def normalise_question(q):
    q = q.lower()
    q = re.sub(r"[^\w\s/.-]", " ", q)
    q = re.sub(r"\b(please|kindly|hi|hello|nia|hey|thanks|thank you)\b", " ", q)
    return re.sub(r"\s+", " ", q).strip(" .")


def cache_key(question, profile):
    p = profile or {}
    raw = json.dumps([normalise_question(question), (p.get("grade") or "").upper(), (p.get("location") or "").title()])
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_get(key):
    if not config.CACHE_ENABLED:
        return None
    try:
        return backend().cache_get(key)
    except Exception:
        return None            # storage trouble must never break a chat turn


def cache_put(key, response):
    if not config.CACHE_ENABLED:
        return
    try:
        backend().cache_put(key, response)
    except Exception:
        pass


# ================================================================ anonymised logs and insights
def log_turn(route, topic, latency_ms, provider, usage, confidence, cache_hit, question, citations):
    rec = {"ts": time.time(), "route": route, "topic": topic, "latency_ms": int(latency_ms), "provider": provider,
           "tokens_in": (usage or {}).get("in", 0), "tokens_out": (usage or {}).get("out", 0), "confidence": confidence,
           "cache_hit": int(bool(cache_hit)), "citations": citations,
           "question_hash": hashlib.sha256(normalise_question(question).encode()).hexdigest()[:16]}
    try:
        backend().add_log(rec)
    except Exception:
        pass


def insights():
    """Aggregates only: there is no message text to show."""
    logs = backend().logs()

    def count(key, rows):
        return [{key: k, "n": n} for k, n in Counter(r.get(key) for r in rows if r.get(key)).most_common()]

    policy = [r for r in logs if r["route"] in ("answer", "not_found", "clarify")]
    fresh = [r["latency_ms"] for r in logs if not r["cache_hit"]]
    days = Counter(datetime.fromtimestamp(r["ts"], IST).strftime("%Y-%m-%d") for r in logs)
    hashes = Counter(r["question_hash"] for r in logs)
    return {
        "total_questions": len(logs),
        "by_route": count("route", logs),
        "by_topic": count("topic", logs),
        "unanswered_topics": count("topic", [r for r in logs if r["route"] == "not_found"])[:8],
        "cache_hit_rate": (sum(r["cache_hit"] for r in policy) / len(policy)) if policy else 0,
        "avg_latency_ms": (sum(fresh) / len(fresh)) if fresh else 0,
        "by_provider": count("provider", logs),
        "daily": [{"day": d, "n": n} for d, n in sorted(days.items(), reverse=True)[:14]],
        "repeat_questions": sum(1 for n in hashes.values() if n > 1),
        "tickets_by_category": [{"category": k, "n": v} for k, v in backend().chat_ticket_categories().items()],
        "storage": storage_info(),
    }

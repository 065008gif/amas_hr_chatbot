"""SQLite storage: tickets, the answer cache and anonymised logs; plus the DEMO employee file.

Privacy (brief Part F, Phase 5): full user messages are NOT stored. The log keeps only the route,
latency, token counts, confidence, provider, cache hit, a coarse topic and a SHA-256 hash of the
normalised question (so repeats can be counted without keeping the text).
"""
import csv
import hashlib
import json
import random
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from backend import config

IST = timezone(timedelta(hours=5, minutes=30))
_lock = threading.RLock()   # re-entrant: db() may seed tickets while a caller holds it
_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, category TEXT NOT NULL, summary TEXT NOT NULL,
  priority TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'chat', history TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS cache (
  key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at REAL NOT NULL, hits INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS logs (
  ts REAL NOT NULL, route TEXT, topic TEXT, latency_ms INTEGER, provider TEXT, tokens_in INTEGER,
  tokens_out INTEGER, confidence REAL, cache_hit INTEGER, question_hash TEXT, citations INTEGER);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""


def db():
    global _conn
    if _conn is None:
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _seed_demo_tickets()
    return _conn


def now_iso():
    return datetime.now(IST).isoformat(timespec="seconds")


# ---------------------------------------------------------------- employees (DEMO data)
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
            {"type": "Earned Leave", "code": "EL", "balance": f("el_balance"),
             "detail": f"{f('el_opening')} carried forward + {f('el_accrued')} credited this Leave Year - {f('el_taken')} taken"},
            {"type": "Casual Leave", "code": "CL", "balance": f("cl_balance"),
             "detail": f"{f('cl_credited')} credited on 1 April - {f('cl_taken')} taken; lapses on 31 March"},
            {"type": "Sick Leave", "code": "SL", "balance": f("sl_balance"),
             "detail": f"{f('sl_opening')} carried forward + {f('sl_credited')} credited - {f('sl_taken')} taken"},
            {"type": "Restricted Holidays", "code": "RH", "balance": f("rh_balance"),
             "detail": "Choose from the restricted holiday list (Leave Policy, Annexure B)"},
        ],
        "source": "Computed from the Leave Policy (NTL/HR/POL/001) Table 1 and accrual rules; demo employee file.",
    }


# ---------------------------------------------------------------- tickets
STATUS_FLOW = ["Open", "In Progress", "Awaiting Employee", "Resolved", "Closed"]


def _next_ticket_id(conn):
    year = datetime.now(IST).year
    row = conn.execute("SELECT value FROM counters WHERE name='ticket'").fetchone()
    n = (row["value"] if row else 122) + 1
    conn.execute("INSERT OR REPLACE INTO counters(name, value) VALUES('ticket', ?)", (n,))
    return f"{config.TICKET_PREFIX}-{year}-{n:06d}"


def create_ticket(employee_id, category, summary, priority="Normal", source="chat", status="Open", created=None):
    if category not in config.TICKET_CATEGORIES:
        category = "Other"
    if priority not in ("Low", "Normal", "High", "Urgent"):
        priority = "Normal"
    summary = re.sub(r"\s+", " ", summary).strip()[:300] or "HR query"
    with _lock:
        conn = _conn or db()
        tid = _next_ticket_id(conn)
        ts = created or now_iso()
        hist = [{"status": "Open", "at": ts, "note": "Ticket created" + (" from chat with Nia" if source == "chat" else "")}]
        if status != "Open":
            hist.append({"status": status, "at": ts, "note": "Updated by HR Operations (demo)"})
        conn.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (tid, employee_id, category, summary, priority, status, ts, ts, source, json.dumps(hist)))
        conn.commit()
    return get_ticket(tid, employee_id)


def get_ticket(tid, employee_id):
    """A ticket is returned only to the employee who owns it."""
    row = db().execute("SELECT * FROM tickets WHERE id=? AND employee_id=?", (tid.upper(), employee_id)).fetchone()
    if not row:
        return None
    t = dict(row)
    t["history"] = json.loads(t["history"])
    return t


def list_tickets(employee_id):
    rows = db().execute("SELECT * FROM tickets WHERE employee_id=? ORDER BY created_at DESC", (employee_id,)).fetchall()
    out = []
    for r in rows:
        t = dict(r)
        t["history"] = json.loads(t["history"])
        out.append(t)
    return out


def _seed_demo_tickets():
    """Each demo account starts with a few past tickets in different states (DEMO data)."""
    conn = _conn
    if conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]:
        return
    samples = [("Leave", "EL credit for August not reflected on NPP", "Resolved"),
               ("Payroll", "Query on professional tax deduction in payslip", "In Progress"),
               ("Benefits", "Add spouse to group medical insurance after marriage", "Awaiting Employee"),
               ("IT Access", "Access to client VDI for new project", "Closed"),
               ("Policy Clarification", "Is Holi a declared holiday at my location?", "Resolved")]
    rng = random.Random(7)
    for k, acc in enumerate(sorted(demo_accounts(), key=lambda a: a["employee_id"])):
        for j in rng.sample(range(len(samples)), 3):
            cat, summ, status = samples[j]
            created = (datetime.now(IST) - timedelta(days=rng.randint(3, 60))).isoformat(timespec="seconds")
            create_ticket(acc["employee_id"], cat, summ, source="portal", status=status, created=created)


# ---------------------------------------------------------------- answer cache
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
    with _lock:
        row = db().execute("SELECT response FROM cache WHERE key=?", (key,)).fetchone()
        if row:
            db().execute("UPDATE cache SET hits = hits + 1 WHERE key=?", (key,))
            db().commit()
    return json.loads(row["response"]) if row else None


def cache_put(key, response):
    if not config.CACHE_ENABLED:
        return
    with _lock:
        db().execute("INSERT OR REPLACE INTO cache(key, response, created_at) VALUES (?,?,?)",
                     (key, json.dumps(response), time.time()))
        db().commit()


# ---------------------------------------------------------------- anonymised logs and insights
def log_turn(route, topic, latency_ms, provider, usage, confidence, cache_hit, question, citations):
    qhash = hashlib.sha256(normalise_question(question).encode()).hexdigest()[:16]
    with _lock:
        db().execute("INSERT INTO logs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (time.time(), route, topic, int(latency_ms), provider, (usage or {}).get("in", 0),
                      (usage or {}).get("out", 0), confidence, int(bool(cache_hit)), qhash, citations))
        db().commit()


def insights():
    """Aggregates only: never message text (there is none stored)."""
    c = db()
    total = c.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    rows = lambda sql: [dict(r) for r in c.execute(sql).fetchall()]  # noqa: E731
    return {
        "total_questions": total,
        "by_route": rows("SELECT route, COUNT(*) AS n FROM logs GROUP BY route ORDER BY n DESC"),
        "by_topic": rows("SELECT topic, COUNT(*) AS n FROM logs WHERE topic IS NOT NULL GROUP BY topic ORDER BY n DESC"),
        "unanswered_topics": rows("SELECT topic, COUNT(*) AS n FROM logs WHERE route='not_found' AND topic IS NOT NULL "
                                  "GROUP BY topic ORDER BY n DESC LIMIT 8"),
        "cache_hit_rate": (c.execute("SELECT AVG(cache_hit) FROM logs WHERE route IN ('answer','not_found','clarify')")
                           .fetchone()[0] or 0),
        "avg_latency_ms": c.execute("SELECT AVG(latency_ms) FROM logs WHERE cache_hit=0").fetchone()[0] or 0,
        "by_provider": rows("SELECT provider, COUNT(*) AS n FROM logs WHERE provider IS NOT NULL GROUP BY provider"),
        "daily": rows("SELECT date(ts, 'unixepoch', '+5 hours', '+30 minutes') AS day, COUNT(*) AS n FROM logs "
                      "GROUP BY day ORDER BY day DESC LIMIT 14"),
        "repeat_questions": c.execute("SELECT COUNT(*) FROM (SELECT question_hash FROM logs GROUP BY question_hash "
                                      "HAVING COUNT(*) > 1)").fetchone()[0],
        "tickets_by_category": rows("SELECT category, COUNT(*) AS n FROM tickets WHERE source='chat' GROUP BY category"),
    }

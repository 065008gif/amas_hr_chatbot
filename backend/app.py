"""FastAPI app for Nia and the Nexora HR portal (DEMO: fictional company, fictional employees).

Run locally from ~/hrbot:   uvicorn backend.app:app --port 8000
Deployed on a Hugging Face Space (port 7860) in Phase 8.

The signed-in demo employee is sent in the X-Employee-Id header. Only the demo accounts in
data/employees.csv can sign in, and every personal endpoint serves only that employee's own data.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend import config, llm, store
from backend import chat as chatmod

app = FastAPI(title="Nia - Nexora HR assistant (demo)", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_origin_regex=config.CORS_ORIGIN_REGEX,
                   allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "X-Employee-Id"])

STATE = {"started": time.time(), "ready": False, "warm_error": None, "warm_seconds": None}
_warm_lock = threading.Lock()


def _warm():
    """Load the index, both local models and storage once per instance (idempotent)."""
    with _warm_lock:
        if STATE["ready"]:
            return
        t = time.perf_counter()
        try:
            r = chatmod.retriever()
            r.search("warm-up: annual leave entitlement")
            store.db()
            STATE["ready"], STATE["warm_error"] = True, None
        except Exception as e:  # reported by /health
            STATE["warm_error"] = f"{type(e).__name__}: {e}"
        STATE["warm_seconds"] = round(time.perf_counter() - t, 2)


def ensure_ready():
    """Warm up on the first request that needs data. Serverless (Vercel) and mounted apps
    (api/index.py) get no start-up hook, so this is the path that always works."""
    if not STATE["ready"]:
        _warm()


@app.on_event("startup")
def startup():
    # Only when this app is served directly by a long-running server (uvicorn backend.app:app).
    threading.Thread(target=_warm, daemon=True).start()


# ------------------------------------------------------------------ helpers
_hits = defaultdict(deque)


def rate_limited(ip):
    q, now = _hits[ip], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MINUTE:
        return True
    q.append(now)
    return False


def demo_employee(emp_id):
    e = store.employee(emp_id)
    if not e or e["demo_account"] != "yes":
        raise HTTPException(401, "Choose one of the demo employees to sign in (demo data).")
    return e


def not_ready():
    return JSONResponse({"detail": "Nia is warming up, please try again in a few seconds.", "warming_up": True},
                        status_code=503)


# ------------------------------------------------------------------ models
class Msg(BaseModel):
    role: str
    content: str = Field(max_length=4000)
    query: str | None = None
    route: str | None = None


class ChatIn(BaseModel):
    message: str = Field(max_length=4000)
    profile: dict | None = None
    history: list[Msg] = Field(default_factory=list, max_length=60)


class TicketIn(BaseModel):
    category: str
    summary: str = Field(min_length=3, max_length=300)
    priority: str = "Normal"


# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    ensure_ready()                   # the portal's "waking up" screen waits on this call
    idx = chatmod._retriever.index if chatmod._retriever else None
    return {
        "status": "ok" if STATE["ready"] else ("error" if STATE["warm_error"] else "warming_up"),
        "ready": STATE["ready"], "warm_seconds": STATE["warm_seconds"], "warm_error": STATE["warm_error"],
        "uptime_seconds": round(time.time() - STATE["started"]),
        "index": {"chunks": len(idx.chunks), "built": idx.meta.get("built"), "documents": len(idx.meta["documents"])} if idx else None,
        "providers": {"order": config.PROVIDER_ORDER, "gemini_models": config.GEMINI_MODELS, "status": llm.provider_status()},
        "storage": store.storage_info() if STATE["ready"] else None,
        "platform": "vercel" if config.ON_VERCEL else "local",
        "demo": True,
    }


@app.post("/chat")
def chat(body: ChatIn, request: Request, x_employee_id: str | None = Header(default=None)):
    ensure_ready()
    if not STATE["ready"]:
        return not_ready()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    if rate_limited(ip):
        return JSONResponse({"route": "error", "kind": "rate_limit", "answer": "You're sending messages quickly. Please wait "
                             "a few seconds and try again.", "citations": [], "conflicts": [], "follow_ups": []}, status_code=429)
    emp = store.employee(x_employee_id) if x_employee_id else None
    emp_id = emp["employee_id"] if emp and emp["demo_account"] == "yes" else None
    resp = chatmod.handle_turn(body.message, emp_id, body.profile, [m.model_dump() for m in body.history])
    resp.pop("_topic", None)
    return resp


@app.get("/demo-employees")
def demo_employees():
    return {"demo_data": True, "employees": store.demo_accounts()}


@app.get("/me")
def me(x_employee_id: str | None = Header(default=None)):
    e = demo_employee(x_employee_id)
    return {"demo_data": True, **{k: e[k] for k in ("employee_id", "name", "grade", "designation", "location", "join_date")}}


@app.get("/leave-balance")
def leave_balance(x_employee_id: str | None = Header(default=None)):
    e = demo_employee(x_employee_id)
    return store.leave_balance(e["employee_id"])


@app.post("/ticket")
def create_ticket(body: TicketIn, x_employee_id: str | None = Header(default=None)):
    e = demo_employee(x_employee_id)
    if body.category not in config.TICKET_CATEGORIES:
        raise HTTPException(422, f"category must be one of {config.TICKET_CATEGORIES}")
    return store.create_ticket(e["employee_id"], body.category, body.summary, body.priority, source="portal")


@app.get("/ticket/{ticket_id}")
def get_ticket(ticket_id: str, x_employee_id: str | None = Header(default=None)):
    e = demo_employee(x_employee_id)
    t = store.get_ticket(ticket_id, e["employee_id"])
    if not t:
        raise HTTPException(404, "No such ticket among your tickets.")
    return t


@app.get("/tickets")
def my_tickets(x_employee_id: str | None = Header(default=None)):
    e = demo_employee(x_employee_id)
    return {"tickets": store.list_tickets(e["employee_id"]), "categories": config.TICKET_CATEGORIES}


def _index():
    ensure_ready()
    if not chatmod._retriever:
        raise HTTPException(503, "Warming up")
    return chatmod._retriever.index


@app.get("/docs-list")
def docs_list():
    idx = _index()
    sections = defaultdict(dict)
    for c in idx.chunks:
        if c["section_no"] not in ("Front", "Circulars") and c["section_no"] not in sections[c["doc_id"]]:
            sections[c["doc_id"]][c["section_no"]] = {"no": c["section_no"], "title": c["section_title"], "page": c["page_start"]}
    circ = defaultdict(list)
    for c in idx.chunks:
        if c.get("circular_no"):
            circ[c["doc_id"]].append({"no": c["circular_no"], "subject": c.get("clause_title"),
                                      "effective": c.get("circular_effective"), "page": c["page_start"]})
    return {"documents": [{**{k: d[k] for k in ("doc_id", "title", "number", "version", "effective_date", "pages")},
                           "sections": list(sections[d["doc_id"]].values()), "circulars": circ[d["doc_id"]]}
                          for d in idx.meta["documents"]],
            "fictional": True}


@app.get("/circulars")
def circulars(limit: int = 6):
    idx = _index()
    out = [{"no": c["circular_no"], "subject": c.get("clause_title"), "effective": c.get("circular_effective"),
            "issued": c.get("circular_issued"), "doc_id": c["doc_id"], "document": c["title"], "page": c["page_start"],
            "amends": c.get("amends", [])} for c in idx.chunks if c.get("circular_no")]
    out.sort(key=lambda x: x["effective"] or "", reverse=True)
    return {"circulars": out[:max(1, min(limit, 20))]}


@app.get("/pdf/{doc_id}")
def pdf(doc_id: str):
    idx = _index()
    d = next((d for d in idx.meta["documents"] if d["doc_id"] == doc_id), None)
    if not d:
        raise HTTPException(404, "Unknown document")
    return FileResponse(config.DOCUMENTS_DIR / d["pdf"], media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{d["pdf"]}"', "Cache-Control": "public, max-age=86400"})


@app.get("/insights")
def insights():
    return {"demo": True, "note": "Aggregates from anonymised logs; no message text is stored.", **store.insights()}

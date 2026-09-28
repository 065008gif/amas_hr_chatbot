"""One chat turn, end to end.

    response = handle_turn(message, employee_id, profile, history)

Order: limits -> safety screen (no model call) -> tools -> follow-up rewrite / clarification merge
-> answer cache -> retrieval + confidence gate (no model call below the threshold) -> answer model
-> post-verification -> anonymised log. At most 2 model calls per turn: an optional JSON intent and
rewrite call for ambiguous follow-ups, and the answer call.
"""
import json
import re
import time

from backend import answer as ans
from backend import config, llm, safety, store
from backend.retrieve import COMPANY_CITIES, FOLLOWUP_START_RE, GRADE_Q_RE, Retriever, rewrite_followup, city_name, CITY_RE

_retriever = None

INTENT_PROMPT = """You classify one message sent to an HR helpdesk assistant and rewrite follow-ups.
Return ONLY JSON: {"intent": "policy_question" | "leave_balance" | "ticket_status" | "create_ticket" | "smalltalk" | "off_topic",
"standalone_question": "<the message rewritten as a complete question using the conversation, or the message itself if already complete>"}
Rules: keep the employee's meaning; do not answer; do not add facts; carry over grade, location, leave type and topic from the conversation when the message refers back to them (for example "what about L7?")."""

RATE_MSG = "The free model limit was reached, please try again shortly."
BUSY_MSG = "The AI service is busy right now, please try again in a minute."


def retriever():
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def _base(route, answer, **kw):
    out = {"route": route, "answer": answer, "citations": [], "confidence": None, "conflicts": [],
           "ticket_offer": None, "follow_ups": [], "tool_result": None, "standalone_query": None,
           "profile": None, "cache_hit": False, "provider": None, "kind": None, "escalation": None}
    out.update(kw)
    return out


def _profile_from(text, profile):
    """Grade and location only (never sensitive details), learned from what the employee says."""
    p = dict(profile or {})
    g = GRADE_Q_RE.search(text)
    if g:
        p["grade"] = f"L{g.group(1)}"
    loc = [city_name(m) for m in CITY_RE.findall(text)]
    loc = [c for c in loc if c in COMPANY_CITIES]
    if loc:
        p["location"] = loc[0]
    return p


def _standalone(message, history):
    """Return (standalone question, model usage or None)."""
    users = [m for m in history if m["role"] == "user"]
    last_bot = next((m for m in reversed(history) if m["role"] == "assistant"), None)
    # Answering Nia's clarifying question: merge the reply into the question that was asked.
    if last_bot and last_bot.get("route") == "clarify" and users:
        prev_q = users[-1].get("query") or users[-1]["content"]
        return f"{prev_q} ({message.strip()})", None
    prev = [u.get("query") or u["content"] for u in users]
    if not prev:
        return message, None
    ruled = rewrite_followup(message, prev)
    ambiguous = ruled == message and (FOLLOWUP_START_RE.match(message) or
                                      re.search(r"\b(it|that|this|those|they|them|same)\b", message, re.I))
    if not ambiguous:
        return ruled, None
    convo = "\n".join(f"{'Employee' if m['role'] == 'user' else 'Nia'}: {m['content'][:300]}" for m in history[-4:])
    try:
        text, _, usage = llm.chat(INTENT_PROMPT, [{"role": "user", "content": f"Conversation:\n{convo}\n\nMessage: {message}"}],
                                  json_mode=True)
        data = json.loads(re.search(r"\{.*\}", text, re.S).group())
        q = str(data.get("standalone_question") or "").strip()
        return (q if 5 < len(q) < 400 else ruled), usage
    except Exception:
        return ruled, None           # the rule-based rewrite is the fallback


def _tool(screen, message, employee_id):
    if not store.employee(employee_id):
        return _base("refused", "Please choose a demo employee in the portal first, so I know whose data to show.")
    if screen.category == "leave_balance":
        lb = store.leave_balance(employee_id)
        parts = ", ".join(f"{b['code']} {b['balance']:g}" for b in lb["balances"])
        return _base("tool", f"Here is your leave balance as of {lb['as_of']} (demo data): {parts}.", kind="leave_balance",
                     tool_result={"type": "leave_balance", "data": lb})
    if screen.category == "ticket_status":
        tid = safety.TICKET_ID_RE.search(message).group().upper()
        t = store.get_ticket(tid, employee_id)
        if not t:
            return _base("tool", f"I couldn't find ticket {tid} among your tickets. I can only show tickets you raised.",
                         kind="ticket_status", tool_result={"type": "ticket", "data": None})
        return _base("tool", f"Ticket {t['id']} ({t['category']}) is {t['status']}. Last updated {t['updated_at'][:10]}.",
                     kind="ticket_status", tool_result={"type": "ticket", "data": t})
    if screen.category == "ticket_list":
        ts = store.list_tickets(employee_id)
        return _base("tool", f"You have {len(ts)} ticket(s). The most recent are shown below.", kind="ticket_list",
                     tool_result={"type": "ticket_list", "data": ts[:5]})
    if screen.category == "create_ticket":
        text = re.sub(safety.RAISE_TICKET, "", message).strip(" :,-.") or message
        hits = retriever().search(text).hits if len(text.split()) > 2 else []
        cat = ans.ticket_category_for(hits, text) if hits else "Other"
        t = store.create_ticket(employee_id, cat, text if len(text) > 8 else message, source="chat")
        return _base("tool", f"I've raised ticket {t['id']} in the {t['category']} category. HR will reply on the NPP; "
                             f"you can ask me for its status any time.", kind="create_ticket",
                     tool_result={"type": "ticket", "data": t})
    return None


def handle_turn(message, employee_id=None, profile=None, history=None):
    t0 = time.perf_counter()
    history = history or []
    message = (message or "").strip()
    usage_total = {"in": 0, "out": 0}
    provider = None

    def done(resp, topic=None, question=message):
        resp["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        resp["usage"] = dict(usage_total)                # model tokens for this turn (0 when no model call)
        store.log_turn(resp["route"], topic, resp["latency_ms"], resp.get("provider"), usage_total,
                       resp.get("confidence"), resp.get("cache_hit"), question, len(resp["citations"]))
        return resp

    if not message:
        return _base("clarify", "Please type a question about Nexora's HR policies.")
    if len(message) > config.MAX_MESSAGE_CHARS:
        return done(_base("refused", f"Please keep messages under {config.MAX_MESSAGE_CHARS} characters.", kind="limit"))
    if sum(m["role"] == "user" for m in history) >= config.MAX_TURNS:
        return done(_base("refused", "This chat has reached its limit of 20 questions. Please start a new chat.", kind="limit"))

    profile = _profile_from(message, profile)
    sc = safety.screen(message, employee_id)
    mode = "policy"
    if sc:
        if sc.kind == "distress":
            return done(_base("escalate", sc.reply, kind="distress", profile=profile,
                              escalation={"category": "distress", "channels": [config.CONTACTS["eap"], config.CRISIS_LINES]}))
        if sc.kind in ("refused", "smalltalk"):
            return done(_base("refused" if sc.kind == "refused" else "answer", sc.reply, kind=sc.category, profile=profile))
        if sc.kind == "tool":
            r = _tool(sc, message, employee_id)
            r["profile"] = profile
            return done(r)
        if sc.kind == "escalate" and not sc.allow_policy_answer:
            return done(_base("escalate", sc.reply, kind=sc.category, profile=profile,
                              escalation={"category": sc.category},
                              ticket_offer={"category": sc.ticket_category, "summary": f"Confidential: {sc.category.replace('_', ' ')} concern",
                                            "priority": "High"}))
        if sc.kind == "escalate":
            mode = "posh_process"

    # ---- policy question ----
    query, u = _standalone(message, history)
    if u:
        usage_total["in"] += u.get("in", 0)
        usage_total["out"] += u.get("out", 0)
    key = store.cache_key(query + ("|posh" if mode == "posh_process" else ""), profile)
    cached = store.cache_get(key)
    if cached:
        cached.update(cache_hit=True, profile=profile, standalone_query=query)
        return done(cached, cached.get("_topic"), query)

    res = retriever().search(query, profile=profile)
    topic = ans.topic_of(res.hits)
    if not res.confident and mode != "posh_process":
        r = _base("not_found", "I couldn't find anything about this in Nexora's HR policy documents, so I won't guess. "
                               "I can raise a ticket so a person in HR can help.",
                  confidence=res.confidence, standalone_query=query, profile=profile,
                  ticket_offer={"category": "Policy Clarification", "summary": query[:200], "priority": "Normal"},
                  follow_ups=["What is my leave balance?", "Raise a ticket for this question"])
        r["_topic"] = "Not covered"
        store.cache_put(key, r)
        return done(r, "Not covered", query)

    system, msgs = ans.build_messages(query, res.hits, profile, history, mode)
    try:
        text, provider, u = llm.chat(system, msgs, json_mode=True)
        usage_total["in"] += u.get("in", 0)
        usage_total["out"] += u.get("out", 0)
    except llm.LLMError as e:
        # Graceful degradation: no model, but still point to the most relevant verified sections.
        top = [ans.make_citation(f"S{i}", h, query, retriever().index.pages) for i, h in enumerate(res.hits[:3], start=1)]
        return done(_base("error", (RATE_MSG if e.kind == "rate_limit" else BUSY_MSG) +
                          " Meanwhile, these policy sections look most relevant:", citations=top,
                          confidence=res.confidence, standalone_query=query, profile=profile, kind=e.kind), topic, query)
    parsed = ans.parse_json(text)
    if parsed is None:
        parsed = {"route": "not_found", "answer": ""}
    route, answer_text, cits, conflicts, follow, notes = ans.verify(parsed, res.hits, query, retriever().index.pages, profile)
    if route == "not_found" and not answer_text:
        answer_text = "I couldn't find this in Nexora's HR policy documents, so I won't guess."
    r = _base(route, answer_text, citations=cits, confidence=res.confidence, conflicts=conflicts, follow_ups=follow,
              standalone_query=query, profile=profile, provider=provider, verification=notes)
    if route == "not_found":
        r["ticket_offer"] = {"category": ans.ticket_category_for(res.hits, query), "summary": query[:200], "priority": "Normal"}
        topic = f"{topic} (not covered)" if topic else "Not covered"
    if mode == "posh_process":
        r["route"] = "escalate"
        r["kind"] = "posh"
        r["escalation"] = {"category": "posh", "channels": [config.CONTACTS["internal_committee"], config.CONTACTS["eap"]]}
        r["answer"] = sc.reply + ("\n\nWhat the POSH Policy says about the process:\n" + answer_text if route == "answer" else "")
        r["ticket_offer"] = {"category": "POSH/Grievance", "summary": "Confidential: request to speak to the Internal Committee",
                             "priority": "High"}
    r["_topic"] = topic
    store.cache_put(key, r)
    return done(r, topic, query)

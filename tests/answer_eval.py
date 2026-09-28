"""Phase 7 answer evaluation (D-043). Resumable: safe to stop and re-run at any time.

  python tests/answer_eval.py --limit 25          # answer the next 25 unanswered items, then stop
  python tests/answer_eval.py --only T01,Q04      # (re)run specific items
  python tests/answer_eval.py --score             # score everything collected so far -> answer_eval.{json,md}

Runs the real backend in-process (retrieval, safety screen, model call, post-verification) with the answer
cache OFF, so every answer is fresh and costs quota. Each result is appended to
tests/results/answer_eval_runs.jsonl as soon as it arrives; items already there are skipped. Logs and
tickets go to a separate SQLite file (data/runtime/eval/), so the portal's HR Insights are not affected.
The run stops by itself after 3 consecutive provider failures (for example a free-tier limit), so the rest
can be run later.
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HRBOT_RUNTIME_DIR", str(ROOT / "data" / "runtime" / "eval"))
for k in ("KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
    os.environ.pop(k, None)                       # never write evaluation traffic to the live Redis
sys.path.insert(0, str(ROOT / "tests"))
from evalkit import RESULTS, facts_matched, load_set  # noqa: E402

RUNS = RESULTS / "answer_eval_runs.jsonl"
BUSY_MARK = "busy"                                 # the graceful "AI service is busy" reply


def load_runs():
    runs = {}
    if RUNS.exists():
        for line in RUNS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                runs[r["id"]] = r                  # last run of an id wins
    return runs


def slim(resp):
    return {k: resp.get(k) for k in ("route", "kind", "answer", "confidence", "provider", "latency_ms", "usage",
                                      "standalone_query", "ticket_offer", "escalation", "follow_ups")} | {
        "citations": [{k: c.get(k) for k in ("id", "doc_id", "document", "page", "clause", "label", "snippet", "verified")}
                      for c in resp.get("citations") or []],
        "conflicts": resp.get("conflicts") or []}


def provider_failed(resp):
    return resp.get("route") == "error" or (not resp.get("provider") and resp.get("route") == "answer"
                                             and BUSY_MARK in (resp.get("answer") or "").lower())


def run(items, sleep):
    from backend import config
    config.CACHE_ENABLED = False
    from backend.chat import handle_turn
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    fails = 0
    for i, it in enumerate(items, 1):
        t0 = time.time()
        try:
            resp = handle_turn(it["q"], employee_id=None, profile=it.get("profile"), history=[])
        except Exception as e:  # noqa: BLE001 - record the failure and keep going
            resp = {"route": "error", "answer": f"{type(e).__name__}: {e}"}
        rec = {"id": it["id"], "q": it["q"], "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "wall_s": round(time.time() - t0, 2)} | slim(resp)
        with RUNS.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        ok = "" if rec["route"] in it["routes"] else f"  (expected {'/'.join(it['routes'])})"
        print(f"[{i}/{len(items)}] {it['id']:4} {rec['route']:9} {rec.get('provider') or '-':7} {rec.get('latency_ms') or 0:>6} ms{ok}")
        fails = fails + 1 if provider_failed(resp) else 0
        if fails >= 3:
            print("Stopping: 3 provider failures in a row (free-tier limit or outage). Re-run later to resume.")
            break
        if resp.get("provider"):
            time.sleep(sleep)                      # pace model calls for the free tier


# ------------------------------------------------------------------ scoring
def score_item(it, r):
    """Return (verdict, detail). Verdicts: correct, partly, wrong, correctly_refused, wrongly_refused,
    hallucinated (answered an unanswerable question), clarify_ok, answered_without_clarifying,
    escalated_ok, missed_escalation."""
    route = r["route"]
    text = r.get("answer") or ""
    matched = facts_matched(it.get("facts"), text)
    exp = set(it["routes"])
    if it["cat"] == "escalation":
        return ("escalated_ok" if route in exp else "missed_escalation"), {}
    if exp == {"not_found"}:
        return ("correctly_refused" if route == "not_found" else "hallucinated"), {}
    if exp == {"clarify"}:
        if route == "clarify":
            return "clarify_ok", {}
        return ("answered_without_clarifying" if route == "answer" else "wrongly_refused"), {}
    if route in ("not_found", "clarify", "refused") and route not in exp:
        return "wrongly_refused", {"route": route}
    if route not in exp:
        return "wrong", {"route": route}
    if matched and all(matched):
        return "correct", {"facts": matched}
    return ("partly" if any(matched) else "wrong"), {"facts": matched}


def snippet_on_page(snippet, page_text):
    """Prose snippets must appear on the page word for word (first 120 characters). Table rows are quoted as
    "Header: value | Header: value", which the PDF lays out in columns with wrapped cells, so for them every
    word of every cell value must be on the page."""
    from evalkit import norm
    snip = norm(snippet)
    if not snip:
        return False
    cells = [part.split(": ", 1)[1] for part in snip.split(" | ") if ": " in part]
    if " | " in snip and cells:
        words = set(re.findall(r"[a-z0-9.%/-]+", page_text))
        return all(set(re.findall(r"[a-z0-9.%/-]+", c)) <= words for c in cells)
    return snip[:120] in page_text


def citation_checks(it, r, pages):
    """Independent citation accuracy: re-read the cited PDF page and look for the cited snippet, and
    check whether any citation points at a gold evidence page."""
    from evalkit import norm
    out = []
    for c in r.get("citations") or []:
        doc = pages.get(c.get("doc_id"), [])
        p = c.get("page") or 0
        text = doc[p - 1] if 0 < p <= len(doc) else ""
        out.append(snippet_on_page(c.get("snippet") or "", text))
    gold = {(e["doc"], e["page"]) for e in it.get("evidence") or []}
    on_gold = any((c.get("doc_id"), c.get("page")) in gold for c in r.get("citations") or [])
    return out, on_gold


def score(data, runs):
    sys.path.insert(0, str(ROOT / "tests"))
    from check_eval_set import pdf_pages
    pages, _ = pdf_pages()
    rows, by_cat = [], defaultdict(Counter)
    cite_total = cite_ok = gold_hit = gold_n = 0
    for it in data["singles"]:
        r = runs.get(it["id"])
        if not r:
            continue
        verdict, detail = score_item(it, r)
        cites, on_gold = citation_checks(it, r, pages)
        cite_total += len(cites)
        cite_ok += sum(cites)
        if r["route"] in ("answer", "escalate") and it.get("evidence") and verdict in ("correct", "partly"):
            gold_n += 1
            gold_hit += on_gold
        by_cat[it["cat"]][verdict] += 1
        rows.append({"id": it["id"], "cat": it["cat"], "q": it["q"], "expected": it["routes"], "route": r["route"],
                     "verdict": verdict, "facts": detail.get("facts"), "citations": len(cites),
                     "citations_on_page": sum(cites), "cites_gold_page": on_gold, "provider": r.get("provider"),
                     "latency_ms": r.get("latency_ms"), "answer": r.get("answer")})
    v = Counter(x["verdict"] for x in rows)
    unans = [x for x in rows if x["expected"] == ["not_found"]]
    refused = [x for x in rows if x["route"] == "not_found"]
    summary = {
        "items_scored": len(rows), "items_in_set": len(data["singles"]), "verdicts": dict(v),
        "by_category": {k: dict(c) for k, c in sorted(by_cat.items())},
        "answerable_accuracy": _ratio(v["correct"], sum(v[k] for k in ("correct", "partly", "wrong", "wrongly_refused"))),
        "answerable_correct_or_partly": _ratio(v["correct"] + v["partly"], sum(v[k] for k in ("correct", "partly", "wrong", "wrongly_refused"))),
        "citation_snippet_on_cited_page": _ratio(cite_ok, cite_total),
        "correct_answers_citing_a_gold_page": _ratio(gold_hit, gold_n),
        # refusal = route not_found; a refusal is "right" when the item is unanswerable
        "refusal_precision": _ratio(sum(1 for x in refused if x["expected"] == ["not_found"]), len(refused)),
        "refusal_recall": _ratio(sum(1 for x in unans if x["route"] == "not_found"), len(unans)),
        "escalation_recall": _ratio(v["escalated_ok"], v["escalated_ok"] + v["missed_escalation"]),
        "clarify_rate": _ratio(v["clarify_ok"], v["clarify_ok"] + v["answered_without_clarifying"] + sum(1 for x in rows if x["cat"] == "clarify" and x["verdict"] == "wrongly_refused")),
        "providers": dict(Counter(x["provider"] or "none (no model call)" for x in rows)),
        "scoring": "String checks against gold facts (tests/eval_set.yaml); no model is used as a judge.",
    }
    return summary, rows


def _ratio(a, b):
    return {"n": a, "of": b, "rate": round(a / b, 3) if b else None}


def write_reports(summary, rows):
    (RESULTS / "answer_eval.json").write_text(json.dumps({"summary": summary, "items": rows}, indent=1, ensure_ascii=False))
    L = ["# Answer evaluation (single questions)", "",
         f"Scored {summary['items_scored']} of {summary['items_in_set']} items. {summary['scoring']}", "",
         "| Metric | Result |", "|---|---|"]
    for k in ("answerable_accuracy", "answerable_correct_or_partly", "citation_snippet_on_cited_page",
              "correct_answers_citing_a_gold_page", "refusal_precision", "refusal_recall", "escalation_recall", "clarify_rate"):
        x = summary[k]
        L.append(f"| {k.replace('_', ' ')} | {x['n']}/{x['of']}" + (f" ({x['rate']:.1%})" if x["rate"] is not None else "") + " |")
    L += ["", "## By category", "", "| Category | " + " | ".join(sorted({v for c in summary['by_category'].values() for v in c})) + " |"]
    cols = sorted({v for c in summary["by_category"].values() for v in c})
    L.append("|---" * (len(cols) + 1) + "|")
    for cat, c in summary["by_category"].items():
        L.append(f"| {cat} | " + " | ".join(str(c.get(col, 0)) for col in cols) + " |")
    L += ["", "## Items not fully correct", ""]
    for x in rows:
        if x["verdict"] not in ("correct", "correctly_refused", "clarify_ok", "escalated_ok"):
            L.append(f"- **{x['id']}** ({x['cat']}, {x['verdict']}, route {x['route']}, expected {'/'.join(x['expected'])}): "
                     f"{x['q']}  \n  Answer: {(x['answer'] or '')[:300].replace(chr(10), ' ')}")
    (RESULTS / "answer_eval.md").write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="run at most this many not-yet-run items")
    ap.add_argument("--only", default="", help="comma-separated ids to (re)run")
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between model calls")
    ap.add_argument("--score", action="store_true", help="score collected runs and write reports")
    args = ap.parse_args()
    data = load_set()
    runs = load_runs()
    if args.score:
        summary, rows = score(data, runs)
        write_reports(summary, rows)
        print(json.dumps({k: v for k, v in summary.items() if k != "by_category"}, indent=1))
        return
    if args.only:
        want = set(args.only.split(","))
        todo = [i for i in data["singles"] if i["id"] in want]
    else:
        todo = [i for i in data["singles"] if i["id"] not in runs]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(runs)} items already done; running {len(todo)} now (cache off, {args.sleep}s between model calls).")
    run(todo, args.sleep)


if __name__ == "__main__":
    main()

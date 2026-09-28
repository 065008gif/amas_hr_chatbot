"""Phase 4 check: retrieval quality on the traps (held-out TEST set) and tests/retrieval_dev.yaml (DEV set).

Run from ~/hrbot:   python tests/retrieval_eval.py

A chunk is "gold" for a question if it belongs to the evidence document and contains the evidence
quote (whitespace-normalised). Metrics are computed on the FINAL list given to the answer model
(top 8, including amending circulars):
  recall@k      share of questions with at least one gold chunk in the top k
  all-evidence  share of trap questions where EVERY evidence item (e.g. both sides of a conflict,
                or the clause and its circular) is in the top 8 - stricter than the brief asks
  MRR           mean of 1/rank of the first gold chunk (0 if none in the top 8)
The confidence threshold is tuned on the DEV set only, then applied unchanged to the traps.
Results are written to tests/results/retrieval_eval.json and .md.
"""
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import config, indexstore  # noqa: E402
from backend.retrieve import Retriever, rewrite_followup  # noqa: E402

RESULTS = ROOT / "tests" / "results"
VARIANTS = {   # name -> Retriever options; "full" is the configuration the chatbot uses
    "full": {},
    "no rerank": {"use_rerank": False},
    "no boosting": {"use_boost": False},
    "no circular rule": {"use_circulars": False},
    "BM25 only, no rerank": {"use_dense": False, "use_rerank": False, "use_boost": False, "use_circulars": False},
    "dense only, no rerank": {"use_bm25": False, "use_rerank": False, "use_boost": False, "use_circulars": False},
}


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def flat(chunk):
    """Chunk text as it reads on the page: table rows lose their "Header: " labels and "|"."""
    text = chunk["text"]
    if chunk["chunk_type"] == "table":
        text = re.sub(r"(^|\| |\n)[^|:\n]{1,60}: ", " ", text).replace(" | ", " ")
    return norm(text)


def gold_ids(chunks, doc, quote):
    q = norm(quote)
    return {c["chunk_id"] for c in chunks if c["doc_id"] == doc and (q in norm(c["text"]) or q in flat(c))}


def load_sets(chunks):
    """Return dev and test question lists: {id, q, groups: [set of acceptable chunk ids], answerable}."""
    dev = yaml.safe_load((ROOT / "tests" / "retrieval_dev.yaml").read_text())
    problems = []
    dev_qs = []
    for d in dev["answerable"]:
        ids = set().union(*(gold_ids(chunks, g["doc"], g["quote"]) for g in d["gold"]))
        if not ids:
            problems.append(f"dev {d['id']}: no chunk contains its gold quote")
        dev_qs.append({"id": d["id"], "q": d["q"], "groups": [ids], "answerable": True})
    for u in dev["unanswerable"]:
        for term in u["absent"]:
            found = [c["chunk_id"] for c in chunks if re.search(r"\b" + re.escape(term) + r"\b", c["text"], re.I)]
            if found:
                problems.append(f"dev {u['id']}: 'unanswerable' term {term!r} appears in {found[:2]}")
        dev_qs.append({"id": u["id"], "q": u["q"], "groups": [], "answerable": False})

    test_qs = []
    for t in json.loads((ROOT / "tests" / "traps.json").read_text()):
        groups = []
        for e in t.get("evidence", []):
            ids = gold_ids(chunks, e["doc_id"], e["quote"])
            if not ids:
                problems.append(f"trap {t['id']}: quote not found in any chunk: {e['quote'][:50]!r}")
            if ids not in groups:
                groups.append(ids)
        test_qs.append({"id": t["id"], "q": t["question"], "groups": groups, "type": t["type"],
                        "answerable": t["expected_route"] != "not_found"})
    return dev_qs, test_qs, dev["followups"], problems


def run(retriever, qs):
    out = []
    for q in qs:
        t = time.perf_counter()
        res = retriever.search(q["q"])
        ms = (time.perf_counter() - t) * 1000
        ids = [h.chunk["chunk_id"] for h in res.hits]
        gold = set().union(*q["groups"]) if q["groups"] else set()
        first = next((r for r, cid in enumerate(ids, start=1) if cid in gold), None)
        out.append({
            "id": q["id"], "q": q["q"], "answerable": q["answerable"], "type": q.get("type"),
            "first_gold_rank": first,
            "all_evidence": bool(q["groups"]) and all(g & set(ids) for g in q["groups"]),
            "confidence": res.confidence, "ms": round(ms, 1), "top": ids,
            "gold": sorted(gold),
        })
    return out


def metrics(rows):
    ans = [r for r in rows if r["answerable"]]
    n = len(ans)
    rec = {k: sum(1 for r in ans if r["first_gold_rank"] and r["first_gold_rank"] <= k) / n for k in (1, 3, 5, 8)}
    mrr = sum(1 / r["first_gold_rank"] for r in ans if r["first_gold_rank"]) / n
    return {"n": n, "recall@1": rec[1], "recall@3": rec[3], "recall@5": rec[5], "recall@8": rec[8],
            "MRR": mrr, "all_evidence@8": sum(r["all_evidence"] for r in ans) / n}


def tune_threshold(rows):
    """Threshold that best separates answerable from unanswerable (balanced accuracy) on DEV."""
    pos = [r["confidence"] for r in rows if r["answerable"]]
    neg = [r["confidence"] for r in rows if not r["answerable"]]
    best = None
    for t in sorted(set(pos + neg)):
        kept = sum(c >= t for c in pos) / len(pos)
        refused = sum(c < t for c in neg) / len(neg)
        score = (kept + refused) / 2
        if best is None or score > best[0] or (score == best[0] and t < best[1]):
            best = (score, t, kept, refused)
    # place the threshold midway between the chosen value and the next lower confidence
    lower = max([c for c in pos + neg if c < best[1]], default=0.0)
    return round((best[1] + lower) / 2, 4), best


def refusal_stats(rows, threshold):
    pos = [r for r in rows if r["answerable"]]
    neg = [r for r in rows if not r["answerable"]]
    return {
        "threshold": threshold,
        "answerable_kept": f"{sum(r['confidence'] >= threshold for r in pos)}/{len(pos)}",
        "unanswerable_refused": f"{sum(r['confidence'] < threshold for r in neg)}/{len(neg)}",
        "wrongly_refused": [r["id"] for r in pos if r["confidence"] < threshold],
        "wrongly_answered": [r["id"] for r in neg if r["confidence"] >= threshold],
    }


def main():
    index = indexstore.load_index()
    dev_qs, test_qs, followups, problems = load_sets(index.chunks)
    print(f"DEV: {sum(q['answerable'] for q in dev_qs)} answerable + {sum(not q['answerable'] for q in dev_qs)} "
          f"unanswerable.  TEST (traps): {sum(q['answerable'] for q in test_qs)} answerable + "
          f"{sum(not q['answerable'] for q in test_qs)} not covered.")
    for p in problems:
        print("  LABEL PROBLEM:", p)

    base = Retriever(index=index)
    base.embedder, base.reranker   # load both models once, shared by every variant
    report = {"run": datetime.now().isoformat(timespec="seconds"), "variants": {}}
    full_rows = {}
    print(f"\n{'variant':<24} {'DEV R@8':>8} {'DEV MRR':>8} {'TEST R@1':>9} {'TEST R@3':>9} {'TEST R@8':>9} "
          f"{'TEST MRR':>9} {'all-ev@8':>9}")
    for name, opts in VARIANTS.items():
        r = Retriever(index=index, **opts)
        r._embedder, r._reranker = base._embedder, base._reranker
        dev_rows, test_rows = run(r, dev_qs), run(r, test_qs)
        dm, tm = metrics(dev_rows), metrics(test_rows)
        report["variants"][name] = {"dev": dm, "test": tm}
        print(f"{name:<24} {dm['recall@8']:8.3f} {dm['MRR']:8.3f} {tm['recall@1']:9.3f} {tm['recall@3']:9.3f} "
              f"{tm['recall@8']:9.3f} {tm['MRR']:9.3f} {tm['all_evidence@8']:9.3f}")
        if name == "full":
            full_rows = {"dev": dev_rows, "test": test_rows}

    # Failures of the full configuration
    print("\nFull configuration - questions with NO gold chunk in the top 8:")
    fails = [(s, r) for s in ("dev", "test") for r in full_rows[s] if r["answerable"] and not r["first_gold_rank"]]
    for s, r in fails:
        print(f"  {s} {r['id']}: {r['q'][:80]}\n      gold {r['gold'][:3]}\n      got  {r['top'][:4]}")
    if not fails:
        print("  none")
    partial = [r for r in full_rows["test"] if r["answerable"] and r["first_gold_rank"] and not r["all_evidence"]]
    print(f"Traps with a gold chunk but not ALL evidence in the top 8: {[r['id'] for r in partial]}")

    # Confidence threshold: tuned on DEV, applied to TEST
    _, best = tune_threshold(full_rows["dev"])
    # Rule fixed in advance (D-035): 1/10 of the lowest answerable DEV confidence, so no DEV
    # question is wrongly refused; the answer model handles in-domain "not covered" questions.
    thr = round(min(r["confidence"] for r in full_rows["dev"] if r["answerable"]) / 10, 4)
    dev_ref, test_ref = refusal_stats(full_rows["dev"], thr), refusal_stats(full_rows["test"], thr)
    print(f"\nConfidence threshold from DEV (lowest answerable / 10): {thr}  "
          f"[for reference, best balanced-accuracy threshold would refuse answerable questions: {best[1]:.4f}]")
    print(f"  DEV : answerable kept {dev_ref['answerable_kept']}, unanswerable refused {dev_ref['unanswerable_refused']}; "
          f"wrongly refused {dev_ref['wrongly_refused']}, wrongly answered {dev_ref['wrongly_answered']}")
    print(f"  TEST: answerable kept {test_ref['answerable_kept']}, not-covered refused {test_ref['unanswerable_refused']}; "
          f"wrongly refused {test_ref['wrongly_refused']}, wrongly answered {test_ref['wrongly_answered']}")
    conf = {s: {"answerable": sorted(r["confidence"] for r in full_rows[s] if r["answerable"]),
                "unanswerable": sorted(r["confidence"] for r in full_rows[s] if not r["answerable"])}
            for s in ("dev", "test")}
    print(f"  lowest answerable confidences (dev): {conf['dev']['answerable'][:4]}; "
          f"highest unanswerable (dev): {conf['dev']['unanswerable'][-4:]}")
    if thr != config.CONFIDENCE_THRESHOLD:
        print(f"  NOTE: backend/config.py has CONFIDENCE_THRESHOLD = {config.CONFIDENCE_THRESHOLD}; tuned value is {thr}")

    # Follow-up rewriting
    print("\nFollow-up rewriting:")
    fu_pass = 0
    for f in followups:
        out = rewrite_followup(f["q"], f["history"])
        ok = out == f["expect"] if "expect" in f else all(w.lower() in out.lower() for w in f["expect_contains"])
        fu_pass += ok
        print(f"  {'PASS' if ok else 'FAIL'} {f['id']}: {f['q']!r} -> {out!r}")

    ms = [r["ms"] for s in ("dev", "test") for r in full_rows[s]]
    print(f"\nLatency per search (full, this PC): median {statistics.median(ms):.0f} ms, "
          f"95th percentile {sorted(ms)[int(0.95 * len(ms)) - 1]:.0f} ms")

    report.update({
        "threshold": {"tuned_on": "dev", "value": thr, "dev": dev_ref, "test": test_ref, "confidences": conf},
        "followups": f"{fu_pass}/{len(followups)}",
        "failures": [{"set": s, **r} for s, r in fails],
        "latency_ms": {"median": statistics.median(ms), "p95": sorted(ms)[int(0.95 * len(ms)) - 1]},
        "per_question": full_rows, "label_problems": problems,
    })
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "retrieval_eval.json").write_text(json.dumps(report, indent=1))
    write_markdown(report)
    tm = report["variants"]["full"]["test"]
    print(f"\nTEST recall@8 = {tm['recall@8']:.3f} (target 0.9), MRR = {tm['MRR']:.3f}.  "
          f"RESULT: {'PASS' if tm['recall@8'] >= 0.9 and not problems else 'BELOW TARGET'}")


def write_markdown(rep):
    lines = [f"# Retrieval evaluation ({rep['run']})", "",
             "Generated by `python tests/retrieval_eval.py`. TEST = the traps in `tests/traps.json` "
             "(held out); DEV = `tests/retrieval_dev.yaml` (used for tuning).", "",
             "| Variant | DEV recall@8 | DEV MRR | TEST recall@1 | TEST recall@3 | TEST recall@8 | TEST MRR | TEST all-evidence@8 |",
             "|---|---|---|---|---|---|---|---|"]
    for name, v in rep["variants"].items():
        d, t = v["dev"], v["test"]
        lines.append(f"| {name} | {d['recall@8']:.3f} | {d['MRR']:.3f} | {t['recall@1']:.3f} | {t['recall@3']:.3f} | "
                     f"{t['recall@8']:.3f} | {t['MRR']:.3f} | {t['all_evidence@8']:.3f} |")
    th = rep["threshold"]
    lines += ["", f"**Confidence threshold** (tuned on DEV): {th['value']}", "",
              f"- DEV: answerable kept {th['dev']['answerable_kept']}, unanswerable refused {th['dev']['unanswerable_refused']}",
              f"- TEST: answerable kept {th['test']['answerable_kept']}, not-covered refused {th['test']['unanswerable_refused']}",
              f"- wrongly refused: DEV {th['dev']['wrongly_refused']}, TEST {th['test']['wrongly_refused']}",
              f"- wrongly answered: DEV {th['dev']['wrongly_answered']}, TEST {th['test']['wrongly_answered']}",
              "", f"**Follow-up rewriting:** {rep['followups']} cases pass.", "",
              f"**Latency per search:** median {rep['latency_ms']['median']:.0f} ms, "
              f"95th percentile {rep['latency_ms']['p95']:.0f} ms (this PC).", "", "## Failures (no gold chunk in top 8)", ""]
    lines += [f"- {f['set']} {f['id']}: {f['q']}" for f in rep["failures"]] or ["- none"]
    (RESULTS / "retrieval_eval.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

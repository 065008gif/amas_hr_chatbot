"""Phase 7 multi-turn (F1, F6) and paraphrase-consistency (F7) evaluation (D-044). Resumable.

  python tests/multiturn_eval.py --part conversations --limit 10   # next 10 conversations (3 turns each)
  python tests/multiturn_eval.py --part paraphrases --limit 20     # next 20 pairs (2 questions each)
  python tests/multiturn_eval.py --score                           # -> multiturn_eval.{json,md}

Same conditions as answer_eval.py: backend in-process, answer cache off, separate log database, results
appended per conversation / pair to tests/results/multiturn_runs.jsonl. A conversation sends each turn with
the previous turns as history and the profile learned so far, as the portal does.
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import answer_eval as ae  # noqa: E402  (sets up the evaluation environment on import)
from evalkit import RESULTS, facts_matched, load_set  # noqa: E402

RUNS = RESULTS / "multiturn_runs.jsonl"


def load_runs():
    out = {}
    if RUNS.exists():
        for line in RUNS.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r
    return out


def _turn(handle_turn, q, history, profile):
    try:
        return handle_turn(q, employee_id=None, profile=profile, history=history)
    except Exception as e:  # noqa: BLE001
        return {"route": "error", "answer": f"{type(e).__name__}: {e}"}


def run(part, todo, sleep):
    from backend import config
    config.CACHE_ENABLED = False
    from backend.chat import handle_turn
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    fails = 0
    for i, unit in enumerate(todo, 1):
        rec = {"id": unit["id"], "part": part, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "responses": []}
        if part == "conversations":
            history, profile = [], None
            for t in unit["turns"]:
                resp = _turn(handle_turn, t["q"], history, profile)
                rec["responses"].append({"q": t["q"]} | ae.slim(resp) | {"profile": resp.get("profile")})
                history += [{"role": "user", "content": t["q"], "query": resp.get("standalone_query")},
                            {"role": "assistant", "content": (resp.get("answer") or "")[:1000], "route": resp.get("route")}]
                history = history[-8:]
                profile = resp.get("profile") or profile
                fails = fails + 1 if ae.provider_failed(resp) else 0
                if resp.get("provider"):
                    time.sleep(sleep)
        else:
            for q in (unit["a"], unit["b"]):
                resp = _turn(handle_turn, q, [], None)
                rec["responses"].append({"q": q} | ae.slim(resp))
                fails = fails + 1 if ae.provider_failed(resp) else 0
                if resp.get("provider"):
                    time.sleep(sleep)
        with RUNS.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(todo)}] {unit['id']:4} " + " | ".join(f"{r['route']}" for r in rec["responses"]))
        if fails >= 3:
            print("Stopping: 3 provider failures in a row. Re-run later to resume.")
            break


def score(data, runs):
    conv_rows, by_kind, turn_pos = [], defaultdict(Counter), defaultdict(Counter)
    for c in data.get("conversations") or []:
        r = runs.get(c["id"])
        if not r:
            continue
        verdicts = []
        for n, (t, resp) in enumerate(zip(c["turns"], r["responses"]), 1):
            cat = "clarify" if t["routes"] == ["clarify"] else "conversation"
            v, _ = ae.score_item(t | {"cat": cat}, resp)
            good = v in ("correct", "clarify_ok", "correctly_refused", "escalated_ok")
            verdicts.append(v)
            by_kind[c["kind"]]["turns"] += 1
            by_kind[c["kind"]]["turns_correct"] += good
            turn_pos[n]["n"] += 1
            turn_pos[n]["correct"] += good
        full = all(v in ("correct", "clarify_ok", "correctly_refused", "escalated_ok") for v in verdicts)
        by_kind[c["kind"]]["conversations"] += 1
        by_kind[c["kind"]]["fully_correct"] += full
        conv_rows.append({"id": c["id"], "kind": c["kind"], "verdicts": verdicts, "fully_correct": full,
                          "turns": [{"q": resp["q"], "route": resp["route"], "rewritten": resp.get("standalone_query"),
                                     "answer": resp.get("answer")} for resp in r["responses"]]})
    pair_rows = []
    for p in data.get("paraphrases") or []:
        r = runs.get(p["id"])
        if not r:
            continue
        a, b = r["responses"]
        fa, fb = (all(facts_matched(p.get("facts"), x.get("answer") or "")) if p.get("facts") else None for x in (a, b))
        same_route = a["route"] == b["route"]
        same_facts = fa == fb
        exp_ok = [x["route"] in p["routes"] and (fx is None or fx) for x, fx in ((a, fa), (b, fb))]
        pair_rows.append({"id": p["id"], "routes": [a["route"], b["route"]], "facts_ok": [fa, fb], "same_route": same_route,
                          "consistent": same_route and same_facts, "both_correct": all(exp_ok),
                          "a": p["a"], "b": p["b"], "answers": [a.get("answer"), b.get("answer")]})
    R = ae._ratio
    summary = {
        "conversations_scored": len(conv_rows),
        "conversations_fully_correct": R(sum(x["fully_correct"] for x in conv_rows), len(conv_rows)),
        "turn_accuracy_by_position": {n: R(c["correct"], c["n"]) for n, c in sorted(turn_pos.items())},
        "by_kind": {k: {"turns_correct": R(c["turns_correct"], c["turns"]), "fully_correct": R(c["fully_correct"], c["conversations"])}
                    for k, c in sorted(by_kind.items())},
        "pairs_scored": len(pair_rows),
        "paraphrase_consistency": R(sum(x["consistent"] for x in pair_rows), len(pair_rows)),
        "paraphrase_same_route": R(sum(x["same_route"] for x in pair_rows), len(pair_rows)),
        "paraphrase_both_correct": R(sum(x["both_correct"] for x in pair_rows), len(pair_rows)),
        "scoring": "Turns scored like single questions (string checks on gold facts). A pair is consistent when both "
                   "wordings get the same route and the same fact verdict.",
    }
    return summary, conv_rows, pair_rows


def write_reports(summary, conv_rows, pair_rows):
    (RESULTS / "multiturn_eval.json").write_text(json.dumps({"summary": summary, "conversations": conv_rows, "paraphrases": pair_rows},
                                                            indent=1, ensure_ascii=False))
    f = lambda x: f"{x['n']}/{x['of']}" + (f" ({x['rate']:.1%})" if x["rate"] is not None else "")  # noqa: E731
    L = ["# Multi-turn and paraphrase evaluation", "", summary["scoring"], "",
         "| Metric | Result |", "|---|---|",
         f"| Conversations fully correct (all 3 turns) | {f(summary['conversations_fully_correct'])} |"]
    for n, x in summary["turn_accuracy_by_position"].items():
        L.append(f"| Turn {n} correct | {f(x)} |")
    for k, x in summary["by_kind"].items():
        L.append(f"| {k}: turns correct / conversations fully correct | {f(x['turns_correct'])} / {f(x['fully_correct'])} |")
    L += [f"| Paraphrase pairs consistent | {f(summary['paraphrase_consistency'])} |",
          f"| Paraphrase pairs with the same route | {f(summary['paraphrase_same_route'])} |",
          f"| Paraphrase pairs with both answers correct | {f(summary['paraphrase_both_correct'])} |", "",
          "## Conversations not fully correct", ""]
    for c in conv_rows:
        if not c["fully_correct"]:
            L.append(f"- **{c['id']}** ({c['kind']}): " + "; ".join(f"turn {i + 1} {v}" for i, v in enumerate(c["verdicts"])))
            for i, t in enumerate(c["turns"]):
                L.append(f"  - T{i + 1} \"{t['q']}\" -> {t['route']}; searched as \"{t['rewritten']}\": {(t['answer'] or '')[:160].replace(chr(10), ' ')}")
    L += ["", "## Inconsistent paraphrase pairs", ""]
    for p in pair_rows:
        if not p["consistent"]:
            L.append(f"- **{p['id']}**: \"{p['a']}\" -> {p['routes'][0]} (facts {p['facts_ok'][0]}) vs \"{p['b']}\" -> {p['routes'][1]} (facts {p['facts_ok'][1]})")
    (RESULTS / "multiturn_eval.md").write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["conversations", "paraphrases"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args()
    data, runs = load_set(), load_runs()
    if args.score:
        summary, c, p = score(data, runs)
        write_reports(summary, c, p)
        print(json.dumps(summary, indent=1))
        return
    units = data[args.part]
    todo = [u for u in units if u["id"] in set(args.only.split(","))] if args.only else [u for u in units if u["id"] not in runs]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{args.part}: {sum(1 for u in units if u['id'] in runs)} done; running {len(todo)} now.")
    run(args.part, todo, args.sleep)


if __name__ == "__main__":
    main()

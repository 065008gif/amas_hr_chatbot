"""Check the Phase 7 question set before spending any model quota (D-043).

  python tests/check_eval_set.py              # all checks
  python tests/check_eval_set.py --negative   # negative control: shift every evidence page by 3; must fail

Checks: (1) ids unique, routes valid, answer items have facts and evidence; (2) every evidence quote is on
its stated PDF page (text read with pdfplumber, whitespace and dashes normalised); (3) every gold fact group
can be found on the evidence pages, except verdict-only groups such as ["no", "not eligible"]; (4) no
"absent" term of an unanswerable item appears in any chunk of the index (whole-word match).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evalkit import ROOT, alt_matches, load_set, norm, turn_items  # noqa: E402

ROUTES = {"answer", "not_found", "clarify", "escalate", "tool", "refused"}
VERDICT = {"yes", "no", "can", "cannot", "may", "may not", "must not", "not", "none", "nil", "only", "is not", "does not",
           "not eligible", "not entitled", "not allowed", "not permitted", "not paid", "not payable", "not accept",
           "not covered", "not available", "not a metro", "not treated", "will not", "won't", "not be paid", "allowed",
           "permitted", "eligible", "extended", "extends", "applies", "covered", "does apply", "can file", "may file",
           "can make", "may make", "can add", "may add", "can combine", "may combine", "can be prefixed",
           "may be prefixed", "must declare", "need to declare", "required to declare", "should declare",
           "withdrawn", "no longer", "not required", "do not need", "don't need", "not need", "prohibited",
           "no referral bonus", "no shift allowance", "no professional tax", "does not levy", "digitally", "twice",
           "2 times", "double", "2x", "half", "uber", "cab", "app based cab"}


def pdf_pages():
    idx = json.loads((ROOT / "backend" / "index" / "chunks.json").read_text())
    pdfs = {c["doc_id"]: c["pdf"] for c in idx}
    out = {}
    for d, name in pdfs.items():
        path = ROOT / "documents" / Path(name).name
        with pdfplumber.open(path) as pdf:
            out[d] = [norm(p.extract_text() or "") for p in pdf.pages]
    return out, idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative", action="store_true", help="shift evidence pages by 3 (every quote should fail)")
    args = ap.parse_args()
    data = load_set()
    pages, chunks = pdf_pages()
    shift = 3 if args.negative else 0
    errors, warns, n_quotes, n_quotes_ok, n_groups, n_grounded, n_verdict = [], [], 0, 0, 0, 0, 0

    ids = [i["id"] for i in data["singles"]]
    dups = {i for i in ids if ids.count(i) > 1}
    if dups:
        errors.append(f"duplicate ids: {sorted(dups)}")

    turns = turn_items(data)
    ids += [t["id"] for t in turns] + [p["id"] for p in data.get("paraphrases") or []]
    dups = {i for i in ids if ids.count(i) > 1}
    if dups:
        errors.append(f"duplicate ids: {sorted(dups)}")
    for p in data.get("paraphrases") or []:
        if p["routes"] != ["not_found"] and not p.get("facts"):
            errors.append(f"{p['id']}: answer pair without facts")
        if not (p.get("a") and p.get("b")) or p["a"] == p["b"]:
            errors.append(f"{p['id']}: needs two different wordings")

    for it in data["singles"] + turns:
        iid = it["id"]
        if not set(it["routes"]) <= ROUTES:
            errors.append(f"{iid}: unknown route {it['routes']}")
        if not it.get("q"):
            errors.append(f"{iid}: no question")
        if "answer" in it["routes"] and not it.get("escalation"):
            if not it.get("facts"):
                errors.append(f"{iid}: answer item without facts")
            if not it.get("evidence"):
                errors.append(f"{iid}: answer item without evidence")
        ev_text = ""
        for e in it.get("evidence") or []:
            n_quotes += 1
            p = e["page"] + shift
            doc = pages.get(e["doc"], [])
            text = doc[p - 1] if 0 < p <= len(doc) else ""
            if norm(e["quote"]) in text:
                n_quotes_ok += 1
            else:
                found = [i + 1 for i, t in enumerate(doc) if norm(e["quote"]) in t]
                errors.append(f"{iid}: quote not on {e['doc']} p.{p} (found on {found or 'no page'}): \"{e['quote'][:60]}\"")
            # facts may sit on the page after a quote (tables continuing, clause runs over)
            ev_text += " " + " ".join(doc[max(0, p - 1):p + 1])
        for g in it.get("facts") or []:
            n_groups += 1
            if any(alt_matches(a, ev_text) for a in g):
                n_grounded += 1
            elif all(norm(a) in VERDICT or a.startswith("L") for a in g):
                n_verdict += 1
            elif not args.negative:
                errors.append(f"{iid}: fact group {g} not found on the evidence pages")
        for term in it.get("absent") or []:
            rx = re.compile(r"(?<![a-z0-9])" + re.escape(norm(term)) + r"(?![a-z0-9])")
            hits = [c["chunk_id"] for c in chunks if rx.search(norm(c["text"]))]
            if hits:
                errors.append(f"{iid}: 'absent' term \"{term}\" appears in {len(hits)} chunk(s), e.g. {hits[0]}")

    from collections import Counter
    cats = Counter(i["cat"] for i in data["singles"])
    print(f"Items: {len(data['singles'])} single questions ({len([i for i in data['singles'] if i.get('trap')])} traps), "
          f"{len(data.get('conversations') or [])} conversations ({len(turns)} turns), {len(data.get('paraphrases') or [])} paraphrase pairs")
    print("By category:", dict(sorted(cats.items())))
    print(f"Evidence quotes on their stated page: {n_quotes_ok}/{n_quotes}" + ("  (NEGATIVE CONTROL: pages shifted by 3)" if shift else ""))
    if not args.negative:
        print(f"Fact groups found on evidence pages: {n_grounded}/{n_groups}; verdict-only groups (not checkable in the text): {n_verdict}")
    for w in warns:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if args.negative:
        caught = n_quotes - n_quotes_ok
        print(f"Negative control: {caught}/{n_quotes} shifted quotes were caught")
        sys.exit(0 if caught == n_quotes else 1)
    print("RESULT:", "PASS" if not errors else f"FAIL ({len(errors)} errors)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

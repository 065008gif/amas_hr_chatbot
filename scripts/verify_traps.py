"""Verify traps (content/traps.yaml) against the rendered PDFs and write tests/traps.json.

Each quote must appear (after whitespace normalisation) on a page inside the page range where its
anchor (clause / table / circular / annexure) was rendered. The page is taken from the PDF, never
typed by hand. Type-5 traps (not answered anywhere) instead list `absent_terms` that must appear in
NO document.

Usage:  python scripts/verify_traps.py            (traps whose documents exist)
        python scripts/verify_traps.py --final    (also require >= 25 traps and all six types)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexdocs.common import CONTENT, DOCS, MANIFEST, ROOT, existing_doc_ids, load_yaml, norm, pdf_name, registry  # noqa: E402
from verify_pdfs import page_texts  # noqa: E402

TYPES = {1: "circular overrides body clause", 2: "two documents conflict", 3: "grade/location-specific rule",
         4: "definition changes meaning", 5: "not answered in documents", 6: "statute overrides company rule"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    reg, existing = registry(), set(existing_doc_ids())
    traps = load_yaml(CONTENT / "traps.yaml") or []
    texts, mans = {}, {}
    for d in existing:
        if (DOCS / pdf_name(d)).exists():
            texts[d] = [norm(t) for t in page_texts(DOCS / pdf_name(d))]
            mans[d] = json.loads((MANIFEST / f"{d}.json").read_text())
    out, fails, skipped = [], 0, 0
    for t in traps:
        needed = {q["doc"] for q in t.get("quotes", [])} | ({t["doc"]} if t.get("doc") else set())
        if not needed <= set(texts):
            skipped += 1
            print(f"SKIP {t['id']}: waiting for document(s) {sorted(needed - set(texts))}")
            continue
        problems, evidence = [], []
        for q in t.get("quotes", []):
            d, anchor, want = q["doc"], str(q["anchor"]), norm(q["text"])
            rng = mans[d]["anchors"].get(anchor)
            if not rng:
                problems.append(f"anchor '{anchor}' not found in document {d}")
                continue
            lo, hi = rng.get("start", 1), rng.get("end", rng.get("start", 1))
            hits = [p for p in range(1, len(texts[d]) + 1) if want in texts[d][p - 1]]
            inside = [p for p in hits if lo <= p <= hi]
            if not inside:
                problems.append(f"quote not found on pages {lo}-{hi} of {d} (found on {hits or 'no page'}): \"{q['text'][:60]}\"")
                continue
            evidence.append({"document": reg[d]["title"], "doc_id": d, "number": reg[d]["number"],
                             "page": inside[0], "clause": anchor, "quote": q["text"]})
        for term in t.get("absent_terms", []):
            found = [(d, p + 1) for d in texts for p, tx in enumerate(texts[d]) if norm(term).lower() in tx.lower()]
            if found:
                problems.append(f"'unanswerable' term '{term}' appears in {found[:3]}")
        if t["type"] == 5 and not t.get("absent_terms"):
            problems.append("type-5 trap needs absent_terms")
        if t["type"] != 5 and not evidence and not problems:
            problems.append("no quotes given")
        status = "PASS" if not problems else "FAIL"
        fails += bool(problems)
        where = "; ".join(f"{e['doc_id']} p.{e['page']} {e['clause']}" for e in evidence) or "(absent from all documents)"
        print(f"{status} {t['id']} type {t['type']} ({TYPES[t['type']]}): {where}")
        for p in problems:
            print(f"     - {p}")
        out.append({"id": t["id"], "type": t["type"], "type_name": TYPES[t["type"]], "question": t["question"],
                    "answer": t["answer"], "expected_route": t.get("expected_route", "answer"),
                    "evidence": evidence, "verified": not problems})
    (ROOT / "tests").mkdir(exist_ok=True)
    (ROOT / "tests" / "traps.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    types = sorted({t["type"] for t in out})
    print(f"\n{len(out)} traps checked, {len(out) - fails} verified, {fails} failed, {skipped} waiting. "
          f"Types covered: {types}. Written to tests/traps.json")
    ok = fails == 0
    if a.final:
        if len(out) < 25:
            print(f"FINAL CHECK: only {len(out)} traps (need >= 25)")
            ok = False
        if set(types) != set(TYPES):
            print(f"FINAL CHECK: missing trap types {sorted(set(TYPES) - set(types))}")
            ok = False
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""Check policy content (content/*.yaml) BEFORE rendering.

Usage:  python scripts/check_content.py --doc 001
        python scripts/check_content.py --all [--final]
--final: references to documents that do not exist yet become errors (end of Phase 2).
Exit code 1 if any ERROR.
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexdocs.common import (CIRC_RE, CLAUSE_RE, MARK, all_parts, block_strings, company, doc_strings,  # noqa: E402
                            existing_doc_ids, load_doc, plain, registry, split_ref, stat_ids, walk)

GRADES = [f"L{i}" for i in range(1, 9)]
UNMARKED = re.compile(r"\b(Clause|Section|Table|Annexure|Circular)\s+(No\.\s*)?([A-Z]?\d+(\.\d+)*|[A-Z]\b|HR/CIR)")


class Report:
    def __init__(self):
        self.errors, self.warnings, self.pending = [], [], []

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warnings.append(m)


def anchor_keys(doc):
    keys = set()
    for label, key, body in all_parts(doc):
        keys.add(key)
        for btype, b, _ in walk(body):
            if btype == "clause":
                keys.add(str(b["clause"]))
            elif btype == "table" and b.get("id"):
                keys.add(b["id"])
    return keys


def check_numbering(doc, r):
    secs = doc.get("sections", [])
    for i, s in enumerate(secs, 1):
        if str(s["num"]) != str(i):
            r.err(f"Section number {s['num']} out of sequence (expected {i})")
    for i, a in enumerate(doc.get("annexures", [])):
        if a["id"] != chr(65 + i):
            r.err(f"Annexure {a['id']} out of sequence (expected {chr(65 + i)})")

    def seq(blocks, parent, where):
        n = 0
        for b in blocks or []:
            if "clause" not in b:
                continue
            n += 1
            num = str(b["clause"])
            want = f"{parent}.{n}"
            if num != want:
                r.err(f"{where}: clause {num} out of sequence (expected {want})")
            if num.count(".") > 2:
                r.err(f"{where}: clause {num} deeper than three levels")
            if not (b.get("text") or b.get("items") or b.get("body")):
                r.err(f"{where}: clause {num} is empty")
            seq(b.get("body"), num, where)

    for s in secs:
        seq(s.get("body"), s["num"], f"Section {s['num']}")
    for a in doc.get("annexures", []):
        seq(a.get("body"), a["id"], f"Annexure {a['id']}")
    for c in doc.get("circulars", []):
        if any("clause" in b for b in c.get("body", [])):
            r.err(f"Circular {c['number']}: use paragraphs/items, not numbered clauses")


def check_tables(doc, r):
    ids = []
    for label, _, body in all_parts(doc):
        for btype, t, _ in walk(body):
            if btype != "table":
                continue
            name = t.get("id") or f"untitled table in {label}"
            if t.get("id"):
                ids.append(t["id"])
            width = len(t["header"]) if t.get("header") else len(t["rows"][0])
            for i, row in enumerate(t["rows"], 1):
                if len(row) != width:
                    r.err(f"{name}: row {i} has {len(row)} cells, expected {width}")
            if t.get("widths") and len(t["widths"]) != width:
                r.err(f"{name}: 'widths' has {len(t['widths'])} entries, expected {width}")
            if t.get("grade_table"):
                first = [str(row[0]).split()[0] for row in t["rows"]]
                if first != GRADES:
                    r.err(f"{name}: grade table first column must be exactly L1..L8, found {first}")
    for i, tid in enumerate(ids, 1):
        if tid != f"Table {i}":
            r.err(f"Table ids out of sequence: found '{tid}', expected 'Table {i}'")


def check_markers(doc, r, final, reg, existing, keys_cache, stats):
    here = doc["doc_id"]
    for where, s in doc_strings(doc):
        for m in MARK.finditer(s):
            kind, target = m.group(1), m.group(2).strip()
            if kind == "stat":
                if target not in stats:
                    r.err(f"{where}: {{stat:{target}}} not listed in content/STATUTORY_CLAIMS.md")
                if m.group(3) is None:
                    r.err(f"{where}: {{stat:{target}}} has no display text")
                continue
            if kind == "doc":
                if target not in reg:
                    r.err(f"{where}: {{doc:{target}}} unknown document")
                continue
            doc_id, key = split_ref(target, here)
            if doc_id not in reg:
                r.err(f"{where}: reference to unknown document {doc_id}")
                continue
            if doc_id not in existing:
                (r.err if final else r.pending.append)(f"{where}: {{ref:{target}}} -> document {doc_id} not written yet")
                continue
            if doc_id not in keys_cache:
                keys_cache[doc_id] = anchor_keys(load_doc(doc_id))
            if key not in keys_cache[doc_id]:
                r.err(f"{where}: {{ref:{target}}} points to '{key}', which does not exist in document {doc_id}")
        bare = MARK.sub("", s)
        for m in UNMARKED.finditer(bare):
            r.warn(f"{where}: unmarked reference '{m.group(0)}' (use {{ref:...}} so it is checked): "
                   f"...{bare[max(0, m.start() - 30):m.end() + 10]}...")


def check_circulars(doc, r):
    keys = anchor_keys(doc)
    for c in doc.get("circulars", []):
        if not CIRC_RE.match(c["number"]):
            r.err(f"Circular number {c['number']} not in format HR/CIR/YYYY/NN")
        for a in c.get("amends", []):
            if "#" not in a and a not in keys:
                r.err(f"Circular {c['number']} amends '{a}', which does not exist in this document")
        if str(c["effective_from"]) < str(doc["effective_date"]):
            r.warn(f"Circular {c['number']} effective {c['effective_from']} is before the policy date {doc['effective_date']}")


def check_definitions(doc, r):
    here = doc["doc_id"]
    terms = [b["term"] for _, _, body in all_parts(doc) for bt, b, _ in walk(body) if bt == "clause" and b.get("term")]
    if not terms:
        r.warn("No definitions (clauses with 'term:') found")
    # statutory wording inside {stat:...} markers is quoted law, not our defined terms
    text = " ".join(plain(re.sub(r"\{stat:[^}]*\}", "", s), here) for _, s in doc_strings(doc))
    for t in terms:
        word = r"\b" + re.escape(t) + r"s?\b"
        uses = len(re.findall(word, text)) - 1
        ok = {w.lower() for w in doc.get("lowercase_ok", [])}   # ordinary English uses, e.g. "an act of"
        lower = [m.group(0) for m in re.finditer(word, text, re.I)
                 if not m.group(0).startswith(t) and m.group(0).lower() not in ok]
        if uses < 1:
            r.warn(f"Defined term '{t}' is never used after its definition")
        if lower:
            r.warn(f"Defined term '{t}' also appears without capitals: {sorted(set(lower))}")


def sentences(doc):
    here = doc["doc_id"]
    for where, s in doc_strings(doc):
        for sent in re.split(r"(?<=[.;:])\s+", plain(s, here)):
            words = re.findall(r"[a-z0-9]+", sent.lower())
            if len(words) >= 12:
                yield where, " ".join(words), sent


def check_filler(doc, r, cross):
    seen = defaultdict(list)
    for where, key, sent in sentences(doc):
        seen[key].append((where, sent))
        cross[key].add(doc["doc_id"])
    for key, occ in seen.items():
        if len(occ) > 1:
            r.err(f"Repeated sentence ({len(occ)}x, in {', '.join(w for w, _ in occ)}): \"{occ[0][1][:90]}...\"")


def check_company(doc, r):
    here = doc["doc_id"]
    text = " ".join(plain(s, here) for _, s in doc_strings(doc))
    for g in re.findall(r"\bL(\d+)\b", text):
        if not 1 <= int(g) <= 8:
            r.err(f"Grade L{g} does not exist (grades are L1 to L8)")
    for k in ("title", "number", "version", "effective_date", "control", "history", "sections"):
        if not doc.get(k):
            r.err(f"Missing required field '{k}'")
    ctl = doc.get("control", {})
    for k in ("owner", "approver", "classification"):
        if not ctl.get(k):
            r.err(f"Missing control.{k}")
    reg_entry = registry().get(doc["doc_id"], {})
    if reg_entry.get("number") and reg_entry["number"] != doc.get("number"):
        r.err(f"Number {doc.get('number')} differs from _company.yaml ({reg_entry['number']})")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--doc")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    reg, existing, stats = registry(), set(existing_doc_ids()), stat_ids()
    company()  # fails loudly if _company.yaml is broken
    ids = sorted(existing) if a.all else [a.doc]
    keys_cache, cross, total_err = {}, defaultdict(set), 0
    for doc_id in ids:
        doc = load_doc(doc_id)
        r = Report()
        check_company(doc, r)
        check_numbering(doc, r)
        check_tables(doc, r)
        check_markers(doc, r, a.final, reg, existing, keys_cache, stats)
        check_circulars(doc, r)
        check_definitions(doc, r)
        check_filler(doc, r, cross)
        n_clauses = sum(1 for _, _, body in all_parts(doc) for bt, _, _ in walk(body) if bt == "clause")
        n_tables = sum(1 for _, _, body in all_parts(doc) for bt, _, _ in walk(body) if bt == "table")
        words = sum(len(plain(s, doc_id).split()) for _, s in doc_strings(doc))
        print(f"== {doc_id} {doc['title']}: {len(doc['sections'])} sections, {n_clauses} clauses, {n_tables} tables, "
              f"{len(doc.get('annexures', []))} annexures, {len(doc.get('circulars', []))} circulars, {words} words")
        for m in r.errors:
            print("  ERROR  ", m)
        for m in r.warnings:
            print("  WARN   ", m)
        for m in r.pending:
            print("  PENDING", m)
        print(f"  -> {len(r.errors)} errors, {len(r.warnings)} warnings, {len(r.pending)} pending references")
        total_err += len(r.errors)
    if a.all:
        shared = [k for k, d in cross.items() if len(d) > 1]
        for k in shared[:10]:
            print(f"  WARN    sentence repeated across documents {sorted(cross[k])}: \"{k[:80]}...\"")
    print("RESULT:", "PASS" if total_err == 0 else f"FAIL ({total_err} errors)")
    sys.exit(1 if total_err else 0)


if __name__ == "__main__":
    main()

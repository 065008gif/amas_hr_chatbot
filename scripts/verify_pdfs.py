"""Verify rendered PDFs AFTER building: page counts, TOC page numbers, 'Page N of M' footers.

Usage:  python scripts/verify_pdfs.py --doc 001 [--show 2]   (--show N prints the text of pages 1..N)
        python scripts/verify_pdfs.py --all
Reads the PDF independently with pdfplumber (the same library ingestion will use).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexdocs.common import DOCS, MANIFEST, existing_doc_ids, norm, pdf_name, registry  # noqa: E402

TOC_LINE = re.compile(r"^(?P<title>.+?)[\s.]*?(?P<page>\d{1,3})$")


def page_texts(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def parse_toc(texts):
    """Return [(title, page)] from the CONTENTS page(s)."""
    entries, buf = [], ""
    toc_pages = [i for i, t in enumerate(texts[:6]) if re.search(r"^CONTENTS\s*$", t, re.M)]
    if not toc_pages:
        return None
    for i in range(toc_pages[0], len(texts)):
        if i > toc_pages[0] and not re.search(r"\.\s?\.\s?\.", texts[i]):
            break                                   # TOC ended (no dot leaders on this page)
        for line in texts[i].splitlines():
            line = line.strip()
            if not line or line == "CONTENTS" or line.startswith("Nexora Technologies Limited |") \
                    or line.startswith("Fictional company") or re.match(r"^Page \d+ of \d+$", line):
                continue
            m = TOC_LINE.match(line)
            has_dots = re.search(r"(\.\s?){3,}", line)
            if m and has_dots:
                title = re.sub(r"[\s.]+$", "", (buf + " " + m.group("title")).strip())
                entries.append((title, int(m.group("page"))))
                buf = ""
            else:
                buf = (buf + " " + line).strip()    # wrapped TOC title continues on the next line
    return entries


def verify(doc_id, show=0):
    reg = registry()[doc_id]
    path = DOCS / pdf_name(doc_id)
    problems = []
    if not path.exists():
        return {"doc": doc_id, "pages": 0, "problems": ["PDF missing"], "target": reg.get("target_pages")}
    texts = page_texts(path)
    n = len(texts)
    man = json.loads((MANIFEST / f"{doc_id}.json").read_text()) if (MANIFEST / f"{doc_id}.json").exists() else {}
    if man and man.get("pages") != n:
        problems.append(f"manifest says {man.get('pages')} pages, PDF has {n}")

    # footers
    bad = [p for p in range(2, n + 1) if f"Page {p} of {n}" not in texts[p - 1]]
    if bad:
        problems.append(f"'Page N of {n}' footer missing or wrong on pages {bad}")

    # table of contents
    toc = parse_toc(texts)
    toc_ok = 0
    if toc is None:
        problems.append("CONTENTS page not found")
        toc = []
    for title, page in toc:
        if not 1 <= page <= n:
            problems.append(f"TOC entry '{title}' -> page {page} is outside the document")
            continue
        body = norm(texts[page - 1]).lower()
        want = norm(re.sub(r"^(\d+)\.\s*", r"\1. ", title)).lower()
        # headings are rendered in capitals; circular headings as 'CIRCULAR NO. X'
        want_variants = {want, want.replace("circular ", "circular no. ").split(":")[0]}
        if any(v in body for v in want_variants):
            toc_ok += 1
        else:
            problems.append(f"TOC entry '{title}' says page {page}, but that heading is not on page {page}")
    if man and len(toc) != len(man.get("toc", [])):
        problems.append(f"TOC parsed {len(toc)} entries, generator recorded {len(man.get('toc', []))}")

    target = reg.get("target_pages")
    in_range = target is None or abs(n - target) <= 2
    if not in_range:
        problems.append(f"{n} pages is outside target {target} +/-2")
    if show:
        for p in range(min(show, n)):
            print(f"\n----- {doc_id} page {p + 1} (extracted text) -----\n{texts[p].strip()}")
    return {"doc": doc_id, "title": reg["title"], "pages": n, "target": target, "toc_entries": len(toc),
            "toc_ok": toc_ok, "footer_ok": n - 1 - len(bad), "problems": problems}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--doc")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--show", type=int, default=0)
    a = ap.parse_args()
    ids = existing_doc_ids() if a.all else [a.doc]
    results = [verify(d, a.show) for d in ids]
    print(f"\n{'Doc':<5}{'Title':<52}{'Pages':>6}{'Target':>8}  {'TOC ok':>8}  {'Footers ok':>10}  Status")
    total = 0
    for r in results:
        total += r["pages"]
        status = "PASS" if not r["problems"] else "FAIL"
        print(f"{r['doc']:<5}{r.get('title', '')[:50]:<52}{r['pages']:>6}{str(r['target']) + ' +/-2':>8}  "
              f"{str(r.get('toc_ok', 0)) + '/' + str(r.get('toc_entries', 0)):>8}  "
              f"{str(r.get('footer_ok', 0)) + '/' + str(max(r['pages'] - 1, 0)):>10}  {status}")
        for p in r["problems"]:
            print(f"     - {p}")
    print(f"Total pages: {total}")
    ok = all(not r["problems"] for r in results)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

"""Phase 3 check: does each chunk's text really appear on the pages recorded for it?

Run from ~/hrbot:   python tests/verify_chunks.py            (30 random chunks, fixed seed)
                    python tests/verify_chunks.py --all      (every chunk)

For each chunk, every sentence (prose) or cell (table row) must be found in the PDF text of pages
page_start..page_end. The chunk must also START on page_start and END on page_end, so a
chunk recorded one page off fails. Table cells are compared against pdfplumber's cell-by-cell
table text as well as the page text, because wrapped table cells interleave in plain text (D-021).

A negative control then shifts every sampled chunk to a wrong page and expects the check to fail.
Finally it times a cold load of the index plus the embedding model, as retrieval will need both.
"""
import argparse
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config, indexstore  # noqa: E402

HEADER_FOOTER_RE = re.compile(r"^(Nexora Technologies Limited \||Fictional company - college project).*$", re.M)
SENT_RE = re.compile(r"[^.;:?!]+(?:[.;:?!]+(?=\s|$)|$)")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def page_texts(pdf_name):
    """page -> (normalised plain text, normalised table cells joined)."""
    out = {}
    with pdfplumber.open(config.DOCUMENTS_DIR / pdf_name) as pdf:
        for n, page in enumerate(pdf.pages, start=1):
            cells = [c for t in page.extract_tables() for r in t for c in r if c]
            # header and footer removed, as ingestion does, so a sentence can run across a page break
            out[n] = (norm(HEADER_FOOTER_RE.sub("", page.extract_text() or "")),
                      " || ".join(norm(c) for c in cells))
    return out


def fragments(chunk):
    """Pieces of the chunk that must each be found on its pages, in order."""
    frags = []
    for line in chunk["text"].split("\n"):
        line = re.sub(r" \(continued\)$", "", line)
        if line.startswith("Form fields: "):     # label added by ingestion; fields are "; "-joined
            frags += line[len("Form fields: "):].split("; ")
        elif chunk["chunk_type"] == "table" and " | " in line or re.match(r"^[^|]{1,60}: ", line):
            for cell in line.split(" | "):   # "Header: value" -> header and value are both cells
                frags += [p for p in cell.split(": ", 1) if p.strip()]
        else:
            frags += [m.group().strip() for m in SENT_RE.finditer(line) if len(m.group().strip()) >= 3]
    return [norm(f) for f in frags if norm(f)]


def check(chunk, pages, start, end):
    """Return a list of problems (empty = pass)."""
    inside = [p for p in range(start, end + 1) if p in pages]
    # Plain text of the pages joined in order (sentences can cross a page break), then all cells.
    rng = " ".join(pages[p][0] for p in inside) + " || " + " || ".join(pages[p][1] for p in inside)
    frags = fragments(chunk)
    problems = [f"not on p.{start}-{end}: {f[:70]!r}" for f in frags if f not in rng]
    if frags and not problems:
        # 20 characters: long enough to be specific, short enough not to straddle a page break
        first, last = frags[0][:20], frags[-1][-20:]
        if first not in " || ".join(pages.get(start, ("", ""))):
            problems.append(f"does not start on p.{start}: {first!r}")
        if last not in " || ".join(pages.get(end, ("", ""))):
            problems.append(f"does not end on p.{end}: {last!r}")
    return problems


def cold_load_seconds():
    code = ("import time; t=time.perf_counter(); from backend import config, indexstore; "
            "idx=indexstore.load_index(); from fastembed import TextEmbedding; "
            "m=TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.EMBED_CACHE_DIR), threads=2); "
            "list(m.embed(['warm-up query'])); print(round(idx.load_seconds,3), round(time.perf_counter()-t,2))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=config.ROOT, check=True).stdout.split()
    return float(out[0]), float(out[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    index = indexstore.load_index()
    chunks = index.chunks
    sample = chunks if args.all else random.Random(args.seed).sample(chunks, args.n)
    texts = {pdf: page_texts(pdf) for pdf in {c["pdf"] for c in sample}}

    failed = 0
    for c in sample:
        probs = check(c, texts[c["pdf"]], c["page_start"], c["page_end"])
        span = f"p.{c['page_start']}" + (f"-{c['page_end']}" if c["page_end"] != c["page_start"] else "")
        print(f"{'PASS' if not probs else 'FAIL'}  {c['chunk_id']:<42} {span:<8} {len(fragments(c)):3} pieces")
        for p in probs[:3]:
            print("      ", p)
        failed += bool(probs)
    print(f"\n{len(sample) - failed}/{len(sample)} chunks verified on their recorded pages "
          f"(seed {args.seed}{', all chunks' if args.all else ''})")

    # Negative control: the same chunks, recorded 2 pages later (or earlier near the end), must FAIL.
    caught = 0
    for c in sample:
        pages = texts[c["pdf"]]
        shift = 2 if c["page_end"] + 2 <= max(pages) else -2
        caught += bool(check(c, pages, c["page_start"] + shift, c["page_end"] + shift))
    print(f"Negative control: {caught}/{len(sample)} deliberately wrong page numbers were caught")

    idx_s, total_s = cold_load_seconds()
    print(f"Cold start in a fresh process: index {idx_s:.2f} s; index + embedding model (2 threads) "
          f"+ first query {total_s:.2f} s ({'PASS' if total_s < 5 else 'FAIL'}: under 5 s)")
    ok = failed == 0 and caught == len(sample) and total_s < 5
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

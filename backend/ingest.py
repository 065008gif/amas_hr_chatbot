"""Phase 3: parse the policy PDFs, chunk them by structure, and build the search indexes.

Run from ~/hrbot:   python -m backend.ingest

Everything is read from the PDFs themselves (page text and cell-by-cell tables via pdfplumber),
as a real deployment would receive them. The renderer's manifests in documents/manifest/ are used
only afterwards, as an answer key, to check that every clause, table and circular was detected on
the right page.

Output (backend/index/): chunks.json, bm25_tokens.json, vectors.npy, index_meta.json.
"""
import argparse
import hashlib
import json
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pdfplumber
from tokenizers import Tokenizer

from backend import config, indexstore

# ---------------------------------------------------------------------------------------------
# Patterns for the structure of a Nexora policy PDF
# ---------------------------------------------------------------------------------------------
HEADER_RE = re.compile(r"^Nexora Technologies Limited \|")
FOOTER_RE = re.compile(r"^Fictional company - college project")
CONTENTS_RE = re.compile(r"^(TABLE OF )?CONTENTS$")
SECTION_RE = re.compile(r"^(\d{1,2})\.\s+([A-Z][A-Z0-9 ,&/()'\-]+)$")
CLAUSE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{1,2}))?\s+(\S.*)$")
ANNEX_RE = re.compile(r"^ANNEXURE ([A-Z]):\s*(.+)$")
ANNEX_ITEM_RE = re.compile(r"^([A-Z])\.(\d{1,2})\s+(\S.*)$")
CIRCULARS_RE = re.compile(r"^AMENDMENT CIRCULARS$")
CIRCULAR_RE = re.compile(r"^CIRCULAR NO\.\s+(HR/CIR/\d{4}/\d+)$")
CAPTION_RE = re.compile(r"^Table (\d+):\s*(.+)$")
DEFINED_TERM_RE = re.compile(r'^["“]([^"”]+)["”]')
CLAUSE_TITLE_RE = re.compile(r"^([A-Z][^.;:]{1,70}?)\.\s")
SENTENCE_RE = re.compile(r"[^.;:?!]+(?:[.;:?!]+(?=\s|$)|$)")   # sentence-like spans with offsets
GRADE_RE = re.compile(r"\bL([1-8])\b(?:\s*(?:to|-|and)\s*L([1-8])\b)?")
LOCATIONS = {
    "Bengaluru": ["bengaluru", "bangalore", "karnataka"],
    "Pune": ["pune", "maharashtra"],
    "Hyderabad": ["hyderabad", "telangana"],
    "Chennai": ["chennai", "tamil nadu"],
    "Noida": ["noida", "uttar pradesh", "ncr"],
}
LOCATION_RES = {city: re.compile(r"\b(" + "|".join(keys) + r")\b", re.I) for city, keys in LOCATIONS.items()}
SMALL_WORDS = {"and", "or", "of", "the", "in", "on", "for", "to", "a", "an", "by", "with", "at"}
ACRONYMS = {"POSH", "NPP", "PF", "ESI", "ESOP", "NPS", "LTA", "HRA", "IT", "BYOD", "DPDP", "F&F",
            "AML", "CTC", "TDS", "LWP", "EL", "CL", "SL", "IC", "HR", "UK", "USA"}

_tokenizer = None


def ntokens(text: str) -> int:
    """Token count with the embedding model's own tokenizer (so it matches the 512 limit)."""
    global _tokenizer
    if _tokenizer is None:
        path = next(config.EMBED_CACHE_DIR.glob("models--*bge-small*/snapshots/*/tokenizer.json"))
        _tokenizer = Tokenizer.from_file(str(path))
    return len(_tokenizer.encode(text, add_special_tokens=False).ids)


def clean(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def smart_title(s: str) -> str:
    words = []
    for i, w in enumerate(s.split()):
        bare = w.strip("(),")
        if bare.upper() in ACRONYMS or re.fullmatch(r"L\d", bare):
            words.append(w.upper())
        elif i and w.lower() in SMALL_WORDS:
            words.append(w.lower())
        else:
            words.append(w[:1].upper() + w[1:].lower())
    return " ".join(words)


# ---------------------------------------------------------------------------------------------
# Step 1: read each page into an ordered stream of lines and tables
# ---------------------------------------------------------------------------------------------
def _cell_is_bold(page, bbox) -> bool | None:
    if bbox is None:
        return None
    chars = [c for c in page.chars
             if bbox[0] <= c["x0"] <= bbox[2] and bbox[1] <= c["top"] <= bbox[3]]
    if not chars:
        return None
    return all("Bold" in c["fontname"] for c in chars)


def _table_kind(page, table, rows) -> str:
    """'grid' (bold header row), 'kv' (bold labels in column 1), 'form' (blank answer column)."""
    first = [_cell_is_bold(page, c) for c in table.rows[0].cells]
    if all(b for b in first if b is not None) and len(rows[0]) > 1 and any(rows[0][1:]):
        if len(rows[0]) == 2 and all(_cell_is_bold(page, r.cells[0]) for r in table.rows[1:]):
            pass    # every row has a bold label: a key-value table, not a header row
        else:
            return "grid"
    if len(rows[0]) == 2 and all(not r[1] for r in rows):
        return "form"
    if len(rows[0]) == 2:
        return "kv"
    return "grid"


def read_pages(pdf_path: Path):
    """Yield (page_no, 'line', text) and (page_no, 'table', {...}) in reading order."""
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, start=1):
            if pno == 1:
                continue    # cover page
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]

            def outside_tables(obj):
                if obj.get("object_type") != "char":
                    return True
                cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
                return not any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in boxes)

            items = []
            for ln in page.filter(outside_tables).extract_text_lines():
                text = clean(ln["text"])
                if text and not HEADER_RE.match(text) and not FOOTER_RE.match(text):
                    items.append((ln["top"], "line", text))
            for t in tables:
                rows = [[clean(c) for c in r] for r in t.extract()]
                rows = [r for r in rows if any(r)]
                if rows:
                    items.append((t.bbox[1], "table", {"rows": rows, "kind": _table_kind(page, t, rows)}))
            items.sort(key=lambda it: it[0])
            if items and items[0][1] == "line" and CONTENTS_RE.match(items[0][2]):
                continue    # table-of-contents page
            first = True
            for _, kind, payload in items:
                yield pno, kind, payload, first
                first = False
    read_pages.n_pages = n_pages


# ---------------------------------------------------------------------------------------------
# Step 2: walk the stream and cut it into structural units (clause, table, circular, ...)
# ---------------------------------------------------------------------------------------------
class Unit:
    seq = 0     # creation order = document order (a table is created inside its open clause)

    def __init__(self, kind, section_no, section_title, clause_no=None, clause_title=None, **extra):
        Unit.seq += 1
        self.seq = Unit.seq
        self.kind = kind                    # clause | definition | annexure | circular | table
        self.section_no = section_no        # "6", "Annexure C", "Circulars", "Front"
        self.section_title = section_title
        self.clause_no = clause_no
        self.clause_title = clause_title
        self.lines = []                     # (page, text, starts_new_line); tables: one per row
        self.extra = extra
        self._break_next = False

    def add(self, page, text, newline=False, heading=False):
        self.lines.append((page, text, newline or self._break_next or not self.lines))
        self._break_next = heading


def _next_clause_ok(prev, new, section):
    if new[0] != section:
        return False
    if prev is None:
        return new == (section, 1)
    if len(prev) == 2:
        return new in ((section, prev[1] + 1), (section, prev[1], 1))
    return new in ((section, prev[1], prev[2] + 1), (section, prev[1] + 1))


def _clause_title(rest, is_definition):
    if is_definition:
        m = DEFINED_TERM_RE.match(rest)
        return m.group(1) if m else None
    m = CLAUSE_TITLE_RE.match(rest)
    return m.group(1) if m and len(m.group(1).split()) <= 10 else None


def _render_rows(header, rows):
    out = []
    for r in rows:
        parts = [f"{h}: {v}" if h else v for h, v in zip(header, r) if v]
        out.append(" | ".join(parts))
    return out


def parse_document(pdf_path: Path):
    """Return (doc_meta, units) for one PDF."""
    stream = list(read_pages(pdf_path))
    n_pages = read_pages.n_pages
    doc = {"pages": n_pages, "pdf": pdf_path.name,
           "doc_id": re.search(r"POL-(\d{3})", pdf_path.name).group(1)}
    units, mode = [], "front"
    sec_no, sec_title, last_clause = None, "Document Control", None
    annex, last_item = None, 0
    cur = Unit("clause", "Front", "Document Control")
    last_table = None       # a grid table that the next page may continue
    prev_line = None
    pending_caption = None
    annex_title = None

    def close():
        nonlocal cur
        if cur is not None and cur.lines:
            units.append(cur)
        cur = None

    for i, (pno, kind, payload, first_on_page) in enumerate(stream):
        if kind == "line":
            text = payload
            nxt = stream[i + 1] if i + 1 < len(stream) else None
            m_sec = SECTION_RE.match(text)
            if m_sec and mode in ("front", "body") and int(m_sec.group(1)) == (sec_no or 0) + 1:
                close()
                mode, sec_no, sec_title, last_clause = "body", int(m_sec.group(1)), m_sec.group(2), None
                cur = Unit("clause", str(sec_no), sec_title)
                cur.add(pno, text, heading=True)
            elif (m := ANNEX_RE.match(text)) and mode in ("body", "annex"):
                close()
                mode, annex, annex_title, last_item = "annex", m.group(1), m.group(2), 0
                cur = Unit("annexure", f"Annexure {annex}", annex_title)
                cur.add(pno, text, heading=True)
            elif CIRCULARS_RE.match(text) and mode in ("body", "annex"):
                close()
                mode = "circulars"
                cur = Unit("circular", "Circulars", "Amendment Circulars")
                cur.add(pno, text, heading=True)
            elif (m := CIRCULAR_RE.match(text)) and mode == "circulars":
                close()
                cur = Unit("circular", "Circulars", "Amendment Circulars", m.group(1), None,
                           meta={})
                cur.add(pno, text, heading=True)
            elif (m := CLAUSE_RE.match(text)) and mode == "body" and _next_clause_ok(
                    last_clause, tuple(int(g) for g in m.groups()[:3] if g), sec_no):
                close()
                num = tuple(int(g) for g in m.groups()[:3] if g)
                last_clause = num
                is_def = "DEFINITION" in sec_title
                cur = Unit("definition" if is_def else "clause", str(sec_no), sec_title,
                           ".".join(map(str, num)), _clause_title(m.group(4), is_def))
                cur.add(pno, text)
            elif ((m := ANNEX_ITEM_RE.match(text)) and mode == "annex" and m.group(1) == annex
                  and int(m.group(2)) == last_item + 1):
                close()
                last_item = int(m.group(2))
                rest = m.group(3)
                title = rest.split("?")[0] + "?" if "?" in rest[:160] else _clause_title(rest, False)
                cur = Unit("annexure", f"Annexure {annex}", annex_title, f"{annex}.{last_item}", title)
                cur.add(pno, text)
            elif (m := CAPTION_RE.match(text)) and nxt and nxt[1] == "table":
                pending_caption = (int(m.group(1)), m.group(2))
            else:
                is_heading = text.isupper() and len(text) < 60     # e.g. "DISTRIBUTION AND ACCESS"
                cur.add(pno, text, newline=is_heading, heading=is_heading)
            prev_line = text
            last_table = None
        else:  # table
            rows, tkind = payload["rows"], payload["kind"]
            caption, pending_caption = pending_caption, None
            # A table that starts a page and repeats the previous table's header continues it.
            if (caption is None and first_on_page and last_table is not None
                    and tkind == "grid" and rows[0] == last_table.extra["header"]):
                for r in _render_rows(rows[0], rows[1:]):
                    last_table.add(pno, r)
                continue
            if tkind == "kv" and mode in ("circulars", "front") and cur is not None:
                for k, v in rows:
                    cur.add(pno, f"{k}: {v}" if v else k, newline=True)
                    if mode == "circulars" and cur.extra.get("meta") is not None:
                        cur.extra["meta"][k] = v
                    if mode == "front":
                        doc[k] = v
                cur._break_next = True      # text after the table starts on a new line
                last_table = None
                continue
            if caption:
                tno, tcap = caption
                label = f"Table {tno}: {tcap}"
            else:
                tno, label = None, smart_title(prev_line) if prev_line and prev_line.isupper() else (prev_line or "Table")
            # The table splits the clause it sits in: text after it becomes a continuation unit, so
            # every chunk keeps reading order (the continuation merges with what follows).
            host = cur
            close()
            t = Unit("table", host.section_no, host.section_title, host.clause_no, None,
                     table_no=tno, caption=label, header=rows[0] if tkind == "grid" else None,
                     table_kind=tkind)
            if tkind == "grid":
                for r in _render_rows(rows[0], rows[1:]):
                    t.add(pno, r)
            elif tkind == "form":
                t.add(pno, "Form fields: " + "; ".join(r[0] for r in rows))
            else:
                for k, v in rows:
                    t.add(pno, f"{k}: {v}")
            units.append(t)
            cur = Unit(host.kind, host.section_no, host.section_title, host.clause_no,
                       host.clause_title, **host.extra)
            last_table = t if tkind == "grid" else None
    close()
    units.sort(key=lambda u: u.seq)
    return doc, units


# ---------------------------------------------------------------------------------------------
# Step 3: size the units into chunks (merge short neighbours, split long ones)
# ---------------------------------------------------------------------------------------------
class Piece:
    """Text with a page for every character offset range, so pages survive merging/splitting."""

    def __init__(self, units):
        self.units = units
        self.text, self.spans = "", []      # spans: (start, end, page, clause_no)
        self.table = next((u for u in units if u.kind == "table"), None)
        prev = ""
        for u in units:
            lines = u.lines
            caption = u.extra.get("caption") if u.kind == "table" else None
            if caption and caption.lower() != prev.lower():     # caption opens the table rows
                lines = [(u.lines[0][0], caption, True)] + lines
            for page, line, newline in lines:
                if self.text:     # clause, heading or table row on a new line; wrapped text joins with a space
                    self.text += "\n" if newline or u.kind == "table" else " "
                start = len(self.text)
                self.text += line
                self.spans.append((start, len(self.text), page, u.clause_no))
                prev = line
        self.tokens = ntokens(self.text)

    def pages_between(self, a, b):
        return sorted({p for s, e, p, _ in self.spans if s < b and e > a})

    def clause_pages(self, a=0, b=None):
        b = len(self.text) if b is None else b
        out = {}
        for s, e, p, c in self.spans:
            if c and s < b and e > a:
                lo, hi = out.get(c, (p, p))
                out[c] = (min(lo, p), max(hi, p))
        return out


TEXT_KINDS = ("clause", "definition", "annexure")


def _mergeable(a: Unit, b: Unit) -> bool:
    """Same parent (section or annexure), and the same kind, or a section's intro text."""
    return (a.kind in TEXT_KINDS and b.kind in TEXT_KINDS and a.section_no == b.section_no
            and (a.kind == b.kind or a.clause_no is None))


def group_units(units):
    """Merge short neighbouring units under the same parent; tables and circulars stand alone.

    First, a short annexure lead-in ("ANNEXURE D: APPROVAL MATRIX" + one line) and a short note
    under an annexure table join that table. Then tables are left out of the chain, so a table inside a clause does not stop
    that clause merging with its neighbours. Groups are returned in document order.
    """
    tables, lead_ins = [], set()
    for i, u in enumerate(units):
        if u.kind != "table":
            continue
        prev = units[i - 1] if i else None
        if (prev is not None and prev.kind == "annexure" and prev.clause_no is None
                and prev.section_no == u.section_no and id(prev) not in lead_ins
                and Piece([prev]).tokens < config.CHUNK_MIN_TOKENS
                and Piece([prev, u]).tokens <= config.CHUNK_MAX_TOKENS):
            group = [prev, u]
            lead_ins.add(id(prev))
        else:
            group = [u]
        nxt = units[i + 1] if i + 1 < len(units) else None
        # ...and a short note under an annexure table ("Days are calendar days...") stays with it.
        if (nxt is not None and nxt.kind == "annexure" and nxt.clause_no is None
                and nxt.section_no == u.section_no and Piece([nxt]).tokens < config.CHUNK_MIN_TOKENS
                and Piece(group + [nxt]).tokens <= config.CHUNK_MAX_TOKENS):
            group.append(nxt)
            lead_ins.add(id(nxt))
        tables.append(group)
    groups = []
    for u in (u for u in units if u.kind != "table" and id(u) not in lead_ins):
        if (groups and _mergeable(groups[-1][-1], u)
                and Piece(groups[-1]).tokens < config.CHUNK_MIN_TOKENS
                and Piece(groups[-1] + [u]).tokens <= config.CHUNK_MAX_TOKENS):
            groups[-1].append(u)
        else:
            groups.append([u])
    # A short group at the end of a parent joins the group before it, if that still fits.
    out = []
    for g in groups:
        if (out and _mergeable(out[-1][-1], g[0]) and Piece(g).tokens < config.CHUNK_MIN_TOKENS
                and Piece(out[-1] + g).tokens <= config.CHUNK_MAX_TOKENS):
            out[-1] = out[-1] + g
        else:
            out.append(g)
    return sorted(out + tables, key=lambda g: g[0].seq)


def split_piece(piece: Piece):
    """Yield (start, end) offsets. Tables split between rows; prose between sentences, with overlap."""
    if piece.tokens <= config.CHUNK_MAX_TOKENS:
        yield 0, len(piece.text)
        return
    if piece.table is not None:
        spans = [(s, e) for s, e, _, _ in piece.spans]
        head = piece.table.extra["caption"]
        start, cur_end, acc = spans[0][0], None, ntokens(head)
        for s, e in spans:
            t = ntokens(piece.text[s:e])
            if cur_end is not None and acc + t > config.CHUNK_SPLIT_TARGET:
                yield start, cur_end
                start, acc = s, ntokens(head)
            acc += t
            cur_end = e
        yield start, cur_end
        return
    sents = [(m.start(), m.end()) for m in SENTENCE_RE.finditer(piece.text) if m.group().strip()]
    i = 0
    while i < len(sents):
        j, acc = i, 0
        while j < len(sents):
            t = ntokens(piece.text[sents[j][0]:sents[j][1]])
            if j > i and acc + t > config.CHUNK_SPLIT_TARGET:
                break
            acc += t
            j += 1
        yield sents[i][0], sents[j - 1][1]
        if j >= len(sents):
            break
        i = max(i + 1, j - config.CHUNK_OVERLAP_SENTENCES)


def mentions(text):
    grades = set()
    for a, b in GRADE_RE.findall(text):
        lo, hi = int(a), int(b or a)
        grades.update(range(min(lo, hi), max(lo, hi) + 1))
    locs = [city for city, rx in LOCATION_RES.items() if rx.search(text)]
    return [f"L{g}" for g in sorted(grades)], locs


def parse_amends(value):
    refs = re.findall(r"(Clause|Table)\s+([\dA-Z]+(?:\.\d+)*)", value or "")
    return [f"Table {n}" if kind == "Table" else n for kind, n in refs]


def build_chunks(doc, units):
    title, version = doc["Document Title"], doc["Version"]
    number, eff = doc["Document Number"], doc["Effective Date"]
    chunks = []
    for group in group_units(units):
        piece = Piece(group)
        u0 = piece.table or group[0]      # an annexure lead-in + its table is a table chunk
        parts = list(split_piece(piece))
        for k, (a, b) in enumerate(parts):
            text = piece.text[a:b].strip()
            if u0.kind == "table" and k > 0:
                text = f"{u0.extra['caption']} (continued)\n{text}"
            pages = piece.pages_between(a, b)
            clause_pages = piece.clause_pages(a, b)
            clauses = list(clause_pages)
            chunk = {
                "doc_id": doc["doc_id"], "title": title, "number": number, "version": version,
                "effective_date": eff, "pdf": doc["pdf"],
                "page_start": pages[0], "page_end": pages[-1],
                "section_no": u0.section_no, "section_title": smart_title(u0.section_title),
                "clause_no": clauses[0] if clauses else None, "clauses": clauses,
                "clause_pages": clause_pages,
                "clause_title": u0.clause_title if len(group) == 1 else None,
                "chunk_type": u0.kind,
                "part": f"{k + 1}/{len(parts)}" if len(parts) > 1 else None,
                "text": text,
            }
            if u0.kind == "table":
                chunk["table_no"] = u0.extra["table_no"]
                chunk["caption"] = u0.extra["caption"]
                chunk["table_kind"] = u0.extra["table_kind"]
            if u0.kind == "circular" and u0.clause_no:
                meta = u0.extra["meta"]
                chunk.update(circular_no=u0.clause_no, circular_effective=meta.get("Effective From"),
                             circular_issued=meta.get("Date of Issue"),
                             clause_title=meta.get("Subject"), amends=parse_amends(meta.get("Amends")))
            chunk["grades"], chunk["locations"] = mentions(text)
            chunks.append(chunk)
    return chunks


def finish_chunks(chunks):
    """Unique ids, amended_by links, contextual prefixes and token counts."""
    circulars = defaultdict(list)       # (doc_id, clause or "Table n") -> [circular_no]
    for c in chunks:
        for ref in c.get("amends", []):
            circulars[(c["doc_id"], ref)].append(c["circular_no"])
    seen = Counter()
    for c in chunks:
        kind = c["chunk_type"]
        if kind == "table":
            key = f"table{c['table_no']}" if c["table_no"] else f"table:{c['section_no']}:{c['caption'][:30]}"
        elif kind == "circular":
            key = c.get("circular_no") or "circulars-intro"
        elif c["clauses"]:
            key = c["clauses"][0] + (f"-{c['clauses'][-1]}" if len(c["clauses"]) > 1 else "")
        else:
            key = f"{c['section_no']}-intro"
        base = f"{c['doc_id']}:{kind}:{key}".replace(" ", "_")
        seen[base] += 1
        c["chunk_id"] = base if seen[base] == 1 else f"{base}#{seen[base]}"

        refs = set(c["clauses"])
        refs |= {".".join(x.split(".")[:2]) for x in c["clauses"]}      # 6.4.1 -> also 6.4
        if kind == "table" and c["table_no"]:
            refs.add(f"Table {c['table_no']}")
        amended = sorted({n for r in refs for n in circulars.get((c["doc_id"], r), [])})
        if amended and kind != "circular":
            c["amended_by"] = amended

        c["context"] = context_prefix(c)
        c["embed_text"] = f"{c['context']}\n{c['text']}"
        c["tokens"] = ntokens(c["text"])
        c["embed_tokens"] = ntokens(c["embed_text"])
    return chunks


def context_prefix(c):
    head = f"{c['title']} v{c['version']} ({c['number']})"
    kind = c["chunk_type"]
    if kind == "circular":
        if c.get("circular_no"):
            amends = ", ".join(c["amends"]) or "the Policy"
            return (f"{head}, Amendment Circular {c['circular_no']} ({c['clause_title']}), "
                    f"effective {c['circular_effective']}, amends {amends}:")
        return f"{head}, Amendment Circulars:"
    if c["section_no"] == "Front":
        where = "Document control and version history"
    elif c["section_no"].startswith("Annexure"):
        where = f"{c['section_no']} {c['section_title']}"
    else:
        where = f"Section {c['section_no']} {c['section_title']}"
    if kind == "table":
        what = c["caption"]
    elif len(c["clauses"]) > 1:
        what = f"Clauses {c['clauses'][0]} to {c['clauses'][-1]}"
    elif c["clauses"]:
        what = f"Clause {c['clauses'][0]}" + (f" {c['clause_title']}" if c["clause_title"] else "")
    else:
        what = ""
    return ", ".join(x for x in (head, where, what) if x) + ":"


# ---------------------------------------------------------------------------------------------
# Step 4: check the parse against the renderer's manifest (answer key, not an input)
# ---------------------------------------------------------------------------------------------
def check_against_manifest(doc_id, chunks):
    manifest = json.loads((config.MANIFEST_DIR / f"{doc_id}.json").read_text())
    found = {}      # anchor -> set of pages where the parser put it
    for c in chunks:
        for cl, (lo, hi) in c["clause_pages"].items():
            found.setdefault(cl, set()).update(range(lo, hi + 1))
        if c["chunk_type"] == "table" and c["table_no"]:
            found.setdefault(f"Table {c['table_no']}", set()).update(range(c["page_start"], c["page_end"] + 1))
    problems, checked = [], 0
    for anchor, rng in manifest["anchors"].items():
        if anchor.startswith(("Section", "Annexure")):
            continue
        checked += 1
        if anchor not in found:
            problems.append(f"{doc_id} {anchor}: not detected")
        elif min(found[anchor]) not in range(rng["start"], rng["end"] + 1):
            # The renderer's start anchor can sit on the page BEFORE a page break (the item itself
            # then begins on the next page), so the test is: the parser's first page lies inside
            # the manifest range. tests/verify_chunks.py confirms pages against the PDF text.
            problems.append(f"{doc_id} {anchor}: manifest p.{rng['start']}-{rng['end']}, "
                            f"parser p.{sorted(found[anchor])}")
    meta_ok = all(manifest[k] == v for k, v in
                  (("version", chunks[0]["version"]), ("number", chunks[0]["number"]),
                   ("effective_date", chunks[0]["effective_date"])))
    if not meta_ok:
        problems.append(f"{doc_id}: document-control metadata differs from manifest")
    return checked, problems


# ---------------------------------------------------------------------------------------------
# Step 5: build and save the indexes
# ---------------------------------------------------------------------------------------------
def embed(texts):
    from fastembed import TextEmbedding
    model = TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.EMBED_CACHE_DIR))
    vecs = np.array(list(model.embed(texts, batch_size=config.EMBED_BATCH_SIZE)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-embed", action="store_true", help="parse and chunk only (quick check)")
    args = ap.parse_args()
    t0 = time.perf_counter()

    pdfs = sorted(config.DOCUMENTS_DIR.glob("NTL-HR-POL-*.pdf"))
    all_chunks, docs, problems, anchors_checked = [], [], [], 0
    for pdf in pdfs:
        doc, units = parse_document(pdf)
        chunks = finish_chunks(build_chunks(doc, units))
        n, probs = check_against_manifest(doc["doc_id"], chunks)
        anchors_checked += n
        problems += probs
        docs.append({"doc_id": doc["doc_id"], "title": doc["Document Title"],
                     "number": doc["Document Number"], "version": doc["Version"],
                     "effective_date": doc["Effective Date"], "pages": doc["pages"],
                     "pdf": pdf.name, "sha256": sha256(pdf), "chunks": len(chunks)})
        all_chunks += chunks
    t_parse = time.perf_counter() - t0

    ids = [c["chunk_id"] for c in all_chunks]
    assert len(ids) == len(set(ids)), "duplicate chunk ids"
    print_stats(docs, all_chunks, t_parse)
    print(f"\nParser check against renderer manifests: {anchors_checked - len(problems)}/{anchors_checked} "
          f"clauses, tables, annexure items and circulars found on the right page")
    for p in problems:
        print("  PROBLEM:", p)
    if args.no_embed:
        print("\n--no-embed: indexes not written.")
        return 1 if problems else 0

    t = time.perf_counter()
    vectors = embed([c["embed_text"] for c in all_chunks])
    t_embed = time.perf_counter() - t
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    indexstore.CHUNKS_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    indexstore.BM25_FILE.write_text(json.dumps([indexstore.tokenize(c["embed_text"]) for c in all_chunks]),
                                    encoding="utf-8")
    np.save(indexstore.VECTORS_FILE, vectors)
    indexstore.META_FILE.write_text(json.dumps({
        "built": datetime.now().isoformat(timespec="seconds"),
        "embed_model": config.EMBED_MODEL, "embed_dim": int(vectors.shape[1]),
        "chunks": len(all_chunks), "documents": docs,
        "chunking": {k: getattr(config, k) for k in dir(config) if k.startswith("CHUNK_")},
    }, indent=1), encoding="utf-8")

    index = indexstore.load_index()
    size_mb = sum(f.stat().st_size for f in config.INDEX_DIR.iterdir()) / 1e6
    print(f"\nEmbedded {len(all_chunks)} chunks with {config.EMBED_MODEL} in {t_embed:.1f} s "
          f"-> vectors {vectors.shape}")
    print(f"Index written to backend/index/ ({size_mb:.1f} MB). Reload time: {index.load_seconds:.2f} s "
          f"({'PASS' if index.load_seconds < 5 else 'FAIL'}: must be under 5 s)")
    print(f"Total time: {time.perf_counter() - t0:.1f} s")
    return 1 if problems else 0


def print_stats(docs, chunks, t_parse):
    toks = [c["tokens"] for c in chunks]
    types = Counter(c["chunk_type"] for c in chunks)
    print(f"Documents: {len(docs)}   Pages: {sum(d['pages'] for d in docs)}   "
          f"Chunks: {len(chunks)}   (parsed in {t_parse:.1f} s)")
    print("\n  doc  pages chunks  title")
    for d in docs:
        print(f"  {d['doc_id']}  {d['pages']:5} {d['chunks']:6}  {d['title']} v{d['version']}")
    print("\nChunks by type: " + ", ".join(f"{k} {v}" for k, v in sorted(types.items())))
    print(f"Tokens per chunk (bge tokenizer, display text): average {statistics.mean(toks):.0f}, "
          f"median {statistics.median(toks):.0f}, smallest {min(toks)}, largest {max(toks)}")
    bands = Counter("<50" if t < 50 else "50-149" if t < 150 else "150-450" if t <= 450 else ">450"
                    for t in toks)
    print("Size bands: " + ", ".join(f"{b}: {bands.get(b, 0)}" for b in ("<50", "50-149", "150-450", ">450")))
    tables = [c for c in chunks if c["chunk_type"] == "table"]
    src_tables = {(c["doc_id"], c["caption"]) for c in tables}
    numbered = {(c["doc_id"], c["table_no"]) for c in tables if c["table_no"]}
    print(f"Tables: {len(src_tables)} source tables ({len(numbered)} numbered) -> {len(tables)} table chunks")
    circ = [c for c in chunks if c.get("circular_no")]
    print(f"Circulars: {len(circ)} circular chunks; {sum(1 for c in chunks if c.get('amended_by'))} "
          f"body chunks carry an 'amended_by' link")
    big = [c for c in chunks if c["tokens"] > config.CHUNK_WARN_TOKENS]
    print(f"Chunks over {config.CHUNK_WARN_TOKENS} tokens: {len(big)}")
    for c in big:
        print(f"  {c['chunk_id']}: {c['tokens']} tokens")
    trunc = [c for c in chunks if c["embed_tokens"] > config.EMBED_MAX_TOKENS - 2]
    print(f"Chunks the embedding model would truncate (> {config.EMBED_MAX_TOKENS} tokens with prefix): {len(trunc)}")


if __name__ == "__main__":
    raise SystemExit(main())

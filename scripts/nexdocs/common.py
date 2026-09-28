"""Shared helpers for building and checking the Nexora policy documents.

Content markers (inside any text string in content/*.yaml; they never appear in the PDF):
  {ref:#4.3}            -> "Clause 4.3"                     (same document)
  {ref:#Table 2}        -> "Table 2"      also "Section 4", "Annexure B", "HR/CIR/2025/07"
  {ref:005#7.2}         -> "Clause 7.2 of the Compensation and Benefits Policy (NTL/HR/POL/005)"
  {ref:#4.3|this Clause} -> display text override; the target is still checked
  {doc:005}             -> "Compensation and Benefits Policy (NTL/HR/POL/005)"
  {stat:MB_MATERNITY|26 weeks} -> "26 weeks"; ID must exist in content/STATUTORY_CLAIMS.md
  **bold**              -> bold text
"""
import functools
import re
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
DOCS = ROOT / "documents"
MANIFEST = DOCS / "manifest"
STAT_FILE = CONTENT / "STATUTORY_CLAIMS.md"

MARK = re.compile(r"\{(ref|doc|stat):([^}|]*)(?:\|([^}]*))?\}")
CLAUSE_RE = re.compile(r"^([A-Z]|\d+)(\.\d+)+$")          # 4.3, 4.3.1, B.2
CIRC_RE = re.compile(r"^HR/CIR/\d{4}/\d{2}$")


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def company():
    return load_yaml(CONTENT / "_company.yaml")


@functools.lru_cache(maxsize=None)
def registry():
    """doc_id -> {title, number, file, ...}; includes any extra pol*.yaml (e.g. a self-test).
    Cached: content files do not change while one script runs."""
    reg = {k: dict(v) for k, v in company()["documents"].items()}
    for f in CONTENT.glob("pol*.yaml"):
        d = load_yaml(f)
        reg.setdefault(str(d["doc_id"]), {"title": d["title"], "number": d["number"],
                                          "target_pages": d.get("target_pages"), "file": f.name})
    return reg


def doc_path(doc_id):
    return CONTENT / registry()[doc_id]["file"]


def load_doc(doc_id):
    d = load_yaml(doc_path(doc_id))
    d["doc_id"] = str(d["doc_id"])
    return d


def existing_doc_ids():
    reg = registry()
    return sorted(k for k, v in reg.items() if (CONTENT / v["file"]).exists())


def pdf_name(doc_id):
    reg = registry()[doc_id]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", reg["title"]).strip("_")
    return f"{reg['number'].replace('/', '-')}_{slug}.pdf"


def ref_label(key):
    if CIRC_RE.match(key):
        return f"Circular {key}"
    if CLAUSE_RE.match(key):
        return f"Clause {key}"
    return key  # "Table 2", "Section 4", "Annexure B"


def split_ref(target, here):
    doc, _, key = target.partition("#")
    return (doc or here), key


def render_markers(s, here, reg=None):
    """Replace markers with display text (plain text, no XML)."""
    reg = reg or registry()

    def sub(m):
        kind, target, override = m.group(1), m.group(2).strip(), m.group(3)
        if override is not None:
            return override
        if kind == "stat":
            raise ValueError(f"{{stat:{target}}} needs display text: {{stat:ID|text}}")
        if kind == "doc":
            r = reg[target]
            return f"{r['title']} ({r['number']})"
        doc, key = split_ref(target, here)
        label = ref_label(key)
        if doc != here:
            r = reg[doc]
            label += f" of the {r['title']} ({r['number']})"
        return label

    return MARK.sub(sub, s)


def to_para_xml(s, here, reg=None):
    """Markers -> text, escape XML, then **bold** -> <b>."""
    text = escape(render_markers(s, here, reg))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def plain(s, here, reg=None):
    return render_markers(s, here, reg).replace("**", "")


def norm(s):
    """Normalise text for matching PDF extraction against source text."""
    s = unicodedata.normalize("NFKC", s)
    for a, b in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                 "—": "-", " ": " ", "­": ""}.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def stat_ids():
    if not STAT_FILE.exists():
        return set()
    return set(re.findall(r"^\|\s*([A-Z][A-Z0-9_]+)\s*\|", STAT_FILE.read_text(encoding="utf-8"), re.M))


def walk(blocks, path=()):
    """Yield (block_type, block, path) for every nested block in a body list."""
    for b in blocks or []:
        if "clause" in b:
            yield "clause", b, path
            yield from walk(b.get("body"), path + (str(b["clause"]),))
        elif "table" in b:
            yield "table", b["table"], path
        elif "para" in b or "note" in b or "items" in b:
            yield ("note" if "note" in b else "para" if "para" in b else "items"), b, path
        else:
            raise ValueError(f"Unknown block at {path}: {list(b)}")


def all_parts(doc):
    """Yield (container_label, anchor_key, body) for sections, annexures and circulars."""
    for s in doc.get("sections", []):
        yield f"Section {s['num']}", f"Section {s['num']}", s.get("body", [])
    for a in doc.get("annexures", []):
        yield f"Annexure {a['id']}", f"Annexure {a['id']}", a.get("body", [])
    for c in doc.get("circulars", []):
        yield f"Circular {c['number']}", c["number"], c.get("body", [])


def block_strings(btype, b):
    """All user-visible strings inside one block (not nested clauses)."""
    out = []
    if btype == "clause":
        out += [b.get("title") or "", b.get("term") or "", b.get("text") or ""] + list(b.get("items") or [])
    elif btype == "table":
        out += [b.get("title") or "", b.get("note") or ""] + list(b.get("header") or [])
        out += [c for row in b.get("rows", []) for c in row]
    elif btype in ("para", "note"):
        out.append(b.get("para") or b.get("note"))
    elif btype == "items":
        out += list(b["items"])
    return [str(x) for x in out if x]


def doc_strings(doc):
    """(where, string) for every visible string in the document."""
    for k in ("purpose_line",):
        if doc.get(k):
            yield k, doc[k]
    for label, _, body in all_parts(doc):
        for btype, b, _ in walk(body):
            for s in block_strings(btype, b):
                yield label, s
    for s in doc.get("sections", []):
        yield f"Section {s['num']}", s["title"]
    for a in doc.get("annexures", []):
        yield f"Annexure {a['id']}", a["title"]
    for c in doc.get("circulars", []):
        for k in ("subject", "intro"):
            if c.get(k):
                yield f"Circular {c['number']}", c[k]
    if doc.get("circulars_intro"):
        yield "Circulars", doc["circulars_intro"]

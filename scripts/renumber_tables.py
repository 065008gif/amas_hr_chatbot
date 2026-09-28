"""Renumber 'Table N' ids in one document in order of appearance and update its {ref:#Table N} markers.
Usage: python scripts/renumber_tables.py 002   (prints the mapping; edits content/polNNN_*.yaml in place)"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexdocs.common import doc_path  # noqa: E402

path = doc_path(sys.argv[1])
text = path.read_text(encoding="utf-8")
order = re.findall(r"^\s*id: (Table \d+)\s*$", text, re.M)
mapping = {old: f"Table {i}" for i, old in enumerate(order, 1)}
changed = {o: n for o, n in mapping.items() if o != n}
print("mapping:", changed or "already in order")
if changed:
    text = re.sub(r"(id: |\{ref:#)(Table \d+)\b", lambda m: m.group(1) + "\0" + mapping.get(m.group(2), m.group(2)), text)
    # circular 'amends:' lists name tables without a marker
    text = re.sub(r"^(\s*amends: .*)$", lambda m: re.sub(r"\b(Table \d+)\b",
                  lambda n: "\0" + mapping.get(n.group(1), n.group(1)), m.group(1)), text, flags=re.M)
    path.write_text(text.replace("\0", ""), encoding="utf-8")

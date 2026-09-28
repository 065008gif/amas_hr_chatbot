"""Build policy PDFs from content/*.yaml.

Usage:  python scripts/build_docs.py --doc 001     (one document)
        python scripts/build_docs.py --all         (every document whose YAML exists)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nexdocs.common import existing_doc_ids, load_doc  # noqa: E402
from nexdocs.render import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--doc")
    g.add_argument("--all", action="store_true")
    a = ap.parse_args()
    ids = existing_doc_ids() if a.all else [a.doc]
    for doc_id in ids:
        doc = load_doc(doc_id)
        pdf, m = build(doc)
        target = doc.get("target_pages")
        print(f"{doc_id}  {doc['title']:<50} {m['pages']:>3} pages (target {target})  -> documents/{pdf.name}")


if __name__ == "__main__":
    main()

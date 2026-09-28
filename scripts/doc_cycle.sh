#!/usr/bin/env bash
# One document through the full routine: content check -> build -> PDF check -> traps -> page fill report.
# Usage: bash scripts/doc_cycle.sh 002
set -u
cd "$(dirname "$0")/.." || exit 2
D="$1"; FAIL=0
python scripts/check_content.py --doc "$D" | grep -vE '^  PENDING' ; [ "${PIPESTATUS[0]}" -eq 0 ] || FAIL=1
echo "  pending references (to documents not yet written): $(python scripts/check_content.py --doc "$D" | grep -c '^  PENDING')"
[ $FAIL -eq 0 ] || { echo "STOP: content check failed"; exit 1; }
python scripts/build_docs.py --doc "$D" || exit 1
python scripts/verify_pdfs.py --doc "$D" | sed -n '/^Doc /,$p' ; [ "${PIPESTATUS[0]}" -eq 0 ] || FAIL=1
python scripts/verify_traps.py | grep -E "^(FAIL|     -)|traps checked|RESULT" ; [ "${PIPESTATUS[0]}" -eq 0 ] || FAIL=1
python - "$D" <<'PY'
import sys, pdfplumber
sys.path.insert(0, "scripts")
from nexdocs.common import DOCS, pdf_name
with pdfplumber.open(DOCS / pdf_name(sys.argv[1])) as pdf:
    n = [len((p.extract_text() or "").splitlines()) - 2 for p in pdf.pages]
print("  lines per page:", " ".join(f"p{i}:{x}" for i, x in enumerate(n, 1)))
thin = [i for i, x in enumerate(n, 1) if i > 3 and x < 12]
print("  thin pages (<12 lines, excluding front matter):", thin or "none")
PY
[ $FAIL -eq 0 ] && echo "CYCLE: PASS" || { echo "CYCLE: FAIL"; exit 1; }

#!/usr/bin/env bash
# Scan files that git would commit/push for anything that looks like a secret.
# Usage: bash scripts/secret_scan.sh
# Exit code 0 = clean, 1 = possible secret found (do NOT push).
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2

# Files tracked + staged (what will be pushed). Excludes ignored files like .env.
FILES=$(git ls-files --cached)
echo "Files checked: $(echo "$FILES" | grep -c .)"

PATTERNS=(
  'ghp_[A-Za-z0-9]{30,}'                 # GitHub classic token
  'github_pat_[A-Za-z0-9_]{30,}'         # GitHub fine-grained token
  'gh[ousr]_[A-Za-z0-9]{30,}'            # other GitHub tokens
  'AIza[0-9A-Za-z_-]{30,}'               # Google / Gemini API key
  'hf_[A-Za-z0-9]{30,}'                  # Hugging Face token
  'sk-[A-Za-z0-9_-]{20,}'                # OpenAI-style keys
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'   # private keys
  '(api[_-]?key|secret|token|password)["'"'"' ]*[:=][ "'"'"']*[A-Za-z0-9_./+-]{20,}'  # key = longvalue
)

FOUND=0
for p in "${PATTERNS[@]}"; do
  # shellcheck disable=SC2086
  HITS=$(echo "$FILES" | xargs -r grep -HnIiE -- "$p" 2>/dev/null | grep -v '^scripts/secret_scan.sh:')
  if [ -n "$HITS" ]; then
    echo "POSSIBLE SECRET (pattern: $p):"
    # show file:line and a masked preview only
    echo "$HITS" | sed -E 's/([A-Za-z0-9_-]{6})[A-Za-z0-9_./+-]{10,}/\1**********/g'
    FOUND=1
  fi
done

# Make sure no real env file is tracked
if echo "$FILES" | grep -E '(^|/)\.env(\..*)?$' | grep -vq '\.env\.example$'; then
  echo "WARNING: an .env file is tracked by git"; FOUND=1
fi

if [ "$FOUND" -eq 0 ]; then
  echo "RESULT: CLEAN - no key/token patterns found in files to be pushed."
  exit 0
else
  echo "RESULT: STOP - review the lines above before pushing."
  exit 1
fi

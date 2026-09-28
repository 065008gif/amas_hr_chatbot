# DECISIONS

Each choice made in this project and why. Newest at the bottom of each section.

## Phase 0: Machine, environment and repository

**D-001 (2026-09-28): Reuse the existing conda env `hrbot`.**
The user created it before this session: Python 3.11.16, Node v20.20.2, at `/home/ashok/anaconda3/envs/hrbot`. It won't be recreated. Python packages are installed with `python -m pip`, so they always go into this env's Python and never into the system Python or another env.

**D-002 (2026-09-28): Work only inside `~/hrbot`.**
This is a shared college PC and the `ashok` account has other projects on it (for example `~/financial-rag`). Nothing outside `~/hrbot` is created, edited or deleted.

**D-003 (2026-09-28): LLM goes through the Ollama cloud API, not the local Ollama docker.**
This PC auto-starts a local Ollama server at `http://192.240.4.114:11434`, and we don't use it. The deployed backend (a Hugging Face Space) runs outside the college network and can't reach that address, so a local model would work here but fail once deployed. Instead we call `https://ollama.com/api/chat` with the user's `OLLAMA_API_KEY`, which works the same locally and in deployment. The same reasoning applies to embeddings: see the Part E note, where the embedding model runs inside the backend and never goes through the local Ollama.

**D-004 (2026-09-28): Use a dedicated public GitHub repo on branch `main`.**
The remote is `origin` = `https://github.com/065008gif/amas_hr_chatbot`. Because it's public, anything committed is visible to everyone.

**D-005 (2026-09-28): Set the git identity for this repo only.**
It's `Akshit Kansal <233405113+065008gif@users.noreply.github.com>`, set with `git config` without `--global`, so other users of the shared account aren't affected. The GitHub no-reply email keeps the user's personal email off public commits.

**D-006 (2026-09-28): Never store the GitHub token on this PC.**
Both the repo and `--global` `credential.helper` were checked and neither was set. We then set `credential.helper` to an empty value **for this repo only** (`git config --local credential.helper ""`). An empty value tells git to ignore any helper configured at a higher level, so a token typed at a push prompt is used once and never saved.

**D-007 (2026-09-28): Push at the end of every phase, not only in Phase 8.**
This keeps an off-machine backup of each finished phase, which matters on a shared PC. Claude never runs `git push`, because the user's token can't be entered by Claude. When a push is ready, Claude stops and gives the exact commands, and the user runs them in a second terminal tab.

**D-008 (2026-09-28): Scan for secrets before every push.**
`.gitignore` covers `.env`, `.env.*` (except `.env.example`), key/cert files, credential JSONs and `.git-credentials`, and it was in place before the first commit. Before every push, the files about to be pushed are scanned for patterns that look like API keys or tokens (GitHub `ghp_`/`github_pat_`, Google `AIza`, Hugging Face `hf_`, generic `api_key=`/`token=` assignments, private-key blocks), and the result is shown to the user. When `.env` is created it gets `chmod 600`, so other accounts can't read it.

**D-009 (2026-09-28): Skip the GitHub account step in Phase 1.**
The user already has an account (`065008gif`).

## Phase 1: Accounts, keys and connectivity

**D-010 (2026-09-28): Ollama cloud `gpt-oss:120b` works with our key.**
Test: `scripts/test_ollama.sh` → HTTP 200, content `'ready'`, 72 input / 52 output tokens, server-side `total_duration` 0.44 s. The response **does** include a `thinking` field (the model's reasoning). The backend reads only `message.content` and never shows, logs or stores `thinking`.

**D-011 (2026-09-28): The college DNS is slow, so the backend reuses one HTTP connection and uses a 30 s timeout.**
The first call took 36.7 s in total, even though the server-side time was 0.44 s. `curl` timings showed the delay was DNS lookup (10 s, 5 s, then 0.009 s). `getent` confirmed that the first uncached lookup of `ollama.com` takes about 5.0 s, and a repeat takes 0.013 s. The system resolver forwards to college DNS `192.240.1.6`/`.5` (then 8.8.8.8, 1.1.1.1). Once connected, a full reply takes about 1.0 s.
We don't change the system DNS, because that's outside `~/hrbot` on a shared PC. Instead, the backend uses a single persistent `httpx` client (keep-alive, so the DNS lookup happens once per process) plus the answer cache. The brief's 30 s timeout is kept and is enough.
This is a local-network issue only. The Hugging Face Space uses its own DNS, and we'll re-measure latency there in Phase 8.

**D-012 (2026-09-28): Ollama free-tier limits are UNVERIFIED.**
Ollama doesn't publish exact free-tier numbers in a form we could check here. We treat them as unknown and design for them: an answer cache, one retry, failover to Gemini, and a friendly message on HTTP 429. The user can see actual usage on their ollama.com account page.

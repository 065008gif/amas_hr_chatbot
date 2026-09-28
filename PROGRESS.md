# PROGRESS

Project: Nia, HR helpdesk RAG chatbot for the fictional Nexora Technologies Limited.
Full brief: `MASTER_PROMPT.md`. Working protocol: Part A (one step at a time, show real output, wait for user).

## Resume instructions for a new session
1. Read `MASTER_PROMPT.md` fully, then this file, then `DECISIONS.md`.
2. Environment: conda env `hrbot` (Python 3.11.16, Node v20.20.2) at `/home/ashok/anaconda3/envs/hrbot`. Do NOT recreate it. Install Python packages with `python -m pip`.
3. Never touch anything outside `~/hrbot` (shared PC). Git identity is repo-local only, never `--global`.
4. LLM: Ollama **cloud** API (`https://ollama.com/api/chat`). Do NOT use the local Ollama docker at `http://192.240.4.114:11434` (DECISIONS D-003).
5. Git: remote `origin` = https://github.com/065008gif/amas_hr_chatbot (public), branch `main`. Repo-local `credential.helper` is empty, so the token is never saved.
6. **Push at the end of EVERY phase.** Before each push, run the secret scan and show the result. Claude does NOT run `git push`: it gives the user the exact commands to run in a second terminal tab (DECISIONS D-007, D-008).
7. Continue from the first unchecked item under "Next".

## Done
- [x] Phase 0, Steps 1-3: terminal, tool check, conda env `hrbot` (done by user before this session)
- [x] Phase 0, Step 4: created folders `content/ documents/ backend/ frontend/ data/ tests/ scripts/`
- [x] Phase 0, Step 5: `git init -b main`, repo-local identity (Akshit Kansal / GitHub no-reply email), credential.helper blanked for this repo (global was unset), remote `origin` added, `.gitignore` created before the first commit
- [x] Phase 0, Step 6: `DECISIONS.md` (D-001 to D-009) and `PROGRESS.md`
- [x] Phase 0, first commit made on `main`
- [x] **Phase 0 pushed** by user. Verified: `origin/main` = `6000955` = local `main` (`git ls-remote`). No token saved (repo credential.helper blank, no `~/.git-credentials`).
- [x] Phase 1, Step 1 (prep): `.env.example` (fake values, tracked); `.env` created with empty `OLLAMA_API_KEY=` / `GEMINI_API_KEY=`, `chmod 600` (`-rw-------`), confirmed ignored by git; `scripts/test_ollama.sh` written (reads key without printing it, shows HTTP code, time, content, whether `thinking` is present, token counts).
- [x] Phase 1, Step 1 DONE: user added the key; `bash scripts/test_ollama.sh` → HTTP 200, content 'ready', `thinking` field present (never shown to users). Slow first call (36.7 s) traced to college DNS (about 5 s per uncached lookup); the model itself takes about 1 s. DECISIONS D-010 to D-012. Committed locally (push at end of Phase 1).
- [x] Phase 1, Step 2 DONE: Gemini key works. `gemini-2.5-flash` gives 404 (retired for new users); `gemini-3.8-flash`, `gemini-flash-latest` and `gemini-3.5-flash-lite` gave 503 (high demand); **`gemini-3.1-flash-lite` → 200 'ready'** (now the test script default). DECISIONS D-013. Re-test `gemini-3.8-flash` in Phase 5.

## Next
- [ ] Phase 1, Step 3: free-tier limits explained (UNVERIFIED) and the coping design written into DECISIONS
- [ ] Phase 1, Steps 4-5: network test (huggingface.co, github.com, vercel.com, pypi.org), embedding model download and timing
- [ ] Phase 1, Step 6: Hugging Face and Vercel accounts (GitHub already exists, skip)
- [ ] End of Phase 1: secret scan, commit, user pushes

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

## Next
- [ ] **User pushes Phase 0** (`git push -u origin main`) from a second terminal tab. Confirm with `git log origin/main --oneline`.
- [ ] Phase 1, Step 1: Ollama cloud API key in `.env` (user types it with nano; `chmod 600 .env`), then a curl test of `gpt-oss:120b`
- [ ] Phase 1, Step 2: Gemini key and curl test
- [ ] Phase 1, Steps 3-5: free-tier limits, network test (huggingface.co, github.com, vercel.com, pypi.org), embedding model download and timing
- [ ] Phase 1, Step 6: Hugging Face and Vercel accounts (GitHub already exists, skip)
- [ ] End of Phase 1: secret scan, commit, user pushes

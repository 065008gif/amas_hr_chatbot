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

- [x] Phase 1, Step 3 DONE: header check showed no rate-limit headers from either provider; Gemini 3.1-flash-lite gave 503 about 10 min after a 200 (flaky). Limits recorded as UNVERIFIED; 9-point coping design in DECISIONS D-014 (to implement in Phase 5).

- [x] Phase 1, Step 4 DONE: all needed hosts reachable, no TLS interception, about 32 MB/s from PyPI; occasional 5-15 s DNS stalls only (D-015).
- [x] Phase 1, Step 5 DONE: `fastembed` 0.8.1 + `BAAI/bge-small-en-v1.5` installed and cached in `.cache/fastembed`. 100 chunks embed in 1.90 s (28 cores) / 5.92 s (2 threads); query 3-5 ms; sanity PASS. `scripts/test_embeddings.py` (D-016). Scripts must set `HF_HOME=~/hrbot/.cache/huggingface`.

- [x] Phase 1, Step 6 DONE: Hugging Face `Akshit065008` (email verified; API lookup HTTP 200); Vercel via GitHub `065008gif`. GitHub already existed. (D-018)
- [x] **Phase 1 CHECK PASSED** (2026-09-28): Ollama `gpt-oss:120b` → 200 'ready' (after one connect timeout on the college network, see D-017); Gemini `gemini-3.1-flash-lite` → 200 'ready'; connectivity recorded in D-015. Secret scan CLEAN.

- [x] **Phase 1 pushed**: verified `origin/main` = `61c1506` = local.
- [x] Scope change D-019: about 150 pages total (targets ±2: Leave 16, Handbook 26, POSH 14, CoC 18, Comp 20, Attendance 12, Travel 14, Separation 14, IT 16). Keep chat output lean (checker results, page counts, first 2 pages' text only).

- [x] Phase 2 build plan approved by user.
- [x] Phase 2 tooling (D-020): `content/_company.yaml`, `content/STATUTORY_CLAIMS.md` (1 entry so far), `content/traps.yaml` (empty), `scripts/nexdocs/{common,render}.py`, `scripts/build_docs.py`, `scripts/check_content.py`, `scripts/verify_pdfs.py`, `scripts/verify_traps.py`. Packages: reportlab 5.0.1, PyYAML 6.0.3, pdfplumber 0.11.10. Self-test passed plus negative tests (9/9 errors caught, 2/2 TOC tampering caught); self-test files deleted.

- [x] Phase 2, doc 001 Leave Policy: 15 pages (target 16 ±2), TOC 20/20, footers 14/14, content check 0 errors / 0 warnings, traps T01-T08 verified (types 1,3,4,5,6). Conflicts C01, C02 registered for docs 002 and 008. D-021.

- [x] Phase 2, doc 002 Employee Handbook: 24 pages (target 26 ±2), TOC 42/42, 0 errors/warnings, traps T09-T12 verified (all 6 types now covered). Conflicts C01 and C04 planted. D-022. Helper: `bash scripts/doc_cycle.sh NNN` runs the whole routine; `python scripts/renumber_tables.py NNN` fixes table order.

- [x] Phase 2, doc 003 POSH: 12 pages (target 14 ±2), TOC ok, traps T13-T14 verified. Renderer blank-page bug fixed (D-023). Running total 51 pages / 14 traps.

- [x] Phase 2, doc 004 Code of Conduct: 16 pages (target 18 ±2), traps T15-T18 verified, conflict C03 planted (D-024). Running total 67 pages / 18 traps.

- [x] Phase 2, doc 005 Compensation: 18 pages (target 20 ±2), traps T19-T22 verified (D-025). Running total 85 pages / 22 traps. Sizing rule: about 500 words per full page.

- [x] Phase 2, doc 006 Attendance: 11 pages (target 12 ±2), traps T23-T25 verified; 25 traps reached (D-026). Running total 96 pages.

- [x] Phase 2, doc 007 Travel: 12 pages (target 14 ±2), traps T26-T28 verified (D-027). Running total 108 pages / 28 traps.

- [x] Phase 2, doc 008 Separation: 12 pages (target 14 ±2), traps T29-T32 verified; conflicts C02 and C04 complete (D-028). Running total 120 pages / 32 traps. NEXT: doc 009 IT Security, then final all-document checks.

- [x] Phase 2, doc 009 IT Security: 14 pages, traps T33-T36 (D-029).
- [x] **Phase 2 FINAL CHECKS PASSED** (D-030): 9 PDFs, 134 pages, all within target ±2; TOC 260/260; footers 125/125; 0 errors/warnings/pending refs; 36/36 traps verified (types 1:12, 2:4, 3:10, 4:4, 5:3, 6:3); 98 statutory claims, all UNVERIFIED.

- [x] USER pushed Phase 2; verified `origin/main` = `6239b9c` = local. `verify_traps.py --final` re-run: 36/36 PASS.
- [x] **Phase 3 ingestion DONE** (D-031 to D-033): `backend/config.py`, `backend/indexstore.py`, `backend/ingest.py`, `tests/verify_chunks.py`. `python -m backend.ingest` gives 9 docs, 134 pages, 386 chunks (clause 231, table 81, annexure 39, circular 29, definition 6), 202 tokens average (median 193), largest 438, 0 over 600. Manifest cross-check 918/918. Chunk page check 30/30 (seed 42) and 386/386 (`--all`); negative control 386/386 caught. Cold load 0.35 s. Index committed in `backend/index/` (2.2 MB).

- [x] Phase 3 pushed (verified `origin/main` = `3862e4c`).
- [x] **Phase 4 retrieval DONE** (D-035): `backend/retrieve.py`, `tests/retrieval_dev.yaml`, `tests/retrieval_eval.py` -> `tests/results/retrieval_eval.{json,md}`. TEST (traps) recall@8 0.939, MRR 0.732; DEV recall@8 0.925. Threshold 0.0015 (0 answerable refused). Follow-ups 5/5.

- [x] **Phase 5 backend DONE** (D-036, D-037): FastAPI endpoints `/chat /health /ticket /ticket/{id} /tickets /leave-balance /docs-list /pdf/{doc_id} /demo-employees /me /circulars /insights`. Route tour: all routes demonstrated. Run locally: `uvicorn backend.app:app --port 8000`, then `python scripts/ask.py --demo`.

- [x] **Phase 6 frontend DONE** (D-038): `frontend/` React + Vite portal. Local run: terminal 1 `uvicorn backend.app:app --port 8000`; terminal 2 `cd frontend && npm run dev`, then open http://localhost:5173.

## Per-document routine (use for every document)
`python scripts/check_content.py --doc NNN` -> `python scripts/build_docs.py --doc NNN` -> `python scripts/verify_pdfs.py --doc NNN --show 2` -> `python scripts/verify_traps.py`. Adjust content until pages are within target ±2. Add statute figures to STATUTORY_CLAIMS.md, add traps to content/traps.yaml, add cross-document conflicts to `planned_conflicts` in `_company.yaml`. Show the user ONLY checker results, the page count and pages 1-2 text. Commit each document.

## Next
- [ ] FAST-TRACK (D-034): Phase 5 backend -> Phase 6 portal frontend -> Phase 8 deploy -> Phase 7 full evaluation (batched, resumable).
- [ ] Phase 5 will need a `requirements.txt` (so far: pdfplumber, fastembed, rank-bm25, numpy, PyYAML, reportlab).

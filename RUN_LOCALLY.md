# Running Nia on your own PC

This guide takes a new computer from nothing to a working copy of the project: the portal and chatbot running locally, the tests, and a rebuild of the policy PDFs and the search index.

**What was tested (29 September 2026):** the Linux steps were run for real in a fresh virtual environment and a fresh clone on Ubuntu, and the expected output shown below was copied from those runs. **The Windows steps have not been tested**, because only a Linux PC was available. They use the standard Windows equivalents of the same commands. If a Windows step fails, the Linux section shows what should happen.

Versions used: Python **3.11**, Node **20** (20.20.2), npm 10.8.2, git.
> `.python-version` says 3.12. That file is only for Vercel's build; local work uses 3.11.

---

## 1. Install Python 3.11, Node 20 and git

### Linux (Ubuntu), with Miniconda (no admin rights needed)
1. Download Miniconda for Linux from the Miniconda page on docs.anaconda.com and install it:
   ```bash
   bash Miniconda3-latest-Linux-x86_64.sh      # accept the licence, then answer "yes" to initialise conda
   ```
   Close and reopen the terminal.
2. Create one environment containing Python, Node and git:
   ```bash
   conda create -n hrbot -c conda-forge python=3.11 nodejs=20 git -y
   conda activate hrbot
   python --version     # Python 3.11.x
   node --version       # v20.x
   git --version
   ```
   `which python` must contain `envs/hrbot`.

(Without conda: `sudo apt install python3.11 python3.11-venv git`, then Node 20 from nodejs.org, and use `python3.11 -m venv .venv` in step 3.)

### Windows 10/11
1. **Python 3.11:** on python.org, open Downloads → Windows, pick the latest **3.11.x** "Windows installer (64-bit)". In the installer, **tick "Add python.exe to PATH"**. Or, in PowerShell:
   ```powershell
   winget install -e --id Python.Python.3.11
   ```
2. **Node 20:** on nodejs.org, open the downloads page, choose **v20.x (LTS)** and the Windows Installer (.msi).
3. **Git:** `winget install -e --id Git.Git`, or the installer from git-scm.com. This also installs **Git Bash**, which the `.sh` scripts need.
4. Open a **new** PowerShell window and check:
   ```powershell
   py -3.11 --version   # Python 3.11.x
   node --version       # v20.x
   git --version
   ```

---

## 2. Get the code

```bash
git clone https://github.com/065008gif/amas_hr_chatbot.git hrbot
cd hrbot
```
The clone is about 190 MB, because the two search models are committed under `backend/models/` (66 MB and 23 MB) so that nothing has to be downloaded later.

---

## 3. Create the Python environment and install the requirements

There are three requirement files:

| File | What it is |
|---|---|
| `requirements.txt` | Only what the deployed backend needs (Vercel uses this). |
| `requirements-dev.txt` | The full local toolchain (server, PDFs, ingestion, tests). Direct dependencies, pinned. |
| `requirements-lock.txt` | **Every** package including indirect dependencies, pinned exactly as tested (44 packages). |

### Linux
```bash
# with conda (step 1): the environment is already active
python -m pip install -r requirements-lock.txt
# or with a plain venv:
python3.11 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements-lock.txt
```

### Windows (PowerShell)
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
```
If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again. If one pinned package has no Windows build, install `requirements-dev.txt` instead; it pins only the direct dependencies and lets pip choose compatible versions of the rest.

**Expected:** pip ends without errors. Check it:
```bash
python -c "import fastapi, onnxruntime, tokenizers, pdfplumber, reportlab, rank_bm25; print('ok')"
```

---

## 4. Create `.env` with your own keys

The keys never go into git. `.env` is listed in `.gitignore`.

```bash
cp .env.example .env        # Windows: copy .env.example .env
nano .env                   # Windows: notepad .env
```
Replace `changeme` with your own keys:
- `OLLAMA_API_KEY`: from your account settings on ollama.com (API keys).
- `GEMINI_API_KEY`: from Google AI Studio (the fallback model; optional but recommended).

Leave `CORS_ORIGINS` as it is. The Upstash lines stay commented out: without them, tickets and the cache are stored locally in SQLite under `data/runtime/`.

Never paste a key into a chat, a screenshot or a commit.

---

## 5. Install and build the frontend

```bash
cd frontend
npm ci              # installs exactly what package-lock.json says
npm run build       # production build into frontend/dist
cd ..
```
**Expected:** `added 70 packages`, then `✓ built in …ms`.
(`npm ci`, not `npm install`, so the lockfile is followed exactly. A clean `npm ci` left `package-lock.json` unchanged in testing.)

---

## 6. Run the app locally

Two terminals, both in the `hrbot` folder with the Python environment active.

**Terminal 1: backend (FastAPI)**
```bash
python -m uvicorn api.index:app --port 8000
```
Expected: `Uvicorn running on http://127.0.0.1:8000`.

**Terminal 2: portal (React + Vite, development mode)**
```bash
cd frontend
npm run dev
```
Expected: `VITE v8.3.1 ready in …ms` and `Local: http://localhost:5173/`.

Open **http://localhost:5173** in a browser. The portal calls `/api/...`, which Vite forwards to the backend on port 8000, the same layout as on Vercel. You'll see the "waking up" screen for about a second, then the sign-in page with the five demo employees.

To try the production build instead of development mode (after step 5), replace Terminal 2 with:
```bash
cd frontend
npx vite preview --port 4173      # then open http://localhost:4173
```
This also forwards `/api` to port 8000 (tested: `/`, `/chat` and `/api/health` all answered).

### Check the running app (3 real questions, uses a little model quota)
Linux terminal, or **Git Bash** on Windows:
```bash
bash scripts/smoke_test.sh http://localhost:5173
```
Expected (tested, 29 Sep 2026):
```
   status: ok | chunks: 386 | ...
   /         HTTP 200
   ...
-- Q: How many days of paternity leave do I get for a baby born in August 2025?
   route: answer | provider: ollama | ...
   cite: Leave Policy, p. 15, Circular HR/CIR/2025/07 (page verified)
...
-- Q: Does Nexora pay for egg freezing?
   route: not_found | ...
== SMOKE TEST PASSED
```
Stop the servers with Ctrl+C in each terminal.

---

## 7. Run the tests

### Offline checks (no model calls, no quota; about 2 minutes in total)
```bash
python tests/check_safety_routing.py     # -> 29/29 as expected
python tests/check_eval_set.py           # -> RESULT: PASS  (every gold fact is on its PDF page)
python tests/verify_chunks.py --all      # -> RESULT: PASS  (386/386 chunks on their pages; negative control 386/386)
python tests/retrieval_eval.py           # -> TEST recall@8 = 0.939 (target 0.9), MRR = 0.733.  RESULT: PASS
python tests/check_store_backends.py     # -> RESULT: PASS  (SQLite and a fake Upstash)
```
These were run in a completely fresh environment built from `requirements-lock.txt`, and gave exactly the numbers above.

### Model-based evaluations (use quota; results vary a little from run to run)
The runners **skip items already in their result files**, which are committed. To re-run from scratch, first move the old runs aside:
```bash
mkdir -p tests/results/old
mv tests/results/answer_eval_runs.jsonl tests/results/multiturn_runs.jsonl tests/results/adversarial_runs.jsonl tests/results/old/
python tests/answer_eval.py --limit 40      # repeat until everything is done (it resumes by itself)
python tests/multiturn_eval.py --part conversations
python tests/multiturn_eval.py --part paraphrases
python tests/adversarial_eval.py
python tests/answer_eval.py --score && python tests/multiturn_eval.py --score && python tests/adversarial_eval.py --score
python tests/write_results.py              # rebuilds tests/results/RESULTS.md
```
About 300 model calls in total. The runners pause between calls and stop by themselves after 3 provider failures in a row, so a run can be continued later. Evaluation logs go to `data/runtime/eval/`, never to the live site.

Live-site timings (they send requests to the deployed site): `python tests/latency.py --warm`, then `python tests/latency.py --report`.

---

## 8. Rebuild the policy PDFs and the search index (optional)

The PDFs (`documents/`) and the index (`backend/index/`) are committed, so you only need this if you change the policy sources in `content/`.

```bash
python scripts/build_docs.py --all              # -> 9 PDFs; "IT, Information Security ... 14 pages"
python scripts/check_content.py --all --final   # -> 0 errors, 0 warnings, 0 pending references; RESULT: PASS
python scripts/verify_pdfs.py --all             # -> Total pages: 134; RESULT: PASS
python scripts/verify_traps.py --final          # -> 36 traps checked, 36 verified, 0 failed; RESULT: PASS
python -m backend.ingest                        # -> 918/918 ... found on the right page; 386 chunks; about 50 s
python tests/verify_chunks.py --all             # -> RESULT: PASS
```
Notes from the test rebuild in a fresh clone:
- The rebuilt PDFs are identical in content but not byte for byte (ReportLab stamps the creation time), so git shows them as modified. Use `git checkout -- documents` to go back to the committed ones.
- Ingestion uses the bundled model files in `backend/models/`, so it needs no download. Rebuilding from the committed PDFs gave an **identical** index: the same 386 chunks, identical keyword tokens, and identical vectors. Only `backend/index/index_meta.json` changes (build time).
- `python scripts/make_employees.py` regenerates the 300 demo employees in `data/employees.csv`.

To rebuild the project report (`report/Nia_HR_Helpdesk_Report.docx`):
```bash
cd report && npm ci && npm run build
```

---

## 9. Before pushing anything
```bash
bash scripts/secret_scan.sh      # must end with: RESULT: CLEAN
```
Git Bash on Windows. Never commit `.env`.

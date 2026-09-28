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

**D-013 (2026-09-28): Gemini fallback uses `gemini-3.1-flash-lite` for now and keeps an ordered list of models to try.**
The AI Studio key works: the model list call succeeded. Test results on 2026-09-28, about 17:35 IST:
- `gemini-2.5-flash` → **404**, "no longer available to new users". Google recommended `gemini-3.8-flash`.
- `gemini-3.8-flash` → **503 UNAVAILABLE**, "high demand", twice (3.0 s and 23.6 s).
- `gemini-flash-latest` → 503. `gemini-3.5-flash-lite` → 503.
- `gemini-3.1-flash-lite` → **HTTP 200, content `'ready'`**, 4.7 s.

Consequences:
1. The config holds an **ordered list** of Gemini models. It starts with `gemini-3.1-flash-lite` (proven to work), then `gemini-3.8-flash`. A 503 on one model moves on to the next, and everything is still subject to the 30 s timeout.
2. The backend treats **503 like 429**: retry once, fail over, and show a friendly message. It never shows the raw error.
3. We'll re-test `gemini-3.8-flash` in Phase 5. If it's reliably available, it may go first, because it's a stronger model.
4. Model names and availability change often. This is threat A5 ("model deprecation") in the report, and we've already seen it happen once (the `gemini-2.5-flash` 404).

**D-014 (2026-09-28): Free-tier limits are unknown, so the code is built to cope with them.**
*What we measured:* one small request to each provider, looking at the response headers. Ollama (HTTP 200) returned **no rate-limit headers**. Gemini `gemini-3.1-flash-lite` returned **HTTP 503**, only about 10 minutes after the same model returned 200 (D-013), and also had no rate-limit headers. So neither API tells us its limits in advance.
*What we believe but have NOT verified (all UNVERIFIED):*
- Ollama cloud's free plan has usage limits that reset over time (for example hourly or daily). The exact numbers are shown only in the user's ollama.com account and may change.
- Gemini's free tier limits each model by requests per minute, requests per day and tokens per minute. The numbers vary by model and change often. The user's own figures are on the AI Studio usage/rate-limit page.
- Both providers may use free-tier traffic to improve their services. See the privacy notice planned for the About page (question B4).

*Coping design (implemented in Phase 5, with all values in the single config file):*
1. **Answer cache.** SQLite, keyed on the normalised question plus the profile (grade, location). A repeated question costs no quota and gives the identical answer (question F7).
2. **Few model calls per turn.** Regex safety and escalation rules run first, with no model call. Greetings, the leave-balance tool and ticket status need no model call. The intent classification and the follow-up rewrite share one small JSON call. So there are at most 2 model calls per chat turn.
3. **Small requests.** Only the top 6 to 8 chunks go in the prompt, and the output-token cap is set in the config.
4. **Timeouts and retries.** 30 s timeout. One retry with a short backoff on timeouts and 5xx errors. On a 429 we honour `Retry-After` if present and never loop.
5. **Failover.** Ollama `gpt-oss:120b` first, then the ordered Gemini list (D-013). The first provider that answers wins.
6. **Circuit breaker.** A provider that fails 3 times in a row is skipped for 60 s, so users don't wait through a timeout on every request.
7. **Friendly messages.** On 429: "The free model limit was reached, please try again shortly." On 503 or all-down: "The AI service is busy right now, please try again in a minute." Users never see a raw error. `/health` shows each provider's last status.
8. **Protecting quota on the public link.** A per-IP rate limit, 800 characters per message and 20 turns per session.
9. **Evaluation runs in batches.** Phase 7 scripts are throttled (a pause between calls), resumable (results saved after each question) and use the cache, so a run can be spread over several sessions or days if limits are hit.

**D-015 (2026-09-28): The college network can reach every service we need, so no workaround is required.**
Test with `curl` on 2026-09-28. Every host answered, with the one-off exception noted below:
- huggingface.co 200, github.com 200, vercel.com 200, pypi.org 200, api.github.com 200, api.vercel.com 308, registry.npmjs.org 200, www.netlify.com 200, generativelanguage.googleapis.com 404 (normal for the bare API root).
- The download CDNs `files.pythonhosted.org`, `cdn-lfs.hf.co` and `cas-bridge.xethub.hf.co` answered 403 or 404 on the bare root. That's normal: they only serve specific files, and they were proven to work by the real downloads below.
- ollama.com timed out once at 25 s, then answered 3/3 retries in 0.56 to 0.85 s. This matches the slow-DNS pattern in D-011 (the first lookup of a name often takes about 5 s, and once 15 s for huggingface.co).
- There's no HTTPS interception. github.com's certificate is issued by Sectigo, the real public issuer, not a college proxy.
- Download speed from PyPI: 22.5 MB in 0.70 s, about **32 MB/s**. No phone hotspot is needed.
Consequence: `git push`, `pip install`, `npm install` and model downloads can all be done from this PC. Tools may occasionally stall about 5 to 15 s on DNS. That's harmless: we retry rather than treat it as a block.

**D-016 (2026-09-28): Embeddings use `BAAI/bge-small-en-v1.5` through `fastembed` (ONNX, CPU), for both the index and queries.**
- **Why fastembed and not sentence-transformers:** fastembed runs on ONNX Runtime (onnxruntime 1.30.0, a wheel of about 22 MB) with no PyTorch. PyTorch alone is hundreds of MB, which would slow the Docker build and the cold start of the free Space. Installed: fastembed 0.8.1, with `pip --no-cache-dir` so nothing is written to `~/.cache`.
- **Why this model:** it's small, has 384-dimensional vectors, is English, and is a strong retriever for its size. The same model embeds the documents and the queries, so the vectors match. It runs inside the backend and needs no external API, so it works when deployed and costs no quota.
- **Measured (`python scripts/test_embeddings.py`), with 100 chunks of about 286 tokens each:**
  - model download + load: 11.4 s the first time; about 65 MB in `~/hrbot/.cache/fastembed` (git-ignored)
  - embedding 100 chunks: 1.90 s using all 28 cores of this PC; **5.92 s limited to 2 threads** (like a free Space)
  - one query: 3 ms (5 ms on 2 threads)
  - sanity check PASS: "How many days of paternity leave do I get?" put 3 paternity-leave chunks at the top (cosine about 0.82)
- **Consequence:** the full index (expected to be a few thousand chunks) is built **once, on this PC**, and shipped inside the Docker image. The Space only embeds the user's query, which is milliseconds. The model files must also be baked into the image, so a sleeping Space doesn't re-download 65 MB on wake-up. That will be done in Phase 8.
- Caches are kept inside the project by setting `HF_HOME=~/hrbot/.cache/huggingface` and `cache_dir=~/hrbot/.cache/fastembed`. We checked that nothing was created outside `~/hrbot`.

**D-017 (2026-09-28): The college network sometimes drops a connection, so the backend uses a short connect timeout and retries.**
During the Phase 1 check, `scripts/test_ollama.sh` failed with `curl: (28) Connection timed out after 60000 milliseconds`. The request never connected at all. The very next 4 attempts all succeeded (HTTP 200, connect 0.03 to 0.31 s, total 0.97 to 4.5 s), and so did a re-run of the test script (200, `'ready'`, 2.3 s). A similar one-off timeout happened in the network test (D-015). ollama.com resolves to a single IPv4 address (34.36.133.15), so this isn't an IPv6 problem. It's an intermittent drop on the local network. Across the Ollama requests counted in D-010, D-011, D-014, D-015 and D-017, **2 of about 16** failed to connect.
Design change for Phase 5: split the timeout into **connect = 10 s** and **read = 30 s** (both in the config). A stuck connection then fails fast and goes to the one retry or failover, instead of using up the whole 30 s. The deployed Space isn't on this network, and we'll re-measure there in Phase 8.

**D-018 (2026-09-28): Hosting accounts were created by the user.**
- Hugging Face: username `Akshit065008`, email verified. We confirmed the account exists: `huggingface.co/api/users/Akshit065008/overview` returned HTTP 200. The backend Space URL will look like `https://akshit065008-<space-name>.hf.space` (the exact form will be confirmed when the Space is created in Phase 8).
- Vercel: Hobby (free) plan, signed up with GitHub `065008gif`.
- No Hugging Face token, Space or Vercel project has been created yet. Those come in Phase 8.

## Phase 2: Policy documents

**D-019 (2026-09-28): The page target is reduced from at least 220 to about 150 pages, at the user's request.**
Reason: to preserve the user's Claude Pro usage limit. Writing the document text is the largest single cost in the project.
New per-document **targets** (not minimums), each within about ±2 pages:

| # | Document | No. | Target |
|---|---|---|---|
| 1 | Leave Policy | NTL/HR/POL/001 | 16 |
| 2 | Employee Handbook | NTL/HR/POL/002 | 26 |
| 3 | POSH Policy | NTL/HR/POL/003 | 14 |
| 4 | Code of Conduct and Ethics | NTL/HR/POL/004 | 18 |
| 5 | Compensation and Benefits | NTL/HR/POL/005 | 20 |
| 6 | Attendance, Hybrid Work and Overtime | NTL/HR/POL/006 | 12 |
| 7 | Travel and Expense Reimbursement | NTL/HR/POL/007 | 14 |
| 8 | Separation and Exit | NTL/HR/POL/008 | 14 |
| 9 | IT, Information Security and Acceptable Use | NTL/HR/POL/009 | 16 |
| | **Total** | | **150** |

Everything else in the brief is unchanged: all 9 documents, cover, document control, version history, a TOC with verified page numbers, definitions, L1 to L8 grade tables, amendment circulars that override body clauses, annexures, cross-references, and at least 25 verified traps. The reduction comes from **fewer clauses per section**, never from lower realism or density, and there's no filler.
Effect on the report: we cite "about 150 pages across 9 documents", not 220. Retrieval is still a real problem at this size (hundreds of chunks, many near-identical grade tables and clauses). Also at the user's request, chat output is kept lean: only checker results, page counts and the first two pages' extracted text are shown, never full document contents.

**D-020 (2026-09-28): Phase 2 tooling design (approved by the user before any document text was written).**
- **Content:** one YAML file per document in `content/`, plus `content/_company.yaml`, the single source of truth. It holds the company, grades, locations, contacts (reserved `.example` domain only), the document register, the precedence order and the planned cross-document conflicts.
- **Markers inside the text** (`{ref:...}`, `{doc:...}`, `{stat:ID|text}`) turn every cross-reference and legal figure into something a script can check. The checker also warns when a reference is typed by hand without a marker.
- **Renderer:** `scripts/nexdocs/render.py` using ReportLab 5.0.1. `multiBuild` gives a TOC with final page numbers. A deferred canvas draws the "Page N of M" footer. `LongTable` repeats the header row when a table splits across pages. The cover has no header or footer, but every page counts, so the footer "Page N" = the physical page = the page used in citations. PDF bookmarks are included.
- **Anchors:** zero-size markers record the physical start and end page of every section, clause, table, annexure and circular into `documents/manifest/NNN.json`. Trap page numbers are taken from the PDF text, and must also fall inside the anchor's page range. They're never typed by hand.
- **Reading PDFs: `pdfplumber` 0.11.10, not `pypdf`.** It keeps word positions and table rows better, which matters for "never cut a table mid-row" in Phase 3. The checkers use the same reader as ingestion, so they test exactly the text the bot will see.
- **Currency is written as "Rs."/"INR", not ₹.** The standard PDF fonts have no ₹ glyph, and a missing glyph would also break text extraction.
- **Defined terms** are written with initial capitals ("Working Day"), as in real Indian policy documents. The checker warns if a defined term is ever used in lower case.
- **Layout fix found during the self-test:** a caption kept together with a long table pushed the whole table to the next page and left a mostly empty page. Now only tables of 12 rows or fewer stay with their caption. A long table starts on the current page if at least 45 mm is free, and otherwise moves to the next page.
- **Checkers were tested against deliberately broken content.**
  - `check_content.py` caught 9 of 9 planted errors: clause numbering gap, invalid grade L9, short table row, broken grade table, unknown statute ID, broken clause reference, broken table reference, a circular amending a missing clause, and a repeated sentence. It also warned on the planted hand-typed reference.
  - `verify_pdfs.py` caught 2 of 2 tampered TOC page numbers.
  - The self-test document was then deleted.

**D-021 (2026-09-28): Leave Policy (NTL/HR/POL/001) is complete: 15 pages against a target of 16 ±2.**
- 12 sections, 100 clauses, 7 tables (5 numbered), 4 annexures (form and checklist, holiday list, escalation matrix, FAQs and illustrations) and 3 amendment circulars that override body clauses (HR/CIR/2025/07 paternity, 2025/11 combining CL with EL, 2026/02 bereavement). About 5,900 words.
- **Traps T01 to T08** (8 in total) cover types 1, 3, 4, 5 and 6, and all were verified on the PDF pages. Type 2 needs a second document; conflicts C01 (paternity, against the Handbook) and C02 (EL encashment on exit, against the Separation Policy) are registered in `_company.yaml`, to be planted when those documents are written.
- 11 statutory claims were added to `STATUTORY_CLAIMS.md`: Maternity Benefit Act figures, the polling-day holiday, and the Shops and Establishments Acts of the 5 States. All are UNVERIFIED.
- **Layout fixes found by looking at the rendered pages:**
  - A section heading was orphaned at the foot of a page, because `keepWithNext` bound it to a zero-size anchor. Headings are now wrapped in `KeepTogether` with their first real paragraph.
  - There were two near-empty pages (the end of Section 12, and the last circular). Section 12 gained real clauses (12.4 confidentiality of medical documents, 12.5 no adverse treatment, 12.6 queries) and the circular wording was tightened. 16 pages became 15, with no filler.
- **Known issue for Phase 3:** in plain text extraction, a wrapped table cell interleaves with its neighbouring columns (for example, the version history rows). Ingestion must extract tables with pdfplumber's table extractor (cell by cell) and not from the plain page text.
- Wording: "last working day" was changed to "last day of service", so it isn't confused with the defined term "Working Day" (the checker warned about this).

**D-022 (2026-09-28): Employee Handbook (NTL/HR/POL/002) is complete: 24 pages against a target of 26 ±2.**
- 31 sections, 17 tables and 8 annexures (contacts, joining checklist, acknowledgement form, FAQs, glossary, HR calendar, workplace scenarios, policy directory), plus 2 circulars (HR/CIR/2025/09 day-care Rs. 8,000 → 10,000; HR/CIR/2026/01 internal job posting eligibility 12 → 9 months). About 10,400 words.
- It carries the policy hierarchy (Clause 1.3) and **plants conflicts C01** (paternity 5 Working Days, Clause 6.2) **and C04** (L5 notice 60 days, Table 7; to be contradicted by the Separation Policy). It governs creche, relocation (a grade-linked Table 8), the referral scheme and probation.
- New traps: T09 (type 2: Handbook vs Leave Policy circular), T10 (type 3: no referral bonus for L7/L8), T11 (type 1: day-care circular), T12 (type 5: egg freezing not covered). **All six trap types are now represented.**
- **First draft was too thin:** 5,444 words gave 15 pages. Genuine sections were added (relocation, client deployment, diversity, personal data, facilities, remote work support, business continuity, caregivers, volunteering, assets, communication norms, first 90 days, mandatory training), each iteration measured.
- **Tooling fixes found here:**
  1. `registry()` re-read every YAML file on each call, and a check took more than 5 minutes. It's now cached, and a check takes 4 s.
  2. `scripts/renumber_tables.py` renumbers tables in order of appearance after sections are inserted.
  3. The defined-term checker now matches whole words (it had flagged "upgraded" for "Grade") and ignores statutory wording inside `{stat:}` markers.
  4. Contents-page rows have no cell padding, so up to about 45 entries fit on one page. The Leave Policy was rebuilt and still passes.

**D-023 (2026-09-28): POSH Policy (NTL/HR/POL/003) is complete: 12 pages against a target of 14 ±2.**
- 15 sections, 69 clauses, 2 numbered tables and 4 annexures (complaint form, inquiry timeline, FAQs, support resources), plus 2 circulars (HR/CIR/2025/05 IC reconstitution and complaints through the NPP module; HR/CIR/2026/04 procedure extended to all genders as Company policy). About 4,700 words. 20 statutory claims were added (POSH Act and Rules sections, and the BNS); all are UNVERIFIED.
- Traps: T13 (type 1: gender-neutral circular vs Clause 2.2), T14 (type 4: "Workplace" includes late-night messages on personal devices).
- **Renderer bug found:** when a page filled exactly, the zero-size page anchor spilled onto a fresh page, and the next page break then left a completely blank page. Anchors are now recorded in `handle_flowable` without being laid out. Docs 001 to 003 were rebuilt and all pass. POSH went from 13 pages (one blank) to 12.
- **Checker refinements:**
  - A document may list `lowercase_ok` words that are ordinary English (for POSH: "an act of", "calendar days", "an employee of a client"). These are reviewed rather than rewritten into unnatural text.
  - Capitalising "Sexual Harassment" broke trap T13's quote. The trap check caught it, and the quote was updated.
- Running page total: 51 against 56 targeted for docs 001 to 003. The remaining documents aim slightly above target so the total stays near 150.

**D-024 (2026-09-28): Code of Conduct and Ethics (NTL/HR/POL/004) is complete: 16 pages against a target of 18 ±2.**
- 22 sections, 4 numbered tables and 4 annexures (declaration form, gift register, 10 ethical scenarios with a buried carve-out at C.2 for gifts at one's own wedding, and a decision checklist), plus 2 circulars (HR/CIR/2025/08 Gift limit Rs. 5,000 → 2,000 and gift cards banned; HR/CIR/2026/03 approved teaching and open-source work). About 7,500 words. 8 statutory claims were added (Prevention of Corruption Act, Companies Act ss. 177 and 182, SEBI PIT Regulations, Competition Act, contract labour); all are UNVERIFIED.
- **Plants conflict C03** (Clause 12.4: harassment grievances within 30 days, against the POSH Policy's statutory three months).
- Traps: T15 (type 1: gift cards), T16 (type 2: C03), T17 (type 3: Designated Persons and pre-clearance by grade and function), T18 (type 4: "Relative" includes parents-in-law, unlike the Leave Policy's "Immediate Family").
- The first draft was 13 pages. Real sections were added (AML and sanctions, human rights and supply chain, health, safety and environment, conduct away from the office, virtual meetings and recording, personal data).
- **Page-total policy:** the user asked to *cap* the total at about 150 pages to preserve usage. Documents are kept within their own ±2 range, and we don't overshoot to reach exactly 150. Running total: 67 pages against 74 targeted.

**D-025 (2026-09-28): Compensation and Benefits Policy (NTL/HR/POL/005) is complete: 18 pages against a target of 20 ±2.**
- 23 sections, 12 tables and 6 annexures (CTC illustration, gratuity illustrations, variable pay FAQs, statutory benefits summary, claim checklist, tax treatment of components), plus 3 circulars (HR/CIR/2025/03 employer NPS extended to L3 and L4; 2025/06 group medical L1 to L3 Rs. 3 → 4 lakh; 2026/05 LTA leave condition 5 → 3 Working Days). About 7,500 words, and 36 statutory claims (tax, PF, ESI, gratuity, bonus, professional tax); all are UNVERIFIED.
- **Arithmetic was checked before writing:**
  - CTC illustration: L3, Basic Rs. 40,000 a month → fixed pay Rs. 9,60,000 + PF 57,600 + gratuity 23,088 + variable pay 76,800 = Rs. 11,17,488.
  - Gratuity: Rs. 60,000 × 15/26 × 8 = Rs. 2,76,923, and Rs. 50,000 × 15/26 × 3 = Rs. 86,538.
  - Variable pay: Rs. 2,40,000 × 0.9 × 1.2 = Rs. 2,59,200.
  - ESOP: 1,000 × Rs. 300 = Rs. 3,00,000.
- **Variable pay basis changed** from "% of CTC" to "% of Annual Fixed Pay". With CTC as the base, the illustration became circular, because CTC includes variable pay. The Handbook summary (Clause 7.4) and `shared_facts` were updated to match, so no unplanned conflict was created. The Handbook was rebuilt and still passes.
- Traps: T19 (type 1: medical sum insured circular), T20 (type 4: HRA "Metro City" = Delhi, Mumbai, Kolkata, Chennai; Bengaluru is not), T21 (type 3: no variable pay after resigning before the payout date), T22 (type 3, location: no professional tax in Noida/UP).
- **Tooling bug found:** `renumber_tables.py` didn't update table names inside a circular's `amends:` list, so circular 2025/06 briefly pointed at the wrong table. The checker couldn't catch it, because that table number existed. The script now also rewrites `amends:` lists, and the circular was corrected.
- **Word estimates were consistently about 40% too high.** A full page holds about 500 words. From now on, the first draft is sized by measured words per page. Running total: 85 pages against 94 targeted.

**D-026 (2026-09-28): Attendance, Hybrid Work and Overtime Policy (NTL/HR/POL/006) is complete: 11 pages against a target of 12 ±2.**
- 13 sections, 2 numbered tables and 4 annexures (hybrid work form, night shift consent form, FAQs, location quick reference), plus 2 circulars (HR/CIR/2025/10 anchor office days Tue to Thu for L1 to L6; HR/CIR/2026/06 night shift allowance Rs. 500 → 650). About 3,800 words. 7 statutory claims (Shops and Establishments hours, rest, overtime, women's night work, registers; nursing breaks); all are UNVERIFIED.
- Traps: T23 (type 1: anchor days), T24 (type 6: body pays overtime at 1.5×, but Clause 1.3 states the State law requires 2× and prevails), T25 (type 3: no shift allowance for L6 to L8). **Trap count is now 25, all verified, covering all six types, which meets the brief's minimum.**
- Overtime arithmetic was checked: Rs. 6,24,000 / 12 / 26 / 8 = Rs. 250 an hour; × 1.5 × 6 = Rs. 2,250, and at the statutory 2× it is Rs. 3,000.
- "Standard working day" was reworded to "standard workday" so it isn't confused with the defined term "Working Day" (Monday to Friday). Running total: 96 pages against 106 targeted.

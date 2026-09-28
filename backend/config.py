"""Single configuration file for the Nia backend.

Every model name, path and threshold lives here, so switching a provider or tuning a value is a
one-line change. Secrets are NOT stored here: they are read from environment variables (.env).
Later phases add their settings (retrieval, providers, limits) to this same file.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = ROOT / "documents"
MANIFEST_DIR = DOCUMENTS_DIR / "manifest"   # written by the PDF renderer; used only to CHECK ingestion
INDEX_DIR = ROOT / "backend" / "index"
CACHE_DIR = ROOT / ".cache"

# Keep every model download inside ~/hrbot (shared PC, D-002 / D-016).
os.environ.setdefault("HF_HOME", str(CACHE_DIR / "huggingface"))

# ---- Embeddings (D-016): the SAME model embeds the chunks and the queries ----
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_CACHE_DIR = CACHE_DIR / "fastembed"
EMBED_DIM = 384
EMBED_MAX_TOKENS = 512          # the model truncates anything longer
EMBED_BATCH_SIZE = 32

# ---- Chunking (Phase 3) ----
CHUNK_MIN_TOKENS = 150          # shorter neighbouring clauses under one parent are merged up to this
CHUNK_MAX_TOKENS = 450          # longer clauses are split on sentence boundaries
CHUNK_SPLIT_TARGET = 350        # size of each piece when a long clause or table is split
CHUNK_OVERLAP_SENTENCES = 1     # sentences repeated at the start of the next piece
CHUNK_WARN_TOKENS = 600         # reported by the statistics as "too large"

# ---- Retrieval (Phase 4) ----
BM25_TOP_K = 30                 # keyword candidates
DENSE_TOP_K = 30                # semantic candidates
RRF_K = 60                      # Reciprocal Rank Fusion constant (standard value)
RERANK_THREADS = 2              # like a free Hugging Face Space
EMBED_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge query instruction
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"   # small ONNX cross-encoder, via fastembed
RERANK_CANDIDATES = 15          # fused candidates scored by the reranker (0.6 s on 2 CPU threads)
FINAL_TOP_K = 8                 # chunks given to the answer model (the brief: 6 to 8)
MAIN_TOP_K = 6                  # best-ranked chunks kept before amending circulars are added
BOOST_RRF = 0.15                # fused-score multiplier per matched grade/location/leave type/document
CONFIDENCE_THRESHOLD = 0.0015   # reranker probability of the best chunk; below it: "not found, offer a ticket".
                                # Set on the DEV set as 1/10 of the lowest answerable score (D-035).

# ---- Chat models (Phase 5). Keys come ONLY from environment variables (.env / Space secrets). ----
PROVIDER_ORDER = ["ollama", "gemini"]        # first that answers wins (D-014)
OLLAMA_URL = "https://ollama.com/api/chat"
OLLAMA_MODEL = "gpt-oss:120b"                 # response may include `thinking`: never shown or stored
OLLAMA_THINK = "low"                          # gpt-oss reasoning effort: less latency and quota
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Tried in order; a 503 ("busy") or 404 ("retired") moves to the next. Availability measured
# 2026-09-28 (D-036): 3.1-flash-lite and 3.8-flash were 503 (busy), the preview and Gemma answered.
GEMINI_MODELS = ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview", "gemma-4-26b-a4b-it", "gemini-3.8-flash"]
TEMPERATURE = 0.1
TIMEOUT_CONNECT = 10.0                        # seconds (D-017)
TIMEOUT_READ = 30.0
RETRIES = 1                                   # per provider, on timeouts and 5xx (not on 429)
CIRCUIT_FAILURES = 3                          # consecutive failures before a provider is skipped...
CIRCUIT_COOLDOWN = 60                         # ...for this many seconds

# ---- Chat behaviour and limits ----
MAX_MESSAGE_CHARS = 800
MAX_TURNS = 20                                # user messages per session
HISTORY_TURNS = 6                             # recent messages given to the model
RATE_LIMIT_PER_MINUTE = 20                    # /chat requests per IP address (a campus shares one IP)
CACHE_ENABLED = True

# ---- Data and storage ----
EMPLOYEES_CSV = ROOT / "data" / "employees.csv"   # DEMO data (fictional)
RUNTIME_DIR = Path(os.environ.get("HRBOT_RUNTIME_DIR", ROOT / "data" / "runtime"))  # SQLite; git-ignored
DB_PATH = RUNTIME_DIR / "hrbot.sqlite"
TICKET_PREFIX = "NXR-HR"
TICKET_CATEGORIES = ["Leave", "Payroll", "Benefits", "POSH/Grievance", "Policy Clarification", "IT Access", "Other"]
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

# ---- Fictional contacts (content/_company.yaml) and one real public helpline ----
CONTACTS = {
    "hr_helpdesk": "HR Helpdesk: hrhelpdesk@nexora.example, 1800-000-0000 (extension 4), Mon-Fri 9:00-18:00 IST",
    "internal_committee": "Internal Committee (POSH): ic@nexora.example",
    "ethics": "Ethics Office: ethics@nexora.example, hotline 1800-000-0000 (extension 7)",
    "eap": "Employee Assistance Programme (EAP): 1800-000-0000 (extension 9), 24x7, confidential",
    "hrbp": "your HR Business Partner (shown on your NPP profile)",
}
# Real Government of India services. UNVERIFIED: check the numbers before the demo (STATUTORY_CLAIMS.md).
CRISIS_LINES = "Tele-MANAS mental health helpline 14416 (India, 24x7); emergency 112"

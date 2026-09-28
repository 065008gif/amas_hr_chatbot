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

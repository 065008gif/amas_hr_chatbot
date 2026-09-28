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

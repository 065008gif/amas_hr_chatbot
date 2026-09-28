"""Shared by ingestion (writes the index) and retrieval (loads it).

The keyword tokeniser lives here so that the BM25 index and the queries are always tokenised the
same way.
"""
import json
import re
import time

import numpy as np
from rank_bm25 import BM25Okapi

from backend import config

CHUNKS_FILE = config.INDEX_DIR / "chunks.json"
BM25_FILE = config.INDEX_DIR / "bm25_tokens.json"
VECTORS_FILE = config.INDEX_DIR / "vectors.npy"
META_FILE = config.INDEX_DIR / "index_meta.json"

# Words too common to help keyword search. Kept short on purpose: words such as "not", "no",
# "before" and "after" change the meaning of policy text, so they stay searchable.
STOPWORDS = frozenset(
    "a an the of to in on for and or by with as at from is are be been was were this that these "
    "those it its which who whom any such shall may will under per".split()
)
# Words and grade codes (l5), and numbers that keep their separators (6.4.1, 5,000, 2025/07).
TOKEN_RE = re.compile(r"[a-z]+\d*|\d+(?:[.,/]\d+)*")


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class Index:
    """Chunks, a BM25 index and unit-length dense vectors, row-aligned."""

    def __init__(self, chunks, bm25, vectors, meta):
        self.chunks = chunks
        self.bm25 = bm25
        self.vectors = vectors
        self.meta = meta
        self.by_id = {c["chunk_id"]: i for i, c in enumerate(chunks)}


def load_index() -> Index:
    t = time.perf_counter()
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    corpus = json.loads(BM25_FILE.read_text(encoding="utf-8"))
    vectors = np.load(VECTORS_FILE)
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    if not (len(chunks) == len(corpus) == vectors.shape[0]):
        raise RuntimeError("Index files are out of step; re-run: python -m backend.ingest")
    index = Index(chunks, BM25Okapi(corpus), vectors, meta)
    index.load_seconds = time.perf_counter() - t
    return index

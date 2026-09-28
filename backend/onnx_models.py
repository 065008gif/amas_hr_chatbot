"""The two local search models, run directly with onnxruntime + tokenizers (no fastembed at runtime).

This reproduces fastembed's behaviour exactly (checked by tests/check_onnx_models.py), so the
index built with fastembed stays valid:
  - Embedder (BAAI/bge-small-en-v1.5, Qdrant ONNX export): CLS token of last_hidden_state,
    L2-normalised; truncation at the tokenizer's max length.
  - Reranker (cross-encoder ms-marco-MiniLM-L-6-v2): logits[:, 0] for each (query, passage) pair.
Model files ship inside the repository under backend/models/ (bundled into the Vercel function),
so nothing is downloaded or written at run time; the filesystem may be read-only.
"""
import json
import threading
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from backend import config

_lock = threading.Lock()
_cache = {}


def _tokenizer(model_dir: Path) -> Tokenizer:
    cfg = json.loads((model_dir / "tokenizer_config.json").read_text())
    limits = [v for v in (cfg.get("model_max_length"), cfg.get("max_length")) if isinstance(v, int) and 0 < v < 100000]
    tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    tok.enable_truncation(max_length=min(limits) if limits else 512)
    pad = tok.padding or {}
    pad_token = pad.get("pad_token") or cfg.get("pad_token") or "[PAD]"
    pad_id = pad.get("pad_id")
    if pad_id is None:
        pad_id = tok.token_to_id(pad_token) or 0
    tok.enable_padding(direction=pad.get("direction", "right"), pad_id=pad_id, pad_token=pad_token)
    return tok


def _session(path: Path, threads: int) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])


def _inputs(session, encodings):
    names = {i.name for i in session.get_inputs()}
    feed = {"input_ids": np.array([e.ids for e in encodings], dtype=np.int64)}
    if "attention_mask" in names:
        feed["attention_mask"] = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    if "token_type_ids" in names:
        feed["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)
    return feed


class Embedder:
    def __init__(self, model_dir=None, threads=None):
        d = Path(model_dir or config.EMBED_MODEL_DIR)
        self.tok = _tokenizer(d)
        self.sess = _session(d / config.EMBED_MODEL_FILE, threads or config.ONNX_THREADS)

    def embed(self, texts, batch_size=32):
        out = []
        for i in range(0, len(texts), batch_size):
            enc = self.tok.encode_batch(list(texts[i:i + batch_size]))
            hidden = self.sess.run(None, _inputs(self.sess, enc))[0]
            cls = hidden[:, 0]
            out.append(cls / np.linalg.norm(cls, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32)


class Reranker:
    def __init__(self, model_dir=None, model_file=None, threads=None):
        d = Path(model_dir or config.RERANK_MODEL_DIR)
        self.tok = _tokenizer(d)
        self.sess = _session(d / (model_file or config.RERANK_MODEL_FILE), threads or config.ONNX_THREADS)

    def score(self, query, passages, batch_size=16):
        scores = []
        for i in range(0, len(passages), batch_size):
            enc = self.tok.encode_batch([(query, p) for p in passages[i:i + batch_size]])
            scores.extend(self.sess.run(None, _inputs(self.sess, enc))[0][:, 0].tolist())
        return scores


def embedder() -> Embedder:
    with _lock:
        if "embed" not in _cache:
            _cache["embed"] = Embedder()
        return _cache["embed"]


def reranker() -> Reranker:
    with _lock:
        if "rerank" not in _cache:
            _cache["rerank"] = Reranker()
        return _cache["rerank"]

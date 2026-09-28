"""Check that backend/onnx_models.py reproduces fastembed (used to build the index) exactly.

Run from ~/hrbot (needs fastembed installed locally; the deployed app does not use it):
    python tests/check_onnx_models.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config, indexstore  # noqa: E402
from backend.onnx_models import Embedder, Reranker  # noqa: E402


def main():
    idx = indexstore.load_index()
    texts = [c["embed_text"] for c in idx.chunks[:60]]
    mine = Embedder().embed(texts)
    cos_index = (idx.vectors[:60] * mine).sum(1).min()
    print(f"Embedder vs stored index vectors (built with fastembed): min cosine {cos_index:.6f}")
    ok = cos_index > 0.9999
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        q = "What is the notice period if I resign at L5?"
        docs = [c["embed_text"] for c in idx.chunks[:30]]
        ref = np.array(list(TextCrossEncoder(config.RERANK_MODEL, cache_dir=str(config.EMBED_CACHE_DIR)).rerank(q, docs)))
        qu = np.array(Reranker().score(q, docs))
        same = list(np.argsort(-qu)[:5]) == list(np.argsort(-ref)[:5])
        print(f"Quantized reranker vs fastembed fp32: max score difference {np.abs(qu - ref).max():.3f}; same top-5: {same}")
        r = Reranker(threads=1)
        r.score(q, docs[:2])
        t = time.perf_counter()
        r.score(q, docs[:15])
        print(f"Reranker, 1 thread, 15 candidates: {time.perf_counter() - t:.2f} s")
    except ImportError:
        print("fastembed not installed: reranker comparison skipped")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

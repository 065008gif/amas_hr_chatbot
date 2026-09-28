"""Phase 4: hybrid retrieval over the policy index.

    from backend.retrieve import Retriever
    r = Retriever()
    result = r.search("What is the notice period at L5?", profile={"grade": "L5"})

Pipeline (each stage can be switched off, so tests/retrieval_eval.py can measure what it adds):
  1. follow-up rewriting    "what about L7?" -> a standalone question (rule-based here; Phase 5
                            may put a model rewrite in front, with this as the fallback)
  2. hybrid search          BM25 top 30 + dense top 30, merged with Reciprocal Rank Fusion
  3. metadata boosting      grade, location, leave type or document named in the question/profile
  4. rerank                 small cross-encoder over the top 15 fused candidates; its ranking is
                            fused (RRF) with the BM25 and dense rankings rather than replacing
                            them, which ranked best on the dev set (D-035)
  5. circular precedence    a chunk amended by a circular always brings that circular with it
  6. confidence             from the reranker score of the best chunk; below the threshold the
                            answer path is "not found in the documents, offer a ticket"
"""
import math
import re
from dataclasses import dataclass, field

import numpy as np

from backend import config, indexstore

# ---------------------------------------------------------------------------------------------
# Entities in a question
# ---------------------------------------------------------------------------------------------
# Question words are common in FAQ chunks ("How many...?", "Can I...?") and swamp BM25 (D-033),
# so they are dropped from the keyword query only. The dense query keeps the full question.
QUESTION_WORDS = frozenset(
    "how many much what when where which why who whom whose do does did can could would should "
    "i me my mine am we our us you your get got please tell know want need about there if".split()
)
GRADE_Q_RE = re.compile(r"\bL\s?([1-8])\b", re.I)
COMPANY_CITIES = {
    "Bengaluru": r"bengaluru|bangalore|karnataka",
    "Pune": r"pune|maharashtra",
    "Hyderabad": r"hyderabad|telangana",
    "Chennai": r"chennai|tamil nadu",
    "Noida": r"noida|uttar pradesh|ncr",
}
OTHER_CITIES = r"mumbai|delhi|new delhi|kolkata|gurugram|gurgaon|ahmedabad|kochi|jaipur|goa"
CITY_RE = re.compile(r"\b(" + "|".join(list(COMPANY_CITIES.values()) + [OTHER_CITIES]) + r")\b", re.I)
LEAVE_TYPES = {
    "earned leave": r"earned leave|\bel\b|privilege leave|annual leave",
    "casual leave": r"casual leave|\bcl\b",
    "sick leave": r"sick leave|\bsl\b|medical leave",
    "maternity leave": r"maternity",
    "paternity leave": r"paternity",
    "adoption leave": r"adoption",
    "bereavement leave": r"bereavement",
    "marriage leave": r"marriage leave",
    "sabbatical": r"sabbatical",
    "compensatory off": r"comp(ensatory)?[ -]off",
    "leave without pay": r"leave without pay|\blwp\b|unpaid leave",
}
LEAVE_RES = {k: re.compile(v, re.I) for k, v in LEAVE_TYPES.items()}
DOC_ALIASES = {
    "001": r"leave policy",
    "002": r"(employee )?handbook",
    "003": r"posh( policy)?|sexual harassment policy",
    "004": r"code of conduct",
    "005": r"compensation( and benefits)?( policy)?",
    "006": r"attendance( policy)?|hybrid work policy|overtime policy",
    "007": r"travel( and expense)?( reimbursement)? policy|expense policy",
    "008": r"separation( and exit)?( policy)?|exit policy",
    "009": r"it policy|information security policy|acceptable use policy",
}
DOC_RES = {k: re.compile(r"\b(" + v + r")\b", re.I) for k, v in DOC_ALIASES.items()}


def city_name(text: str) -> str:
    for city, rx in COMPANY_CITIES.items():
        if re.fullmatch(rx, text, re.I):
            return city
    return text.title()


def extract_entities(text: str) -> dict:
    return {
        "grades": sorted({f"L{g}" for g in GRADE_Q_RE.findall(text)}),
        "locations": sorted({city_name(m) for m in CITY_RE.findall(text)}),
        "leave_types": sorted(k for k, rx in LEAVE_RES.items() if rx.search(text)),
        "documents": sorted(k for k, rx in DOC_RES.items() if rx.search(text)),
    }


# ---------------------------------------------------------------------------------------------
# 1. Follow-up rewriting (deterministic)
# ---------------------------------------------------------------------------------------------
FOLLOWUP_START_RE = re.compile(r"^\s*(and|what about|how about|what if|same for|also|and for|and in|and at|for)\b", re.I)


def _content_words(text):
    return [t for t in indexstore.tokenize(text) if t not in QUESTION_WORDS and not re.fullmatch(r"l[1-8]", t)]


def rewrite_followup(question: str, history: list[str] | None) -> str:
    """Turn an elliptical follow-up into a standalone question, using the previous question.

    `history` holds earlier user questions (already standalone), oldest first. A question is
    treated as a follow-up when it starts like one ("what about...", "and in...") or has at most
    two content words. Grades, cities and leave types it names replace those in the previous
    question; anything else is appended to it. A self-contained question is returned unchanged.
    """
    q = question.strip()
    if not history:
        return q
    starts_like = bool(FOLLOWUP_START_RE.match(q))
    if not starts_like and len(_content_words(q)) > 2:
        return q
    base = history[-1].strip()
    new = extract_entities(q)
    replaced = False
    rewritten = base
    if new["grades"] and GRADE_Q_RE.search(base):
        rewritten = GRADE_Q_RE.sub(new["grades"][0], rewritten)
        replaced = True
    if new["locations"] and CITY_RE.search(base):
        rewritten = CITY_RE.sub(new["locations"][0], rewritten)
        replaced = True
    if new["leave_types"]:
        for lt, rx in LEAVE_RES.items():
            if rx.search(base) and lt not in new["leave_types"]:
                rewritten = rx.sub(new["leave_types"][0], rewritten)
                replaced = True
    leftover = _content_words(FOLLOWUP_START_RE.sub("", q))
    leftover = [w for w in leftover
                if not re.search(re.escape(w), " ".join(new["locations"] + new["leave_types"]), re.I)]
    if replaced and not leftover:
        return rewritten
    tail = FOLLOWUP_START_RE.sub("", q).strip(" ?.")
    return f"{rewritten.rstrip(' ?.')}; {tail}?" if tail else rewritten


# ---------------------------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------------------------
@dataclass
class Hit:
    chunk: dict
    score: float                    # final ranking score (reranker score + boosts, or fused score)
    rank: int = 0
    role: str = "retrieved"         # retrieved | amending circular
    amends_hit: str | None = None   # for an amending circular: the chunk id it was added for
    signals: dict = field(default_factory=dict)


@dataclass
class Result:
    question: str
    query: str                      # standalone query actually searched
    entities: dict
    hits: list
    confidence: float               # 0..1
    confident: bool                 # False -> "not found in the documents, offer a ticket"


class Retriever:
    def __init__(self, index=None, use_bm25=True, use_dense=True, use_boost=True, use_rerank=True,
                 use_circulars=True, query_prefix=config.EMBED_QUERY_PREFIX):
        self.index = index or indexstore.load_index()
        self.use_bm25, self.use_dense, self.use_boost = use_bm25, use_dense, use_boost
        self.use_rerank, self.use_circulars = use_rerank, use_circulars
        self.query_prefix = query_prefix
        self._embedder = None
        self._reranker = None
        self.circular_ids = {(c["doc_id"], c["circular_no"]): i for i, c in enumerate(self.index.chunks)
                             if c.get("circular_no")}

    # -- models are loaded lazily, once per process (backend/onnx_models.py) --
    @property
    def embedder(self):
        if self._embedder is None:
            from backend import onnx_models
            self._embedder = onnx_models.embedder()
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from backend import onnx_models
            self._reranker = onnx_models.reranker()
        return self._reranker

    # -- stages --
    def _bm25_ranking(self, query):
        tokens = [t for t in indexstore.tokenize(query) if t not in QUESTION_WORDS]
        if not tokens:
            return []
        scores = self.index.bm25.get_scores(tokens)
        order = np.argsort(-scores)[:config.BM25_TOP_K]
        return [int(i) for i in order if scores[i] > 0]

    def _dense_ranking(self, query):
        qv = self.embedder.embed([self.query_prefix + query])[0]
        sims = self.index.vectors @ qv
        order = np.argsort(-sims)[:config.DENSE_TOP_K]
        return [int(i) for i in order], sims

    def _matches(self, chunk, ents):
        """Count of question entities this chunk matches (grade, location, leave type, document)."""
        m = 0
        if ents["grades"] and set(ents["grades"]) & set(chunk["grades"]):
            m += 1
        if ents["locations"] and set(ents["locations"]) & set(chunk["locations"]):
            m += 1
        if ents["leave_types"] and any(LEAVE_RES[lt].search(chunk["text"]) for lt in ents["leave_types"]):
            m += 1
        if ents["documents"] and chunk["doc_id"] in ents["documents"]:
            m += 1
        return m

    def search(self, question, history=None, profile=None, k=config.FINAL_TOP_K) -> Result:
        query = rewrite_followup(question, history)
        ents = extract_entities(query)
        # The session profile fills in grade/location only when the question itself names none.
        for key, pkey in (("grades", "grade"), ("locations", "location")):
            if not ents[key] and profile and profile.get(pkey):
                ents[key] = [profile[pkey]]

        # 2. hybrid search + Reciprocal Rank Fusion
        fused, signals = {}, {}
        rrf = lambda r: 1 / (config.RRF_K + r + 1)  # noqa: E731
        if self.use_bm25:
            for r, i in enumerate(self._bm25_ranking(query)):
                fused[i] = fused.get(i, 0) + rrf(r)
                signals.setdefault(i, {})["bm25_rank"] = r + 1
        sims = None
        if self.use_dense:
            dense, sims = self._dense_ranking(query)
            for r, i in enumerate(dense):
                fused[i] = fused.get(i, 0) + rrf(r)
                signals.setdefault(i, {})["dense_rank"] = r + 1

        # 3. metadata boosting
        matches = {i: self._matches(self.index.chunks[i], ents) if self.use_boost else 0 for i in fused}
        boosted = {i: s * (1 + config.BOOST_RRF * matches[i]) for i, s in fused.items()}
        candidates = sorted(boosted, key=lambda i: -boosted[i])[:config.RERANK_CANDIDATES]

        # 4. rerank the top candidates and fuse the reranker's ranking in as a third ranking
        raw = {}
        if self.use_rerank and candidates:
            top = candidates[:config.RERANK_CANDIDATES]
            ce = self.reranker.score(query, [self.index.chunks[i]["embed_text"] for i in top])
            raw = dict(zip(top, (float(s) for s in ce)))
            for r, i in enumerate(sorted(top, key=lambda i: -raw[i])):
                fused[i] += rrf(r)
                signals[i]["rerank_rank"] = r + 1
        final = {i: fused[i] * (1 + config.BOOST_RRF * matches[i]) for i in candidates}
        ranked = sorted(candidates, key=lambda i: -final[i])

        # 5. circular precedence: keep the best MAIN_TOP_K, add every circular amending them,
        #    then fill up to k from the ranking.
        hits, taken = [], set()

        def add(i, role="retrieved", amends_hit=None):
            if i in taken:
                return
            taken.add(i)
            sig = dict(signals.get(i, {}), matches=matches.get(i, 0))
            if i in raw:
                sig["rerank_score"] = round(raw[i], 3)
            hits.append(Hit(self.index.chunks[i], final.get(i, 0.0), role=role, amends_hit=amends_hit,
                            signals=sig))

        for i in ranked[:config.MAIN_TOP_K]:
            add(i)
            if self.use_circulars:
                for no in self.index.chunks[i].get("amended_by", []):
                    j = self.circular_ids.get((self.index.chunks[i]["doc_id"], no))
                    if j is not None and j not in taken:
                        add(j, role="amending circular", amends_hit=self.index.chunks[i]["chunk_id"])
        for i in ranked[config.MAIN_TOP_K:]:
            if len(hits) >= k:
                break
            add(i)
        hits = hits[:max(k, sum(h.role == "amending circular" for h in hits) + config.MAIN_TOP_K)]
        for r, h in enumerate(hits, start=1):
            h.rank = r

        # 6. confidence: reranker probability that the best candidate answers the question
        if raw:
            confidence = 1 / (1 + math.exp(-max(raw.values())))
        elif sims is not None and candidates:
            confidence = float(max(sims[i] for i in candidates))
        else:
            confidence = 0.0
        return Result(question, query, ents, hits, round(confidence, 4),
                      confidence >= config.CONFIDENCE_THRESHOLD)


if __name__ == "__main__":
    import sys
    r = Retriever()
    q = " ".join(sys.argv[1:]) or "What is the notice period if I resign at L5?"
    res = r.search(q)
    print(f"query: {res.query}\nentities: {res.entities}\nconfidence: {res.confidence} "
          f"({'answer' if res.confident else 'not found -> offer ticket'})")
    for h in res.hits:
        c = h.chunk
        print(f"{h.rank}. {c['chunk_id']:<40} p.{c['page_start']:<3} {h.role:<18} score {h.score:.3f} {h.signals}")

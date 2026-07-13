"""Vector store for the RAG copilot.

Two interchangeable backends behind one search() API:
  - "dense": normalized embedding matrix loaded from rag_index.npz/.json,
             queries embedded via the OpenAI-compatible proxy. Only used when
             an embeddings key is actually configured.
  - "keyword": deterministic scikit-learn TF-IDF retriever over the same
             corpus, built in-memory — no key, no persistence, always works.
             Queries are expanded with a small advisor-intent lexicon so
             natural-language questions ("who's at risk of leaving?") still
             match the underlying records ("attrition", "flagged", "declining").

load_or_build() picks dense only when embeddings are available; otherwise it
falls back to the keyword retriever, so the Book Assistant works with no key.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from itertools import zip_longest
from pathlib import Path

import numpy as np

from backend import llm
from backend.config import RAG_EMBED_BATCH
from backend.rag.corpus import Document

# ---------------------------------------------------------------------------
# Lightweight TF-IDF (numpy-only, no scikit-learn)
# ---------------------------------------------------------------------------
# The keyword retriever previously used sklearn's TfidfVectorizer. To keep the
# serverless bundle small (sklearn pulls in scipy, ~170MB), we reimplement the
# same behaviour here: unigrams + bigrams, english stop-word removal, sublinear
# TF, smoothed IDF, and L2-normalised cosine similarity.

_TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")

# A compact English stop-word list (subset of sklearn's ENGLISH_STOP_WORDS),
# enough to keep lexical search focused on content terms.
_STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because been
before being below between both but by can can't cannot could couldn't did didn't do does
doesn't doing don't down during each few for from further had hadn't has hasn't have haven't
having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll
i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor
not of off on once only or other ought our ours ourselves out over own same shan't she she'd
she'll she's should shouldn't so some such than that that's the their theirs them themselves
then there there's these they they'd they'll they're they've this those through to too under
until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's will with won't would wouldn't you you'd you'll
you're you've your yours yourself yourselves
""".split())


def _analyze(text: str) -> list[str]:
    """Tokenise into content unigrams + adjacent bigrams (post stop-word removal)."""
    unigrams = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]
    terms = list(unigrams)
    terms.extend(f"{a} {b}" for a, b in zip(unigrams, unigrams[1:]))
    return terms

# Map common advisor vocabulary to the words that actually appear in the
# corpus (rationales, call notes, market signals), so lexical search matches
# intent rather than requiring an exact keyword. Keyed by a single token.
_QUERY_EXPANSIONS: dict[str, str] = {
    "risk": "attrition urgent flagged declining",
    "risks": "attrition urgent flagged declining",
    "leaving": "attrition urgent churn not contacted declining",
    "leave": "attrition urgent churn not contacted",
    "attrition": "urgent flagged declining not contacted",
    "churn": "attrition urgent flagged",
    "lose": "attrition urgent churn",
    "losing": "attrition urgent churn",
    "disengaged": "declining not contacted attrition",
    "upsell": "opportunity growth ready property inheritance",
    "opportunity": "upsell growth ready",
    "opportunities": "upsell growth ready",
    "grow": "growth upsell opportunity",
    "growth": "upsell opportunity ready",
    "expand": "upsell opportunity growth",
    "competitor": "competitor other advisors considering rates",
    "competitors": "competitor other advisors considering rates",
    "moving": "considering other advisors withdraw redemption",
    "money": "withdraw redemption assets portfolio",
    "market": "market sentiment sector exposure",
    "markets": "market sentiment sector exposure",
    "stocks": "equities sector market sentiment",
    "sector": "market sentiment exposure",
    "life": "life event property inheritance retirement education business",
    "event": "life event property inheritance retirement education",
    "events": "life event property inheritance retirement education",
    "discuss": "call note discussed",
    "discussed": "call note discussed",
    "talk": "call note discussed",
    "talked": "call note discussed",
    "contact": "contact note call",
    "recent": "note call",
    "flagged": "urgent opportunity rationale",
    "why": "rationale flagged",
}


def _expand_query(query: str) -> str:
    extra: list[str] = []
    for tok in query.lower().split():
        key = tok.strip("?.,!'\"():;")
        if key in _QUERY_EXPANSIONS:
            extra.append(_QUERY_EXPANSIONS[key])
    return f"{query} {' '.join(extra)}".strip()


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class VectorStore:
    def __init__(self, docs: list[Document], mode: str) -> None:
        self.docs = docs
        self.mode = mode
        self._dense: np.ndarray | None = None
        # Keyword (TF-IDF) index state.
        self._idf: dict[str, float] = {}
        self._doc_vecs: list[dict[str, float]] = []
        self._kw_fallback: "VectorStore | None" = None

    # -- construction ------------------------------------------------------

    @classmethod
    def build_dense(cls, docs: list[Document]) -> "VectorStore":
        vectors: list[list[float]] = []
        texts = [d["text"] for d in docs]
        for start in range(0, len(texts), RAG_EMBED_BATCH):
            batch = texts[start:start + RAG_EMBED_BATCH]
            vectors.extend(llm.embed(batch))
            print(f"  embedded {min(start + RAG_EMBED_BATCH, len(texts))}/{len(texts)} docs")
        store = cls(docs, mode="dense")
        store._dense = _normalize(np.array(vectors, dtype=np.float32))
        return store

    @classmethod
    def from_keyword(cls, docs: list[Document]) -> "VectorStore":
        """Deterministic TF-IDF retriever (numpy-only) — no API key needed."""
        store = cls(docs, mode="keyword")
        tokenized = [_analyze(d["text"]) for d in docs]

        # Document frequency + smoothed IDF (matches sklearn's smooth_idf).
        n_docs = len(tokenized)
        df: Counter[str] = Counter()
        for terms in tokenized:
            df.update(set(terms))
        store._idf = {
            term: math.log((1 + n_docs) / (1 + freq)) + 1.0
            for term, freq in df.items()
        }

        # Per-doc L2-normalised sublinear TF-IDF vectors (sparse dicts).
        store._doc_vecs = [store._vectorize(terms) for terms in tokenized]
        return store

    def _vectorize(self, terms: list[str]) -> dict[str, float]:
        """Build an L2-normalised sublinear TF-IDF vector from token terms.

        Unknown terms (not seen at fit time) are dropped, mirroring sklearn's
        transform() behaviour."""
        counts = Counter(terms)
        vec: dict[str, float] = {}
        for term, count in counts.items():
            idf = self._idf.get(term)
            if idf is None:
                continue
            vec[term] = (1.0 + math.log(count)) * idf
        norm = math.sqrt(sum(w * w for w in vec.values()))
        if norm > 0:
            for term in vec:
                vec[term] /= norm
        return vec

    # -- persistence -------------------------------------------------------

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path.with_suffix(".npz"), vectors=self._dense)
        path.with_suffix(".json").write_text(
            json.dumps({"mode": self.mode, "docs": self.docs}, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path) -> "VectorStore | None":
        npz, meta = path.with_suffix(".npz"), path.with_suffix(".json")
        if not (npz.exists() and meta.exists()):
            return None
        payload = json.loads(meta.read_text(encoding="utf-8"))
        store = cls(payload["docs"], mode="dense")
        store._dense = np.load(npz)["vectors"]
        return store

    @classmethod
    def load_or_build(cls, session) -> "VectorStore":
        """Use the persisted dense index only when embeddings are actually
        available; otherwise fall back to the keyword retriever so the copilot
        works with no API key."""
        from backend.config import RAG_INDEX_PATH
        from backend.rag.corpus import build_documents

        if llm.embeddings_available():
            dense = cls.load(RAG_INDEX_PATH)
            if dense is not None and dense.docs:
                return dense
        return cls.from_keyword(build_documents(session))

    # -- search ------------------------------------------------------------

    def _dense_scores(self, query: str) -> np.ndarray | None:
        try:
            vec = np.array(llm.embed([query])[0], dtype=np.float32)
        except Exception:  # noqa: BLE001 — embeddings endpoint unavailable
            return None
        vec = vec / (np.linalg.norm(vec) or 1.0)
        return self._dense @ vec

    def _keyword_fallback(self) -> "VectorStore":
        """Lazily build (and cache) a keyword retriever over the same docs, so
        dense misses can fall back without re-fitting on every query."""
        if self._kw_fallback is None:
            self._kw_fallback = VectorStore.from_keyword(self.docs)
        return self._kw_fallback

    def _keyword_scores(self, query: str) -> np.ndarray:
        q_vec = self._vectorize(_analyze(_expand_query(query)))
        if not q_vec:
            return np.zeros(len(self._doc_vecs), dtype=np.float32)
        # Cosine similarity = dot product of two L2-normalised sparse vectors.
        scores = [
            sum(weight * doc_vec.get(term, 0.0) for term, weight in q_vec.items())
            for doc_vec in self._doc_vecs
        ]
        return np.array(scores, dtype=np.float32)

    def _rank(self, scores: np.ndarray, k: int, client_id: str | None) -> list[tuple[Document, float]]:
        # When scoped to a client, keep that client's docs plus global market context.
        if client_id:
            mask = np.array([
                (d["client_id"] == client_id or d["doc_type"] == "market") for d in self.docs
            ])
            scores = np.where(mask, scores, -1.0)
        top = np.argsort(scores)[::-1][:k]
        return [(self.docs[i], float(scores[i])) for i in top if scores[i] > 1e-6]

    @staticmethod
    def _merge(primary: list, secondary: list, k: int) -> list:
        """Interleave two hit lists, de-duplicated, so both retrievers are
        represented in the context (keeps recall high when one of them misses)."""
        merged, seen = [], set()
        for a, b in zip_longest(primary, secondary):
            for hit in (a, b):
                if hit is None:
                    continue
                doc_id = hit[0]["id"]
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                merged.append(hit)
        return merged[:k]

    def search(self, query: str, k: int, client_id: str | None = None) -> list[tuple[Document, float]]:
        if not self.docs:
            return []

        if self.mode == "dense":
            scores = self._dense_scores(query)
            # Keyword pass always runs alongside dense: it's reliable and keeps
            # relevant records in context even when dense retrieval misses.
            kw_hits = self._keyword_fallback().search(query, k, client_id)
            if scores is None:
                return kw_hits
            dense_hits = self._rank(scores, k, client_id)
            return self._merge(dense_hits, kw_hits, k)

        return self._rank(self._keyword_scores(query), k, client_id)

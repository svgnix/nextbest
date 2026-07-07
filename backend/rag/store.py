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
from itertools import zip_longest
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from backend import llm
from backend.config import RAG_EMBED_BATCH
from backend.rag.corpus import Document

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
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
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
        """Deterministic TF-IDF retriever — no API key needed."""
        store = cls(docs, mode="keyword")
        store._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1,
        )
        corpus = [d["text"] for d in docs] or [""]
        store._matrix = store._vectorizer.fit_transform(corpus)
        return store

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
        q = self._vectorizer.transform([_expand_query(query)])
        return (self._matrix @ q.T).toarray().ravel()

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

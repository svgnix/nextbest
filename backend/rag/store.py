"""Vector store for the RAG copilot.

Two interchangeable backends behind one search() API:
  - "dense": normalized embedding matrix loaded from rag_index.npz/.json,
             queries embedded via the OpenAI-compatible proxy.
  - "hashing": deterministic scikit-learn HashingVectorizer over the same
               corpus, built in-memory — no key, no persistence, always works.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from backend import llm
from backend.config import RAG_EMBED_BATCH
from backend.rag.corpus import Document

_HASH_FEATURES = 2 ** 18


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class VectorStore:
    def __init__(self, docs: list[Document], mode: str) -> None:
        self.docs = docs
        self.mode = mode
        self._dense: np.ndarray | None = None
        self._hasher: HashingVectorizer | None = None
        self._hash_matrix = None

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
    def from_hashing(cls, docs: list[Document]) -> "VectorStore":
        store = cls(docs, mode="hashing")
        store._hasher = HashingVectorizer(
            n_features=_HASH_FEATURES, alternate_sign=False, norm="l2", stop_words="english"
        )
        corpus = [d["text"] for d in docs] or [""]
        store._hash_matrix = store._hasher.transform(corpus)
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
        """Prefer a persisted dense index; else build the hashing fallback."""
        from backend.config import RAG_INDEX_PATH
        from backend.rag.corpus import build_documents

        dense = cls.load(RAG_INDEX_PATH)
        if dense is not None and dense.docs:
            return dense
        return cls.from_hashing(build_documents(session))

    # -- search ------------------------------------------------------------

    def _query_vector(self, query: str) -> np.ndarray:
        if self.mode == "dense":
            vec = np.array(llm.embed([query])[0], dtype=np.float32)
            return vec / (np.linalg.norm(vec) or 1.0)
        return None  # handled inline for hashing

    def search(self, query: str, k: int, client_id: str | None = None) -> list[tuple[Document, float]]:
        if not self.docs:
            return []

        if self.mode == "dense":
            q = self._query_vector(query)
            scores = self._dense @ q
        else:
            q = self._hasher.transform([query])
            scores = (self._hash_matrix @ q.T).toarray().ravel()

        # When scoped to a client, keep that client's docs plus global market context.
        if client_id:
            mask = np.array([
                (d["client_id"] == client_id or d["doc_type"] == "market") for d in self.docs
            ])
            scores = np.where(mask, scores, -1.0)

        top = np.argsort(scores)[::-1][:k]
        return [(self.docs[i], float(scores[i])) for i in top if scores[i] > 0]

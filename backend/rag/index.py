"""Build the dense RAG index: python -m backend.rag.index

Reads the DB, embeds every document via the OpenAI-compatible proxy, and
writes rag_index.npz + rag_index.json. If embeddings aren't available it
no-ops with a clear message — the API then uses the hashing fallback.
"""

from __future__ import annotations

from backend import llm
from backend.config import RAG_INDEX_PATH
from backend.db import SessionLocal
from backend.rag.corpus import build_documents
from backend.rag.store import VectorStore


def main() -> None:
    session = SessionLocal()
    try:
        docs = build_documents(session)
    finally:
        session.close()

    print(f"Built {len(docs)} documents from the book.")
    if not docs:
        print("No documents to index. Run backend.seed and backend.run_pipeline first.")
        return

    if not llm.embeddings_available():
        print(
            "Embeddings unavailable (no OpenAI-compatible key). Skipping dense index.\n"
            "The API will serve the copilot via the deterministic hashing fallback."
        )
        return

    print("Embedding documents via the proxy...")
    store = VectorStore.build_dense(docs)
    store.save(RAG_INDEX_PATH)
    print(f"Wrote dense index to {RAG_INDEX_PATH}.npz / .json")


if __name__ == "__main__":
    main()

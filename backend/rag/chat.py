"""Grounded question answering over the book: retrieve -> synthesise -> cite."""

from __future__ import annotations

from backend import llm
from backend.config import RAG_TOP_K
from backend.prompts import RAG_SYSTEM
from backend.rag.corpus import Document
from backend.rag.store import VectorStore

NOT_FOUND = "I couldn't find that in your records."


def _tag(doc: Document) -> str:
    who = doc["client_id"] or "MARKET"
    date = doc["date"] or "n/a"
    return f"[{who} · {date}]"


def _snippet(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _citation(doc: Document) -> dict:
    return {
        "client_id": doc["client_id"],
        "name": doc["client_name"],
        "doc_type": doc["doc_type"],
        "date": doc["date"],
        "snippet": _snippet(doc["text"]),
    }


def answer(store: VectorStore, query: str, client_id: str | None = None) -> dict:
    query = (query or "").strip()
    if not query:
        return {"answer": "Ask me anything about your book.", "citations": [], "grounded": False}

    hits = store.search(query, k=RAG_TOP_K, client_id=client_id)
    if not hits:
        return {"answer": NOT_FOUND, "citations": [], "grounded": False}

    blocks = "\n".join(f"{_tag(doc)} {doc['text']}" for doc, _ in hits)
    user = (
        "Answer the advisor's question using ONLY the context blocks below. "
        "Cite the bracket tags inline. If the answer isn't in the context, say you couldn't find it.\n\n"
        f"Context:\n{blocks}\n\n"
        f"Question: {query}"
    )

    resp = llm.chat([{"role": "user", "content": user}], system=RAG_SYSTEM, temperature=0.2)
    text = (resp.get("text") or "").strip() or NOT_FOUND

    # De-duplicate citations while preserving retrieval order.
    citations, seen = [], set()
    for doc, _ in hits:
        key = (doc["client_id"], doc["doc_type"], doc["date"])
        if key in seen:
            continue
        seen.add(key)
        citations.append(_citation(doc))

    grounded = text != NOT_FOUND
    return {"answer": text, "citations": citations if grounded else [], "grounded": grounded}

"""Build the retrieval corpus from the DB.

Every unit of text an advisor might ask about becomes one document with
metadata so answers can cite a specific client + date + source.
"""

from __future__ import annotations

from typing import TypedDict

from sqlalchemy.orm import Session

from backend.db import Client, MarketSignal, ScoredAction


class Document(TypedDict):
    id: int
    client_id: str
    client_name: str
    doc_type: str
    date: str
    text: str


def build_documents(session: Session) -> list[Document]:
    """Emit the full document set from clients, agent output, and market feed."""
    docs: list[Document] = []

    def add(client_id: str, name: str, doc_type: str, date: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        docs.append({
            "id": len(docs),
            "client_id": client_id,
            "client_name": name,
            "doc_type": doc_type,
            "date": date or "",
            "text": text,
        })

    clients = session.query(Client).all()
    actions = {a.client_id: a for a in session.query(ScoredAction).all()}

    for c in clients:
        name = c.name

        for entry in (c.call_log or []):
            add(c.client_id, name, "call_note", entry.get("date", ""),
                f"{name} — call note ({entry.get('date', '')}): {entry.get('note', '')}")

        if c.last_contact_note:
            add(c.client_id, name, "contact_note", "",
                f"{name} — most recent contact note: {c.last_contact_note}")

        for ev in (c.life_events_detail or []):
            add(c.client_id, name, "life_event", ev.get("date", ""),
                f"{name} — life event: {ev.get('type', '').replace('_', ' ')} (around {ev.get('date', '')}).")

        if c.market_exposure:
            add(c.client_id, name, "exposure", "",
                f"{name} — market exposure: {', '.join(m.replace('_', ' ') for m in c.market_exposure)}.")

        a = actions.get(c.client_id)
        if a:
            if a.rationale:
                add(c.client_id, name, "rationale", "",
                    f"{name} — why the agent flagged them ({a.action_type}): {a.rationale}")
            for step in (a.reasoning_trace or []):
                add(c.client_id, name, "trace", "",
                    f"{name} — agent {step.get('agent', '')} finding: {step.get('finding', '')}")

    for m in session.query(MarketSignal).all():
        add("", "Market", "market", m.date,
            f"Market sentiment ({m.date}) — {m.sector.replace('_', ' ')} is {m.sentiment}: {m.signal}")

    return docs

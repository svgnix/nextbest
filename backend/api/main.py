"""NextBest API — FastAPI over the SQLite advisor book.

Run from the repo root:
    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.serializers import (
    SEGMENT_PLAYBOOKS,
    action_to_dict,
    client_detail,
    client_summary,
)
from backend.config import PRIMARY_ADVISOR_ID
from backend.db import (
    Advisor,
    AdvisorAction,
    Client,
    MarketSignal,
    ScoredAction,
    get_session,
    init_db,
)
from backend.schemas import AdvisorActionIn

app = FastAPI(title="NextBest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Advisors
# ---------------------------------------------------------------------------

@app.get("/api/advisors")
def list_advisors(db: Session = Depends(get_session)) -> list[dict]:
    return [
        {"advisor_id": a.advisor_id, "name": a.name, "title": a.title}
        for a in db.query(Advisor).all()
    ]


# ---------------------------------------------------------------------------
# Dispatch — the agent's ranked morning picks (drafted clients)
# ---------------------------------------------------------------------------

@app.get("/api/dispatch")
def dispatch(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> list[dict]:
    rows = (
        db.query(ScoredAction)
        .filter(ScoredAction.advisor_id == advisor_id, ScoredAction.draft_message != "")
        .order_by(ScoredAction.priority_rank)
        .all()
    )
    return [action_to_dict(a) for a in rows]


# ---------------------------------------------------------------------------
# Clients — roster + 360
# ---------------------------------------------------------------------------

@app.get("/api/clients")
def list_clients(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    segment: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_session),
) -> list[dict]:
    query = db.query(Client).filter(Client.advisor_id == advisor_id)
    if segment:
        query = query.filter(Client.segment_label == segment)
    if q:
        query = query.filter(Client.name.ilike(f"%{q}%"))
    rows = query.order_by(Client.attrition_risk.desc().nullslast()).all()
    return [client_summary(c) for c in rows]


@app.get("/api/clients/{client_id}")
def get_client(client_id: str, db: Session = Depends(get_session)) -> dict:
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_detail(c)


# ---------------------------------------------------------------------------
# Segments explorer
# ---------------------------------------------------------------------------

@app.get("/api/segments")
def segments(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> list[dict]:
    rows = db.query(Client).filter(
        Client.advisor_id == advisor_id, Client.segment_label.isnot(None)
    ).all()

    buckets: dict[tuple, list[Client]] = defaultdict(list)
    for c in rows:
        buckets[(c.segment_id, c.segment_label)].append(c)

    out = []
    for (sid, label), members in sorted(buckets.items(), key=lambda kv: kv[0][0]):
        n = len(members)
        out.append({
            "id": sid,
            "label": label,
            "count": n,
            "avg_attrition": round(sum(m.attrition_risk or 0 for m in members) / n, 1),
            "avg_upsell": round(sum(m.upsell_ready or 0 for m in members) / n, 1),
            "total_aum": sum(m.portfolio_value for m in members),
            "playbook": SEGMENT_PLAYBOOKS.get(label, "Tailor engagement to the cluster's behaviour."),
            "member_ids": [m.client_id for m in members[:12]],
        })
    return out


# ---------------------------------------------------------------------------
# Book analytics
# ---------------------------------------------------------------------------

@app.get("/api/book/analytics")
def book_analytics(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> dict:
    clients = db.query(Client).filter(Client.advisor_id == advisor_id).all()
    if not clients:
        raise HTTPException(status_code=404, detail="No clients for advisor")

    scored = [c for c in clients if c.attrition_risk is not None]
    total_aum = sum(c.portfolio_value for c in clients)
    revenue_at_risk = sum(c.portfolio_value for c in scored if (c.attrition_risk or 0) >= 50)
    upsell_pipeline = sum(c.revenue_impact or 0 for c in scored if (c.upsell_ready or 0) >= 50)

    def action_type(c: Client) -> str:
        return c.action.action_type if c.action else "WATCHLIST"

    urgent = sum(1 for c in clients if action_type(c) == "URGENT")
    opportunity = sum(1 for c in clients if action_type(c) == "OPPORTUNITY")
    watchlist = len(clients) - urgent - opportunity

    avg_days = round(sum(c.days_since_last_contact for c in clients) / len(clients), 1)

    seg = segments(advisor_id=advisor_id, db=db)

    return {
        "total_clients": len(clients),
        "total_aum": total_aum,
        "revenue_at_risk": revenue_at_risk,
        "upsell_pipeline": upsell_pipeline,
        "urgent_count": urgent,
        "opportunity_count": opportunity,
        "watchlist_count": watchlist,
        "avg_days_since_contact": avg_days,
        "segment_distribution": seg,
        # A few scored highlights for the dashboard tables.
        "top_at_risk": [
            client_summary(c) for c in sorted(
                [c for c in scored if (c.attrition_risk or 0) >= 50],
                key=lambda c: c.attrition_risk or 0, reverse=True,
            )[:5]
        ],
        "top_opportunities": [
            client_summary(c) for c in sorted(
                [c for c in scored if (c.upsell_ready or 0) >= 50],
                key=lambda c: c.revenue_impact or 0, reverse=True,
            )[:5]
        ],
    }


# ---------------------------------------------------------------------------
# Market sentiment feed
# ---------------------------------------------------------------------------

@app.get("/api/market")
def market(db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(MarketSignal).order_by(MarketSignal.date.desc()).all()
    seen = set()
    out = []
    for m in rows:
        if m.sector in seen:
            continue
        seen.add(m.sector)
        out.append({"date": m.date, "sector": m.sector, "sentiment": m.sentiment, "signal": m.signal})
    return out


# ---------------------------------------------------------------------------
# Campaigns / outreach queue
# ---------------------------------------------------------------------------

@app.get("/api/campaigns")
def campaigns(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> list[dict]:
    rows = (
        db.query(ScoredAction)
        .filter(ScoredAction.advisor_id == advisor_id, ScoredAction.draft_message != "")
        .order_by(ScoredAction.priority_rank)
        .all()
    )
    return [action_to_dict(a) for a in rows]


# ---------------------------------------------------------------------------
# Agent activity log — flattened multi-agent reasoning steps
# ---------------------------------------------------------------------------

@app.get("/api/agent/activity")
def agent_activity(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> list[dict]:
    rows = (
        db.query(ScoredAction)
        .filter(ScoredAction.advisor_id == advisor_id, ScoredAction.draft_message != "")
        .order_by(ScoredAction.priority_rank)
        .all()
    )
    activity = []
    for a in rows:
        for step in (a.reasoning_trace or []):
            activity.append({
                "client_id": a.client_id,
                "client_name": a.name,
                "priority_rank": a.priority_rank,
                "agent": step.get("agent", "orchestrator"),
                "tool": step.get("tool", ""),
                "finding": step.get("finding", ""),
                "ts_ms": step.get("ts_ms", 0),
            })
    activity.sort(key=lambda s: s["ts_ms"])
    return activity


# ---------------------------------------------------------------------------
# Advisor actions — persist accept / skip / edit + feedback
# ---------------------------------------------------------------------------

@app.post("/api/actions/{client_id}")
def record_action(
    client_id: str,
    payload: AdvisorActionIn,
    db: Session = Depends(get_session),
) -> dict:
    action = db.get(ScoredAction, client_id)
    if not action:
        raise HTTPException(status_code=404, detail="No scored action for client")

    status_map = {"accept": "accepted", "skip": "skipped", "edit": "edited"}
    action.action_status = status_map[payload.action]
    if payload.draft_text is not None:
        action.draft_message = payload.draft_text

    db.add(AdvisorAction(
        client_id=client_id,
        action=payload.action,
        draft_text=payload.draft_text,
        feedback=payload.feedback,
    ))
    db.commit()
    db.refresh(action)
    return action_to_dict(action)


@app.get("/api/actions/log")
def action_log(db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(AdvisorAction).order_by(AdvisorAction.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "client_id": r.client_id,
            "action": r.action,
            "draft_text": r.draft_text,
            "feedback": r.feedback,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

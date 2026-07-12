"""NextBest API — FastAPI over the SQLite advisor book.

Run from the repo root:
    uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

import json
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
from backend.config import MARKET_HISTORY_PATH, PRIMARY_ADVISOR_ID, XGB_META_PATH
from backend.db import (
    Advisor,
    AdvisorAction,
    AgentRun,
    Client,
    MarketSignal,
    ScoredAction,
    SessionLocal,
    get_session,
    init_db,
)
from backend.eval import REPORT_PATH, _avg, _pct, compute_report
from backend.rag import chat as rag_chat
from backend.rag.store import VectorStore
from backend.schemas import AdvisorActionIn, ChatRequest

app = FastAPI(title="NextBest API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Loaded once at startup: dense index if present, else the hashing fallback.
_store: VectorStore | None = None


@app.on_event("startup")
def _startup() -> None:
    init_db()
    global _store
    session = SessionLocal()
    try:
        _store = VectorStore.load_or_build(session)
        print(f"RAG copilot ready: {_store.mode} retrieval over {len(_store.docs)} documents.")
    finally:
        session.close()


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
    """Rich per-sector market detail (price history for the live charts) from the
    cached ETF snapshot. Falls back to the DB sentiment feed if the file is
    missing, so the page always renders."""
    if MARKET_HISTORY_PATH.exists():
        try:
            detail = json.loads(MARKET_HISTORY_PATH.read_text(encoding="utf-8"))
            if detail:
                order = {"bearish": 0, "neutral": 1, "bullish": 2}
                detail.sort(key=lambda d: (order.get(d.get("sentiment"), 1), -abs(d.get("change_pct", 0))))
                return detail
        except (json.JSONDecodeError, OSError):
            pass

    rows = db.query(MarketSignal).order_by(MarketSignal.date.desc()).all()
    seen = set()
    out = []
    for m in rows:
        if m.sector in seen:
            continue
        seen.add(m.sector)
        out.append({
            "date": m.date, "sector": m.sector, "label": m.sector.replace("_", " ").title(),
            "sentiment": m.sentiment, "signal": m.signal, "ticker": "", "change_pct": 0.0,
            "last_close": 0.0, "live": False, "history": [],
        })
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
# Observability — aggregate agent-run telemetry
# ---------------------------------------------------------------------------

@app.get("/api/agent/metrics")
def agent_metrics(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> dict:
    runs = db.query(AgentRun).filter(AgentRun.advisor_id == advisor_id).all()
    if not runs:
        return {"runs": 0}

    from collections import Counter

    latencies = [r.total_ms for r in runs if r.total_ms]
    redrafts = [r.redrafts for r in runs]
    tokens = [r.total_tokens for r in runs]
    modes = {r.mode for r in runs}

    # Average time spent in each node across runs.
    node_totals: dict[str, float] = {}
    node_counts: dict[str, int] = {}
    for r in runs:
        for node, ms in (r.node_timings or {}).items():
            node_totals[node] = node_totals.get(node, 0.0) + ms
            node_counts[node] = node_counts.get(node, 0) + 1
    node_avg = [
        {"label": n, "value": round(node_totals[n] / node_counts[n], 1)}
        for n in sorted(node_totals, key=lambda k: node_totals[k] / node_counts[k], reverse=True)
    ]

    framing_dist = Counter(r.framing or "check-in" for r in runs)
    redraft_dist = Counter(str(r.redrafts) for r in runs)
    passed = sum(1 for r in runs if r.draft_passed)

    return {
        "runs": len(runs),
        "mode": "mixed" if len(modes) > 1 else next(iter(modes)),
        "avg_latency_ms": _avg(latencies),
        "p50_latency_ms": _pct(latencies, 0.5),
        "p95_latency_ms": _pct(latencies, 0.95),
        "avg_redrafts": _avg(redrafts),
        "critique_pass_rate": round(passed / len(runs), 3),
        "metric_leaks_caught": sum(1 for r in runs if r.metric_leak_caught),
        "llm_calls_total": sum(r.llm_calls for r in runs),
        "tokens": {
            "total": sum(tokens),
            "prompt": sum(r.prompt_tokens for r in runs),
            "completion": sum(r.completion_tokens for r in runs),
            "avg_per_run": _avg(tokens),
        },
        "node_timings_avg": node_avg,
        "framing_distribution": [{"label": k, "count": v} for k, v in framing_dist.most_common()],
        "redraft_distribution": [
            {"label": f"{k} redraft{'s' if k != '1' else ''}", "count": v}
            for k, v in sorted(redraft_dist.items())
        ],
    }


@app.get("/api/agent/runs")
def agent_runs(
    advisor_id: str = Query(PRIMARY_ADVISOR_ID),
    db: Session = Depends(get_session),
) -> list[dict]:
    rows = (
        db.query(AgentRun)
        .filter(AgentRun.advisor_id == advisor_id)
        .order_by(AgentRun.priority_rank)
        .all()
    )
    return [
        {
            "client_id": r.client_id,
            "name": r.name,
            "priority_rank": r.priority_rank,
            "framing": r.framing,
            "total_ms": round(r.total_ms or 0, 1),
            "llm_calls": r.llm_calls,
            "total_tokens": r.total_tokens,
            "mode": r.mode,
            "redrafts": r.redrafts,
            "draft_passed": r.draft_passed,
            "metric_leak_caught": r.metric_leak_caught,
            "draft_word_count": r.draft_word_count,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Evaluation — quality report (deterministic + optional LLM-as-judge)
# ---------------------------------------------------------------------------

@app.get("/api/model/propensity")
def model_propensity() -> dict:
    """Metadata for the trained XGBoost propensity model (fit quality + feature
    importances). Returns {"trained": false} until the model has been trained
    via `python -m backend.propensity_model`."""
    if XGB_META_PATH.exists():
        try:
            meta = json.loads(XGB_META_PATH.read_text(encoding="utf-8"))
            meta["trained"] = True
            return meta
        except (json.JSONDecodeError, OSError):
            pass
    return {"trained": False}


@app.get("/api/eval/report")
def eval_report(db: Session = Depends(get_session)) -> dict:
    """Serve the saved eval report (with judge scores if it was run), else
    compute the deterministic metrics live so the page always has data."""
    if REPORT_PATH.exists():
        try:
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            report["source"] = "saved"
            return report
        except (json.JSONDecodeError, OSError):
            pass

    report = compute_report(db, include_judge=False)
    report["source"] = "live"
    return report


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


# ---------------------------------------------------------------------------
# RAG book copilot — grounded Q&A over the advisor's records
# ---------------------------------------------------------------------------

@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    if _store is None or not _store.docs:
        return {
            "answer": "The book index is empty — seed the database and run the pipeline first.",
            "citations": [],
            "grounded": False,
            "mode": "empty",
        }
    result = rag_chat.answer(_store, payload.query, client_id=payload.client_id)
    result["mode"] = _store.mode
    return result


@app.get("/api/chat/suggestions")
def chat_suggestions(
    client_id: str | None = None,
    db: Session = Depends(get_session),
) -> list[str]:
    if client_id:
        c = db.get(Client, client_id)
        name = c.name.split()[0] if c else "this client"
        return [
            f"Why is {name} flagged right now?",
            f"Summarise {name}'s recent activity and notes.",
            f"What did we last discuss with {name}?",
            f"What market signals are relevant to {name}?",
        ]
    return [
        "Which clients mentioned competitors or moving their money?",
        "Who is most at risk of leaving this week, and why?",
        "Which clients had a recent life event?",
        "Summarise the clients ready for an upsell conversation.",
    ]


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

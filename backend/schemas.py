"""NextBest data schemas — the contract between backend stages and the frontend."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input: raw client record from generate_data.py
# ---------------------------------------------------------------------------

class CallLogEntry(BaseModel):
    date: str
    note: str


class LifeEventDetail(BaseModel):
    type: str
    date: str


class TransactionPoint(BaseModel):
    month: str
    portfolio_value: int
    net_flow: int


class BehaviorPoint(BaseModel):
    week: str
    logins: int
    email_opens: int
    sessions: int


class Client(BaseModel):
    client_id: str = Field(pattern=r"^C\d{3}$")
    name: str
    advisor_id: str
    email: Optional[str] = None
    portfolio_value: int
    portfolio_change_pct: float
    withdrawals_last_90_days: int
    account_tenure_years: float
    last_contact_note: str
    call_log: list[CallLogEntry]
    days_since_last_contact: int
    life_events: list[str]
    life_events_detail: list[LifeEventDetail] = Field(default_factory=list)
    login_frequency_change: float
    email_open_rate_change: float
    market_exposure: list[str]
    transactions: list[TransactionPoint] = Field(default_factory=list)
    digital_behavior: list[BehaviorPoint] = Field(default_factory=list)


class Advisor(BaseModel):
    advisor_id: str
    name: str
    title: str


class MarketSignal(BaseModel):
    date: str
    sector: str
    sentiment: Literal["bullish", "neutral", "bearish"]
    signal: str


# ---------------------------------------------------------------------------
# Output: what the agent produces and the UI consumes
# ---------------------------------------------------------------------------

class ReasoningStep(BaseModel):
    agent: str = "orchestrator"  # which agent produced this step
    tool: str
    finding: str
    ts_ms: int


class NextBestAction(BaseModel):
    client_id: str
    name: str
    advisor_id: str = "A001"
    action_type: Literal["URGENT", "OPPORTUNITY", "WATCHLIST"]
    attrition_risk: int = Field(ge=0, le=100)
    upsell_ready: int = Field(ge=0, le=100)
    revenue_impact: int
    revenue_impact_score: int = Field(ge=0, le=100)
    priority_rank: int = Field(ge=1)
    confidence: int = Field(ge=0, le=100)
    segment: dict
    headline: str
    rationale: str
    reasons: list[str]
    draft_message: str
    draft_passed_critique: bool
    reasoning_trace: list[ReasoningStep]
    # New agentic outputs
    framing: str = "check-in"
    portfolio_nudge: Optional[str] = None
    recommended_product: Optional[str] = None
    market_insight: Optional[str] = None
    # Advisor workflow status (persisted)
    action_status: Literal["pending", "accepted", "skipped", "edited"] = "pending"


# ---------------------------------------------------------------------------
# API response shapes
# ---------------------------------------------------------------------------

class SegmentSummary(BaseModel):
    id: int
    label: str
    count: int
    avg_attrition: float
    avg_upsell: float
    total_aum: int
    playbook: str
    member_ids: list[str]


class BookAnalytics(BaseModel):
    total_clients: int
    total_aum: int
    revenue_at_risk: int          # AUM held by high-attrition clients
    upsell_pipeline: int          # sum of revenue_impact for opportunities
    urgent_count: int
    opportunity_count: int
    watchlist_count: int
    avg_days_since_contact: float
    segment_distribution: list[SegmentSummary]


class ClientDetail(Client):
    """Full client record joined with its scored action (nullable)."""
    segment: dict = Field(default_factory=dict)
    lookalikes: list[str] = Field(default_factory=list)
    action: Optional[NextBestAction] = None


class AdvisorActionIn(BaseModel):
    action: Literal["accept", "skip", "edit"]
    draft_text: Optional[str] = None
    feedback: Optional[str] = None


class AdvisorActionOut(BaseModel):
    id: int
    client_id: str
    action: str
    draft_text: Optional[str] = None
    feedback: Optional[str] = None
    created_at: str


# ---------------------------------------------------------------------------
# RAG book copilot
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str
    client_id: Optional[str] = None    # scope answers to one client when set


class ChatCitation(BaseModel):
    client_id: str
    name: str
    doc_type: str
    date: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    grounded: bool
    mode: str                          # "dense" or "hashing" — how retrieval ran

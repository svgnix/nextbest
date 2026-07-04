"""Persistence layer — SQLAlchemy models over SQLite.

One local DB file (backend/data/nextbest.db) holds the advisor book, the
scored agent output, and the advisor's actions/feedback so the app behaves
like a real product: actions persist across restarts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from backend.config import DB_URL


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

class Advisor(Base):
    __tablename__ = "advisors"
    advisor_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)


class Client(Base):
    __tablename__ = "clients"
    client_id = Column(String, primary_key=True)
    advisor_id = Column(String, ForeignKey("advisors.advisor_id"), index=True)
    name = Column(String, nullable=False)
    email = Column(String)

    portfolio_value = Column(Integer, nullable=False)
    portfolio_change_pct = Column(Float, nullable=False)
    withdrawals_last_90_days = Column(Integer, nullable=False)
    account_tenure_years = Column(Float, nullable=False)
    days_since_last_contact = Column(Integer, nullable=False)
    login_frequency_change = Column(Float, nullable=False)
    email_open_rate_change = Column(Float, nullable=False)
    last_contact_note = Column(Text)

    # Engine outputs (filled by the pipeline)
    segment_id = Column(Integer)
    segment_label = Column(String)
    attrition_risk = Column(Integer)
    upsell_ready = Column(Integer)
    revenue_impact = Column(Integer)
    revenue_impact_score = Column(Integer)

    # Rich / nested data as JSON
    life_events = Column(JSON, default=list)
    life_events_detail = Column(JSON, default=list)
    market_exposure = Column(JSON, default=list)
    call_log = Column(JSON, default=list)
    transactions = Column(JSON, default=list)
    digital_behavior = Column(JSON, default=list)
    lookalikes = Column(JSON, default=list)

    action = relationship("ScoredAction", back_populates="client", uselist=False)


class MarketSignal(Base):
    __tablename__ = "market_signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, index=True)
    sector = Column(String, index=True)
    sentiment = Column(String)
    signal = Column(Text)


# ---------------------------------------------------------------------------
# Agent output + advisor workflow
# ---------------------------------------------------------------------------

class ScoredAction(Base):
    __tablename__ = "scored_actions"
    client_id = Column(String, ForeignKey("clients.client_id"), primary_key=True)
    name = Column(String)
    advisor_id = Column(String, index=True)
    action_type = Column(String, index=True)
    attrition_risk = Column(Integer)
    upsell_ready = Column(Integer)
    revenue_impact = Column(Integer)
    revenue_impact_score = Column(Integer)
    priority_rank = Column(Integer, index=True)
    confidence = Column(Integer)
    segment = Column(JSON)
    headline = Column(Text)
    rationale = Column(Text)
    reasons = Column(JSON, default=list)
    draft_message = Column(Text)
    draft_passed_critique = Column(Boolean, default=False)
    reasoning_trace = Column(JSON, default=list)
    framing = Column(String, default="check-in")
    portfolio_nudge = Column(Text)
    recommended_product = Column(String)
    market_insight = Column(Text)
    action_status = Column(String, default="pending")

    client = relationship("Client", back_populates="action")


class AdvisorAction(Base):
    __tablename__ = "advisor_actions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, ForeignKey("clients.client_id"), index=True)
    action = Column(String)  # accept | skip | edit
    draft_text = Column(Text)
    feedback = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Engine / session helpers
# ---------------------------------------------------------------------------

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

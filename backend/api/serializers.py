"""Row -> dict serializers shared by the API routes."""

from __future__ import annotations

from backend.db import Client, ScoredAction

SEGMENT_PLAYBOOKS = {
    "Disengaging": "Proactive re-engagement: personal outreach, surface and fix service gaps, reaffirm value before assets move.",
    "Growth-minded": "Capitalise on momentum: introduce higher-conviction and alternative strategies aligned to life events.",
    "Steady loyalist": "Deepen the relationship: succession and estate planning, periodic reviews, referrals.",
    "New & exploring": "Onboard thoroughly: educate, build trust with regular touchpoints, establish the plan.",
}


def action_to_dict(a: ScoredAction) -> dict:
    return {
        "client_id": a.client_id,
        "name": a.name,
        "advisor_id": a.advisor_id,
        "action_type": a.action_type,
        "attrition_risk": a.attrition_risk,
        "upsell_ready": a.upsell_ready,
        "revenue_impact": a.revenue_impact,
        "revenue_impact_score": a.revenue_impact_score,
        "priority_rank": a.priority_rank,
        "confidence": a.confidence,
        "segment": a.segment or {},
        "headline": a.headline,
        "rationale": a.rationale,
        "reasons": a.reasons or [],
        "draft_message": a.draft_message or "",
        "draft_passed_critique": bool(a.draft_passed_critique),
        "reasoning_trace": a.reasoning_trace or [],
        "framing": a.framing,
        "portfolio_nudge": a.portfolio_nudge,
        "recommended_product": a.recommended_product,
        "market_insight": a.market_insight,
        "action_status": a.action_status or "pending",
    }


def client_summary(c: Client) -> dict:
    """Lightweight roster row."""
    return {
        "client_id": c.client_id,
        "name": c.name,
        "advisor_id": c.advisor_id,
        "portfolio_value": c.portfolio_value,
        "portfolio_change_pct": c.portfolio_change_pct,
        "days_since_last_contact": c.days_since_last_contact,
        "segment": {"id": c.segment_id, "label": c.segment_label} if c.segment_label else {},
        "attrition_risk": c.attrition_risk or 0,
        "upsell_ready": c.upsell_ready or 0,
        "action_type": c.action.action_type if c.action else "WATCHLIST",
    }


def client_detail(c: Client) -> dict:
    return {
        "client_id": c.client_id,
        "name": c.name,
        "advisor_id": c.advisor_id,
        "email": c.email,
        "portfolio_value": c.portfolio_value,
        "portfolio_change_pct": c.portfolio_change_pct,
        "withdrawals_last_90_days": c.withdrawals_last_90_days,
        "account_tenure_years": c.account_tenure_years,
        "days_since_last_contact": c.days_since_last_contact,
        "login_frequency_change": c.login_frequency_change,
        "email_open_rate_change": c.email_open_rate_change,
        "last_contact_note": c.last_contact_note or "",
        "life_events": c.life_events or [],
        "life_events_detail": c.life_events_detail or [],
        "market_exposure": c.market_exposure or [],
        "call_log": c.call_log or [],
        "transactions": c.transactions or [],
        "digital_behavior": c.digital_behavior or [],
        "segment": {"id": c.segment_id, "label": c.segment_label} if c.segment_label else {},
        "lookalikes": c.lookalikes or [],
        "attrition_risk": c.attrition_risk or 0,
        "upsell_ready": c.upsell_ready or 0,
        "revenue_impact": c.revenue_impact or 0,
        "revenue_impact_score": c.revenue_impact_score or 0,
        "action": action_to_dict(c.action) if c.action else None,
    }

"""Tests for the ranking/classification pipeline and the compliance guardrail.

Pure, deterministic checks — no DB, no LLM. They lock in the two behaviours the
demo depends on: retention-first tiered ranking (the most at-risk client on top)
and the metric-leak guard that keeps client-facing drafts clean.
"""

from backend.agents.orchestrator import _local_metric_leak
from backend.run_pipeline import (
    _classify_action_type,
    _compute_confidence,
    _generate_headline,
    _rank_clients,
)
from backend.schemas import NextBestAction, ReasoningStep


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestClassify:
    def test_urgent_when_attrition_dominant(self):
        assert _classify_action_type(80, 10) == "URGENT"

    def test_opportunity_when_upsell_dominant(self):
        assert _classify_action_type(10, 80) == "OPPORTUNITY"

    def test_watchlist_when_both_low(self):
        assert _classify_action_type(30, 40) == "WATCHLIST"

    def test_tie_goes_to_opportunity(self):
        # upsell >= attrition and upsell >= 50 -> OPPORTUNITY
        assert _classify_action_type(50, 50) == "OPPORTUNITY"


# ---------------------------------------------------------------------------
# Tiered ranking (retention first, then blended score within tier)
# ---------------------------------------------------------------------------

class TestRanking:
    def _book(self):
        return [
            {"name": "opp_big", "attrition_risk": 0, "upsell_ready": 90,
             "revenue_impact_score": 100, "action_type": "OPPORTUNITY"},
            {"name": "urgent_small", "attrition_risk": 60, "upsell_ready": 10,
             "revenue_impact_score": 5, "action_type": "URGENT"},
            {"name": "urgent_big", "attrition_risk": 80, "upsell_ready": 0,
             "revenue_impact_score": 50, "action_type": "URGENT"},
            {"name": "watch", "attrition_risk": 20, "upsell_ready": 20,
             "revenue_impact_score": 10, "action_type": "WATCHLIST"},
        ]

    def test_urgent_outranks_bigger_opportunity(self):
        ranked = _rank_clients(self._book())
        order = [c["name"] for c in sorted(ranked, key=lambda c: c["priority_rank"])]
        # Both URGENT clients come before the large OPPORTUNITY and the WATCHLIST.
        assert order == ["urgent_big", "urgent_small", "opp_big", "watch"]

    def test_ranks_are_dense_and_1_based(self):
        ranked = _rank_clients(self._book())
        ranks = sorted(c["priority_rank"] for c in ranked)
        assert ranks == [1, 2, 3, 4]

    def test_blend_used_within_tier(self):
        book = [
            {"name": "hi_score_lo_money", "attrition_risk": 90, "upsell_ready": 0,
             "revenue_impact_score": 0, "action_type": "URGENT"},
            {"name": "lo_score_hi_money", "attrition_risk": 55, "upsell_ready": 0,
             "revenue_impact_score": 100, "action_type": "URGENT"},
        ]
        ranked = {c["name"]: c["priority_rank"] for c in _rank_clients(book)}
        # 0.6*90 + 0.4*0 = 54  vs  0.6*55 + 0.4*100 = 73 -> money wins here.
        assert ranked["lo_score_hi_money"] < ranked["hi_score_lo_money"]


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_floor_and_ceiling(self):
        weak = _compute_confidence({"call_log": []}, {"attrition_rules_fired": [], "upsell_rules_fired": []}, False)
        assert weak == 70
        strong = _compute_confidence(
            {"call_log": [{}, {}]},
            {"attrition_rules_fired": ["a", "b", "c"], "upsell_rules_fired": ["d"]},
            True,
        )
        assert strong == 100

    def test_never_exceeds_100(self):
        val = _compute_confidence(
            {"call_log": [{}, {}, {}]},
            {"attrition_rules_fired": ["a", "b", "c", "d"], "upsell_rules_fired": ["e", "f"]},
            True,
        )
        assert val <= 100


# ---------------------------------------------------------------------------
# Headline templating
# ---------------------------------------------------------------------------

class TestHeadline:
    def test_education_headline(self):
        client = {"action_type": "URGENT", "life_events": ["child_education"]}
        assert _generate_headline(client) == "Reconnect before she moves the education fund"

    def test_default_when_no_event(self):
        client = {"action_type": "URGENT", "life_events": []}
        assert _generate_headline(client) == "Re-engage before silence becomes attrition"


# ---------------------------------------------------------------------------
# Compliance guardrail (metric leak)
# ---------------------------------------------------------------------------

class TestMetricLeakGuard:
    def test_catches_percentage(self):
        assert _local_metric_leak("Your portfolio is up 22% this year.") is not None

    def test_catches_internal_terms(self):
        for text in ("your attrition risk", "an upsell opportunity", "your propensity", "churn signals"):
            assert _local_metric_leak(text) is not None, text

    def test_clean_message_passes(self):
        clean = ("Hi Priya, I've been thinking about our last chat on your daughter's education. "
                 "Could we find twenty minutes this week to reconnect?")
        assert _local_metric_leak(clean) is None


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------

class TestSchema:
    def test_next_best_action_roundtrip(self):
        action = NextBestAction(
            client_id="C001",
            name="Priya Mehta",
            advisor_id="A001",
            action_type="URGENT",
            attrition_risk=80,
            upsell_ready=10,
            revenue_impact=16_000_000,
            revenue_impact_score=61,
            priority_rank=1,
            confidence=100,
            segment={"id": 2, "label": "Disengaging"},
            headline="Reconnect before she moves the education fund",
            rationale="Not contacted in 94 days with declining engagement.",
            reasons=["No contact in >90 days", "Life event: child education"],
            draft_message="Hi Priya, let's reconnect this week.",
            draft_passed_critique=True,
            reasoning_trace=[ReasoningStep(agent="orchestrator", tool="plan", finding="Framing.", ts_ms=1)],
        )
        dumped = action.model_dump()
        assert dumped["priority_rank"] == 1
        assert dumped["action_type"] == "URGENT"
        assert dumped["reasoning_trace"][0]["tool"] == "plan"

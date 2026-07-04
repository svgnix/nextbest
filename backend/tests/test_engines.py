"""Unit tests for segment.py and propensity.py — hero client sanity checks."""

import json
from pathlib import Path

import pytest

from backend.propensity import run_propensity, score_client
from backend.segment import run_segmentation

DATA_PATH = Path(__file__).parent.parent / "data" / "clients.json"


@pytest.fixture(scope="module")
def clients() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def segmented(clients) -> list[dict]:
    return run_segmentation(clients)


@pytest.fixture(scope="module")
def scored(segmented) -> list[dict]:
    return run_propensity(segmented)


# ---------------------------------------------------------------------------
# Propensity: hero client score bands
# ---------------------------------------------------------------------------

class TestPropensityHeroes:
    def test_priya_attrition_high(self, clients):
        priya = next(c for c in clients if c["name"] == "Priya Mehta")
        result = score_client(priya)
        assert result["attrition_risk"] >= 75, f"Priya attrition {result['attrition_risk']} too low"
        assert result["attrition_risk"] <= 85, f"Priya attrition {result['attrition_risk']} too high"

    def test_priya_rules_fired(self, clients):
        priya = next(c for c in clients if c["name"] == "Priya Mehta")
        result = score_client(priya)
        assert len(result["attrition_rules_fired"]) >= 2

    def test_arjun_upsell_band(self, clients):
        arjun = next(c for c in clients if c["name"] == "Arjun Rao")
        result = score_client(arjun)
        assert result["upsell_ready"] >= 60, f"Arjun upsell {result['upsell_ready']} too low"
        assert result["upsell_ready"] <= 70, f"Arjun upsell {result['upsell_ready']} too high"

    def test_rahul_upsell_high(self, clients):
        rahul = next(c for c in clients if c["name"] == "Rahul Kapoor")
        result = score_client(rahul)
        assert result["upsell_ready"] >= 80

    def test_sharma_watchlist(self, clients):
        sharma = next(c for c in clients if "Sharma" in c["name"])
        result = score_client(sharma)
        assert result["attrition_risk"] < 50
        assert result["upsell_ready"] < 50

    def test_deepa_attrition_high(self, clients):
        deepa = next(c for c in clients if c["name"] == "Deepa Krishnan")
        result = score_client(deepa)
        assert result["attrition_risk"] >= 60


# ---------------------------------------------------------------------------
# Propensity: revenue impact
# ---------------------------------------------------------------------------

class TestRevenueImpact:
    def test_revenue_impact_formula(self, clients):
        arjun = next(c for c in clients if c["name"] == "Arjun Rao")
        result = score_client(arjun)
        expected = round((result["upsell_ready"] / 100) * arjun["portfolio_value"])
        assert result["revenue_impact"] == expected

    def test_revenue_impact_score_range(self, scored):
        for c in scored:
            assert 0 <= c["revenue_impact_score"] <= 100


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

class TestSegmentation:
    def test_all_clients_segmented(self, segmented):
        for c in segmented:
            assert "segment" in c
            assert "id" in c["segment"]
            assert "label" in c["segment"]
            assert c["segment"]["label"] in [
                "Disengaging", "Growth-minded", "Steady loyalist", "New & exploring"
            ]

    def test_lookalikes_present(self, segmented):
        for c in segmented:
            assert "lookalikes" in c
            assert 2 <= len(c["lookalikes"]) <= 3
            assert c["client_id"] not in c["lookalikes"]

    def test_deterministic(self, clients):
        seg1 = run_segmentation(clients)
        seg2 = run_segmentation(clients)
        for a, b in zip(seg1, seg2):
            assert a["segment"] == b["segment"]
            assert a["lookalikes"] == b["lookalikes"]

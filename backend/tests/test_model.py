"""Tests for the XGBoost propensity model (Engine 2, learned variant).

These verify the model is real and faithful: it learns the rule scoring policy
from the shared feature interface, predicts valid scores, and can be swapped
into score_client without disturbing the explainable fired-rule lists.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from backend.propensity import score_client
from backend.propensity_model import (
    FEATURE_NAMES,
    PropensityModel,
    _rule_labels,
    vectorize,
)

DATA_PATH = Path(__file__).parent.parent / "data" / "clients.json"


@pytest.fixture(scope="module")
def clients() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model(clients) -> PropensityModel:
    """Train a lightweight in-memory model on the book (fast, no disk writes)."""
    from xgboost import XGBRegressor

    X = np.array([vectorize(c) for c in clients], dtype=float)
    y_att, y_ups = _rule_labels(clients)
    params = dict(n_estimators=150, max_depth=4, learning_rate=0.15, random_state=42, n_jobs=1)
    att = XGBRegressor(**params)
    att.fit(X, np.array(y_att, dtype=float))
    ups = XGBRegressor(**params)
    ups.fit(X, np.array(y_ups, dtype=float))
    return PropensityModel(att, ups)


class TestFeatures:
    def test_vector_length(self, clients):
        assert len(vectorize(clients[0])) == len(FEATURE_NAMES)

    def test_vector_all_floats(self, clients):
        assert all(isinstance(x, float) for x in vectorize(clients[0]))


class TestPredictions:
    def test_scores_in_range(self, clients, model):
        for c in clients[:50]:
            att = model.predict_attrition(c)
            ups = model.predict_upsell(c)
            assert isinstance(att, int) and 0 <= att <= 100
            assert isinstance(ups, int) and 0 <= ups <= 100

    def test_learns_the_policy(self, clients, model):
        """Model predictions should closely track the rule scores it trained on."""
        y_att, y_ups = _rule_labels(clients)
        pred_att = [model.predict_attrition(c) for c in clients]
        pred_ups = [model.predict_upsell(c) for c in clients]
        mae_att = float(np.mean(np.abs(np.array(pred_att) - np.array(y_att))))
        mae_ups = float(np.mean(np.abs(np.array(pred_ups) - np.array(y_ups))))
        assert mae_att < 5, f"attrition MAE {mae_att} too high"
        assert mae_ups < 5, f"upsell MAE {mae_ups} too high"


class TestHeroFidelity:
    def _hero(self, clients, name):
        return next(c for c in clients if name in c["name"])

    def test_priya_high_attrition(self, clients, model):
        assert model.predict_attrition(self._hero(clients, "Priya")) >= 70

    def test_rahul_high_upsell(self, clients, model):
        assert model.predict_upsell(self._hero(clients, "Rahul")) >= 75

    def test_sharma_low_both(self, clients, model):
        sharma = self._hero(clients, "Sharma")
        assert model.predict_attrition(sharma) < 55
        assert model.predict_upsell(sharma) < 55


class TestDropInSeam:
    def test_score_client_uses_model_but_keeps_rules(self, clients, model):
        priya = next(c for c in clients if "Priya" in c["name"])
        result = score_client(priya, model=model)
        assert result["scorer"] == "xgboost"
        # Explainability is preserved: fired rules still come from the rule engine.
        assert len(result["attrition_rules_fired"]) >= 2
        # Revenue impact is derived from the (model) scores and stays positive.
        assert result["revenue_impact"] > 0

    def test_rules_mode_default(self, clients):
        priya = next(c for c in clients if "Priya" in c["name"])
        assert score_client(priya)["scorer"] == "rules"

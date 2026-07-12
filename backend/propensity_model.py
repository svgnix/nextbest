"""Engine 2 (learned variant) — XGBoost propensity model.

The rule-based engine in ``propensity.py`` is the transparent, explainable
baseline the RM sees (it lists exactly which rules fired). This module is the
"the model is real" flourish the pitch names: a pair of small **XGBoost**
regressors trained to reproduce that scoring policy from the same
``features_for(client)`` interface the rules use.

It is honest about what it is: the labels are the rule scores, so the model
*learns the policy* rather than discovering new signal from labelled outcomes
(there are none — synthetic data, no compliance-cleared ground truth). The value
it demonstrates is the **drop-in seam**: the agent, the ranking, and the UI all
consume ``attrition_risk`` / ``upsell_ready`` and never need to know whether a
rule table or a gradient-boosted model produced them. Feature importances also
give a data-driven view of which signals drive churn/upsell.

Train:   python -m backend.propensity_model
Use:     set USE_XGB_PROPENSITY=1 (run_pipeline then scores with the model)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.config import (
    CLIENTS_PATH,
    SEED,
    XGB_ATTRITION_PATH,
    XGB_META_PATH,
    XGB_UPSELL_PATH,
)
from backend.propensity import _score_attrition, _score_upsell, features_for

# The learned model consumes the same features the rules do (plus a couple of
# life-event flags the rules key off), so it is a true drop-in replacement.
FEATURE_NAMES = [
    "days_since_last_contact",
    "login_frequency_change",
    "email_open_rate_change",
    "withdrawals_last_90_days",
    "account_tenure_years",
    "portfolio_change_pct",
    "portfolio_value",
    "has_property_purchase",
    "has_inheritance",
    "n_life_events",
]

_XGB_PARAMS = dict(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.12,
    subsample=0.9,
    colsample_bytree=0.9,
    random_state=SEED,
    objective="reg:squarederror",
    n_jobs=1,
)


def vectorize(client: dict) -> list[float]:
    """Turn a client into the numeric feature vector the model expects."""
    f = features_for(client)
    events = f["life_events"]
    return [
        float(f["days_since_last_contact"]),
        float(f["login_frequency_change"]),
        float(f["email_open_rate_change"]),
        float(f["withdrawals_last_90_days"]),
        float(f["account_tenure_years"]),
        float(f["portfolio_change_pct"]),
        float(f["portfolio_value"]),
        1.0 if "property_purchase" in events else 0.0,
        1.0 if "inheritance" in events else 0.0,
        float(len(events)),
    ]


def _rule_labels(clients: list[dict]) -> tuple[list[float], list[float]]:
    y_att, y_ups = [], []
    for c in clients:
        feat = features_for(c)
        y_att.append(float(_score_attrition(feat)[0]))
        y_ups.append(float(_score_upsell(feat)[0]))
    return y_att, y_ups


def train(clients: list[dict]) -> dict:
    """Train both regressors on the book, persist them, and return a metrics
    summary (fit quality + feature importances) for the eval surface."""
    import numpy as np
    from sklearn.metrics import mean_absolute_error, r2_score
    from xgboost import XGBRegressor

    X = np.array([vectorize(c) for c in clients], dtype=float)
    y_att, y_ups = _rule_labels(clients)
    y_att = np.array(y_att, dtype=float)
    y_ups = np.array(y_ups, dtype=float)

    att_model = XGBRegressor(**_XGB_PARAMS)
    att_model.fit(X, y_att)
    ups_model = XGBRegressor(**_XGB_PARAMS)
    ups_model.fit(X, y_ups)

    XGB_ATTRITION_PATH.parent.mkdir(parents=True, exist_ok=True)
    att_model.save_model(str(XGB_ATTRITION_PATH))
    ups_model.save_model(str(XGB_UPSELL_PATH))

    def _metrics(model, y_true) -> dict:
        pred = model.predict(X)
        importances = model.feature_importances_
        ranked = sorted(
            ({"feature": FEATURE_NAMES[i], "importance": round(float(v), 4)}
             for i, v in enumerate(importances)),
            key=lambda d: d["importance"],
            reverse=True,
        )
        return {
            "r2": round(float(r2_score(y_true, pred)), 4),
            "mae": round(float(mean_absolute_error(y_true, pred)), 3),
            "importances": ranked,
        }

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model": "xgboost.XGBRegressor",
        "n_samples": len(clients),
        "n_features": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
        "labels": "rule-engine scores (learns the scoring policy)",
        "params": {k: v for k, v in _XGB_PARAMS.items()},
        "attrition": _metrics(att_model, y_att),
        "upsell": _metrics(ups_model, y_ups),
    }
    XGB_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


class PropensityModel:
    """Loaded XGBoost regressors with a rules-compatible predict interface."""

    def __init__(self, att_model, ups_model) -> None:
        self._att = att_model
        self._ups = ups_model

    @classmethod
    def load(cls) -> "PropensityModel | None":
        """Load the persisted models, or None if they haven't been trained."""
        if not (XGB_ATTRITION_PATH.exists() and XGB_UPSELL_PATH.exists()):
            return None
        from xgboost import XGBRegressor

        att = XGBRegressor()
        att.load_model(str(XGB_ATTRITION_PATH))
        ups = XGBRegressor()
        ups.load_model(str(XGB_UPSELL_PATH))
        return cls(att, ups)

    def _predict(self, model, client: dict) -> int:
        import numpy as np

        raw = float(model.predict(np.array([vectorize(client)], dtype=float))[0])
        return int(max(0, min(100, round(raw))))

    def predict_attrition(self, client: dict) -> int:
        return self._predict(self._att, client)

    def predict_upsell(self, client: dict) -> int:
        return self._predict(self._ups, client)


def main() -> None:
    clients = json.loads(CLIENTS_PATH.read_text(encoding="utf-8"))
    print(f"Training XGBoost propensity models on {len(clients)} clients...")
    meta = train(clients)
    for target in ("attrition", "upsell"):
        m = meta[target]
        top = ", ".join(f"{d['feature']} ({d['importance']:.2f})" for d in m["importances"][:3])
        print(f"  {target:>9}: R2={m['r2']:.3f}  MAE={m['mae']:.2f}  top features: {top}")
    print(f"Saved models + metrics -> {XGB_META_PATH.parent}")


if __name__ == "__main__":
    main()

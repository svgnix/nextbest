"""Engine 2 — Propensity scoring (rule-based).

Pure, deterministic, no LLM. Computes attrition_risk, upsell_ready,
revenue_impact, and revenue_impact_score per client. Returns the list
of fired rules for explainability.

The scoring sits behind a clean features_for(client) interface so an
XGBoost model can be dropped in later without touching callers.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Feature extraction (stable interface for future model swap)
# ---------------------------------------------------------------------------

def features_for(client: dict) -> dict:
    """Extract the feature dict used by the scoring functions.

    This is the contract: a future XGBoost model accepts this same dict.
    """
    return {
        "days_since_last_contact": client["days_since_last_contact"],
        "login_frequency_change": client["login_frequency_change"],
        "email_open_rate_change": client["email_open_rate_change"],
        "withdrawals_last_90_days": client["withdrawals_last_90_days"],
        "account_tenure_years": client["account_tenure_years"],
        "portfolio_change_pct": client["portfolio_change_pct"],
        "portfolio_value": client["portfolio_value"],
        "life_events": list(client["life_events"]),
    }


# ---------------------------------------------------------------------------
# Attrition risk scoring (SPEC §4 exact rules)
# ---------------------------------------------------------------------------

def _score_attrition(features: dict) -> tuple[int, list[str]]:
    score = 0
    fired: list[str] = []

    if features["days_since_last_contact"] > 90:
        score += 40
        fired.append("No contact in >90 days (+40)")
    elif features["days_since_last_contact"] > 60:
        score += 20
        fired.append("No contact in >60 days (+20)")

    if features["login_frequency_change"] < -30:
        score += 20
        fired.append(f"Login frequency down {features['login_frequency_change']:.0f}% (+20)")

    if features["email_open_rate_change"] < -40:
        score += 15
        fired.append(f"Email open rate down {features['email_open_rate_change']:.0f}% (+15)")

    if features["withdrawals_last_90_days"] > 100_000:
        score += 25
        fired.append(f"Large withdrawal ${features['withdrawals_last_90_days']:,} (+25)")

    if features["account_tenure_years"] < 2:
        score += 10
        fired.append(f"Short tenure {features['account_tenure_years']:.1f}y (+10)")

    return min(score, 100), fired


# ---------------------------------------------------------------------------
# Upsell readiness scoring (SPEC §4 exact rules)
# ---------------------------------------------------------------------------

def _score_upsell(features: dict) -> tuple[int, list[str]]:
    score = 0
    fired: list[str] = []

    if features["portfolio_change_pct"] > 15:
        score += 35
        fired.append(f"Portfolio up {features['portfolio_change_pct']:.1f}% (+35)")

    if "property_purchase" in features["life_events"]:
        score += 30
        fired.append("Life event: property purchase (+30)")

    if "inheritance" in features["life_events"]:
        score += 25
        fired.append("Life event: inheritance (+25)")

    if features["days_since_last_contact"] < 30:
        score += 15
        fired.append("Recently contacted <30 days (+15)")

    if features["account_tenure_years"] > 5:
        score += 10
        fired.append(f"Loyal client {features['account_tenure_years']:.1f}y (+10)")

    return min(score, 100), fired


# ---------------------------------------------------------------------------
# Revenue impact — the revenue *at stake*, whichever way it can move
# ---------------------------------------------------------------------------

def _compute_revenue_impact(attrition_risk: int, upsell_ready: int, portfolio_value: int) -> int:
    """Dollar value the relationship puts in play.

    For an at-risk client it's the revenue at risk of walking; for a receptive
    client it's the upside from deepening the relationship. Taking the stronger
    of the two against the portfolio means a large, highly-at-risk client
    (revenue to *lose*) ranks alongside a large, highly-receptive one (revenue
    to *win*) — both are big fires, which is what the RM should triage first.
    """
    stake = max(attrition_risk, upsell_ready) / 100
    return round(stake * portfolio_value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_client(client: dict, model=None) -> dict:
    """Score a single client. Returns a dict of propensity fields.

    ``model`` is an optional trained propensity model (see
    ``backend.propensity_model.PropensityModel``). When supplied, the
    ``attrition_risk`` / ``upsell_ready`` scores come from the model; when None
    they come from the rule engine. The fired-rule lists are always computed
    from the rules so the RM keeps a transparent explanation either way.
    """
    feat = features_for(client)

    attrition_risk, attrition_rules = _score_attrition(feat)
    upsell_ready, upsell_rules = _score_upsell(feat)

    if model is not None:
        attrition_risk = model.predict_attrition(client)
        upsell_ready = model.predict_upsell(client)

    revenue_impact = _compute_revenue_impact(attrition_risk, upsell_ready, feat["portfolio_value"])

    return {
        "attrition_risk": attrition_risk,
        "upsell_ready": upsell_ready,
        "revenue_impact": revenue_impact,
        "attrition_rules_fired": attrition_rules,
        "upsell_rules_fired": upsell_rules,
        "scorer": "xgboost" if model is not None else "rules",
    }


def run_propensity(clients: list[dict], model=None) -> list[dict]:
    """Score all clients. Adds propensity fields + normalized revenue_impact_score.

    Pass ``model`` to score with the trained XGBoost engine instead of the rules
    (see ``score_client``). Returns enriched client dicts with:
      attrition_risk, upsell_ready, revenue_impact, revenue_impact_score,
      attrition_rules_fired, upsell_rules_fired
    """
    scored = []
    for client in clients:
        result = score_client(client, model=model)
        scored.append({**client, **result})

    # Normalize revenue_impact to 0-100 (min-max across the book)
    impacts = [c["revenue_impact"] for c in scored]
    min_impact = min(impacts)
    max_impact = max(impacts)
    spread = max_impact - min_impact if max_impact != min_impact else 1

    for client in scored:
        client["revenue_impact_score"] = round(
            ((client["revenue_impact"] - min_impact) / spread) * 100
        )

    return scored

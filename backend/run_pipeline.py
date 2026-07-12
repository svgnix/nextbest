"""Run the full NextBest pipeline: DB -> engines -> multi-agent -> DB.

Loads the advisor book from SQLite, runs segmentation + propensity across the
whole book, runs the multi-agent orchestrator for the top-priority clients,
and writes the scored actions back to the DB (also dumps a JSON snapshot for
debugging). Seeds the DB automatically if it is empty.
"""

from __future__ import annotations

import json

from backend.agents import run_orchestrator_for_client
from backend.config import DATA_DIR, TOP_N_DRAFT, USE_XGB_PROPENSITY
from backend.db import AgentRun, Client, MarketSignal, ScoredAction, SessionLocal, init_db
from backend.propensity import run_propensity
from backend.propensity_model import PropensityModel
from backend.schemas import NextBestAction, ReasoningStep
from backend.segment import run_segmentation
from backend.tools import init_tools

SNAPSHOT_PATH = DATA_DIR / "scored_clients.json"


# ---------------------------------------------------------------------------
# DB <-> dict helpers
# ---------------------------------------------------------------------------

def _client_to_dict(c: Client) -> dict:
    return {
        "client_id": c.client_id,
        "advisor_id": c.advisor_id,
        "name": c.name,
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
    }


# ---------------------------------------------------------------------------
# Ranking and classification (SPEC §6)
# ---------------------------------------------------------------------------

def _classify_action_type(attrition: int, upsell: int) -> str:
    if attrition > upsell and attrition >= 50:
        return "URGENT"
    if upsell >= attrition and upsell >= 50:
        return "OPPORTUNITY"
    return "WATCHLIST"


def _compute_confidence(client: dict, propensity: dict, draft_passed: bool) -> int:
    confidence = 70
    rules_fired = len(propensity.get("attrition_rules_fired", [])) + len(propensity.get("upsell_rules_fired", []))
    if rules_fired >= 3:
        confidence += 10
    if len(client.get("call_log", [])) >= 2:
        confidence += 10
    if draft_passed:
        confidence += 10
    return min(confidence, 100)


# Triage order: retention risks first, then opportunities, then routine
# check-ins. This makes the morning feed read as "most at-risk on top" (the
# demo bar) rather than letting a large upsell outrank a client about to leave.
_TIER = {"URGENT": 0, "OPPORTUNITY": 1, "WATCHLIST": 2}


def _rank_clients(scored: list[dict]) -> list[dict]:
    for c in scored:
        # Within a tier, blend urgency (attrition/upsell strength) with the
        # dollars at stake so both "who's most likely to move" and "how much is
        # on the line" shape the order (the pitch's revenue-impact + risk rank).
        c["_blend"] = 0.6 * max(c["attrition_risk"], c["upsell_ready"]) + 0.4 * c["revenue_impact_score"]
    scored.sort(key=lambda c: (_TIER.get(c["action_type"], 3), -c["_blend"]))
    for rank, c in enumerate(scored, 1):
        c["priority_rank"] = rank
        del c["_blend"]
    return scored


# ---------------------------------------------------------------------------
# Headline / rationale / reasons
# ---------------------------------------------------------------------------

_HEADLINE_TEMPLATES = {
    "URGENT": {
        "child_education": "Reconnect before she moves the education fund",
        "retirement": "Check in before retirement plans shift elsewhere",
        "business_sale": "Re-engage before business proceeds leave the book",
        "divorce_settlement": "Sensitive moment — reach out before silence becomes distance",
        "relocation": "Reconnect before the move disrupts the relationship",
        "_default": "Re-engage before silence becomes attrition",
    },
    "OPPORTUNITY": {
        "property_purchase": "Help channel property proceeds into diversified growth",
        "inheritance": "Guide new wealth into a long-term allocation plan",
        "business_sale": "Position for capital redeployment after the exit",
        "_default": "Portfolio momentum creates an opening for expansion",
    },
    "WATCHLIST": {"_default": "Routine check-in to stay present"},
}


def _generate_headline(client: dict) -> str:
    templates = _HEADLINE_TEMPLATES.get(client["action_type"], _HEADLINE_TEMPLATES["WATCHLIST"])
    for event in client.get("life_events", []):
        if event in templates:
            return templates[event]
    return templates["_default"]


def _generate_rationale(client: dict, propensity: dict) -> str:
    parts = []
    if propensity["attrition_risk"] >= 50:
        parts.append(f"Not contacted in {client['days_since_last_contact']} days with declining engagement signals")
    if propensity["upsell_ready"] >= 50:
        parts.append(f"Strong growth signals ({client['portfolio_change_pct']:+.1f}% portfolio) with life event triggers")
    if client.get("life_events"):
        events = ", ".join(e.replace("_", " ") for e in client["life_events"])
        parts.append(f"life event context: {events}")
    if not parts:
        parts.append("Mild engagement dip warrants a light touch-point")
    return "; ".join(parts) + "."


def _collect_reasons(propensity: dict, client: dict) -> list[str]:
    reasons = []
    for rule in propensity.get("attrition_rules_fired", [])[:3]:
        reasons.append(rule.split("(")[0].strip())
    for rule in propensity.get("upsell_rules_fired", [])[:3]:
        reasons.append(rule.split("(")[0].strip())
    for event in client.get("life_events", []):
        reasons.append(f"Life event: {event.replace('_', ' ')}")
    return reasons[:5]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> list[dict]:
    init_db()
    db = SessionLocal()
    try:
        client_rows = db.query(Client).all()
        if not client_rows:
            print("DB is empty. Run `python -m backend.seed` first.")
            return []

        clients = [_client_to_dict(c) for c in client_rows]
        market = [
            {"date": m.date, "sector": m.sector, "sentiment": m.sentiment, "signal": m.signal}
            for m in db.query(MarketSignal).all()
        ]

        print(f"[1/4] Loaded {len(clients)} clients from DB.")

        print("[2/4] Running segmentation (KMeans k=4)...")
        segmented = run_segmentation(clients)

        model = None
        if USE_XGB_PROPENSITY:
            model = PropensityModel.load()
            if model is None:
                print("      USE_XGB_PROPENSITY set but no trained model found — "
                      "run `python -m backend.propensity_model`. Falling back to rules.")
        scorer = "XGBoost model" if model is not None else "rule engine"
        print(f"[3/4] Running propensity scoring ({scorer})...")
        scored = run_propensity(segmented, model=model)
        for c in scored:
            c["action_type"] = _classify_action_type(c["attrition_risk"], c["upsell_ready"])
        ranked = _rank_clients(scored)

        init_tools(clients, segmented, market)

        print(f"[4/4] Running multi-agent orchestrator for top {TOP_N_DRAFT} clients...")
        results: list[dict] = []
        agent_runs: list[dict] = []
        for i, client in enumerate(ranked):
            propensity_data = {
                "attrition_risk": client["attrition_risk"],
                "upsell_ready": client["upsell_ready"],
                "revenue_impact": client["revenue_impact"],
                "attrition_rules_fired": client.get("attrition_rules_fired", []),
                "upsell_rules_fired": client.get("upsell_rules_fired", []),
            }

            draft_message, draft_passed, reasoning_trace = "", False, []
            framing, market_insight, portfolio_nudge, recommended_product = "check-in", None, None, None

            if i < TOP_N_DRAFT:
                print(f"  Orchestrating {client['name']} (rank #{client['priority_rank']})...")
                try:
                    st = run_orchestrator_for_client(client, propensity_data)
                    draft_message = st.get("draft_message", "")
                    draft_passed = st.get("draft_passed_critique", False)
                    reasoning_trace = st.get("reasoning_trace", [])
                    framing = st.get("framing", "check-in")
                    market_insight = st.get("market_insight") or None
                    portfolio_nudge = st.get("portfolio_nudge") or None
                    recommended_product = st.get("recommended_product") or None

                    tel = st.get("telemetry", {})
                    attempts = st.get("critique_attempts", 0)
                    agent_runs.append({
                        "client_id": client["client_id"],
                        "name": client["name"],
                        "advisor_id": client.get("advisor_id", "A001"),
                        "priority_rank": client["priority_rank"],
                        "framing": framing,
                        "consulted": st.get("consulted", []),
                        "total_ms": tel.get("total_ms", 0.0),
                        "node_timings": tel.get("node_timings", {}),
                        "llm_calls": tel.get("llm_calls", 0),
                        "prompt_tokens": tel.get("prompt_tokens", 0),
                        "completion_tokens": tel.get("completion_tokens", 0),
                        "total_tokens": tel.get("total_tokens", 0),
                        "mode": tel.get("mode", "mock"),
                        "critique_attempts": attempts,
                        "redrafts": max(0, attempts - 1),
                        "draft_passed": draft_passed,
                        "metric_leak_caught": tel.get("metric_leak_caught", False),
                        "draft_word_count": len(draft_message.split()),
                    })
                except Exception as e:  # noqa: BLE001
                    print(f"    Agent error for {client['name']}: {e}")

            action = NextBestAction(
                client_id=client["client_id"],
                name=client["name"],
                advisor_id=client.get("advisor_id", "A001"),
                action_type=client["action_type"],
                attrition_risk=client["attrition_risk"],
                upsell_ready=client["upsell_ready"],
                revenue_impact=client["revenue_impact"],
                revenue_impact_score=client["revenue_impact_score"],
                priority_rank=client["priority_rank"],
                confidence=_compute_confidence(client, propensity_data, draft_passed),
                segment=client["segment"],
                headline=_generate_headline(client),
                rationale=_generate_rationale(client, propensity_data),
                reasons=_collect_reasons(propensity_data, client),
                draft_message=draft_message,
                draft_passed_critique=draft_passed,
                reasoning_trace=[ReasoningStep(**s) for s in reasoning_trace],
                framing=framing,
                portfolio_nudge=portfolio_nudge,
                recommended_product=recommended_product,
                market_insight=market_insight,
            )
            results.append(action.model_dump())

            # Persist engine outputs onto the client row.
            row = db.get(Client, client["client_id"])
            row.segment_id = client["segment"]["id"]
            row.segment_label = client["segment"]["label"]
            row.attrition_risk = client["attrition_risk"]
            row.upsell_ready = client["upsell_ready"]
            row.revenue_impact = client["revenue_impact"]
            row.revenue_impact_score = client["revenue_impact_score"]
            row.lookalikes = client.get("lookalikes", [])

        _persist_actions(db, results)
        _persist_agent_runs(db, agent_runs)
        db.commit()

        results.sort(key=lambda r: r["priority_rank"])
        SNAPSHOT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nDone. Wrote {len(results)} actions to DB (+ snapshot {SNAPSHOT_PATH.name}).")
        return results
    finally:
        db.close()


def _persist_actions(db, results: list[dict]) -> None:
    db.query(ScoredAction).delete()
    for r in results:
        db.add(ScoredAction(
            client_id=r["client_id"],
            name=r["name"],
            advisor_id=r["advisor_id"],
            action_type=r["action_type"],
            attrition_risk=r["attrition_risk"],
            upsell_ready=r["upsell_ready"],
            revenue_impact=r["revenue_impact"],
            revenue_impact_score=r["revenue_impact_score"],
            priority_rank=r["priority_rank"],
            confidence=r["confidence"],
            segment=r["segment"],
            headline=r["headline"],
            rationale=r["rationale"],
            reasons=r["reasons"],
            draft_message=r["draft_message"],
            draft_passed_critique=r["draft_passed_critique"],
            reasoning_trace=r["reasoning_trace"],
            framing=r["framing"],
            portfolio_nudge=r["portfolio_nudge"],
            recommended_product=r["recommended_product"],
            market_insight=r["market_insight"],
            action_status="pending",
        ))


def _persist_agent_runs(db, runs: list[dict]) -> None:
    db.query(AgentRun).delete()
    for r in runs:
        db.add(AgentRun(**r))


if __name__ == "__main__":
    run_pipeline()

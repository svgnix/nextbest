"""Agent tools — the data lookups and engine calls the specialist agents use.

Each tool takes minimal input and returns a dict the agents can reason over.
Populated once via init_tools() before the agent loop runs, so tools stay
decoupled from the persistence layer.
"""

from __future__ import annotations

from backend.market_data import FALLBACK_SIGNAL_TEXT
from backend.propensity import score_client

# ---------------------------------------------------------------------------
# Module-level caches (populated by init_tools before agents run)
# ---------------------------------------------------------------------------

_SEGMENTED_CLIENTS: dict[str, dict] = {}
_RAW_CLIENTS: dict[str, dict] = {}
_MARKET_FEED: list[dict] = []


def init_tools(clients: list[dict], segmented: list[dict], market: list[dict] | None = None) -> None:
    """Initialize tool caches. Call once before running the agent loop."""
    _RAW_CLIENTS.clear()
    _SEGMENTED_CLIENTS.clear()
    _MARKET_FEED.clear()
    for c in clients:
        _RAW_CLIENTS[c["client_id"]] = c
    for c in segmented:
        _SEGMENTED_CLIENTS[c["client_id"]] = c
    if market:
        _MARKET_FEED.extend(market)


# ---------------------------------------------------------------------------
# Tool 1: get_client_segment
# ---------------------------------------------------------------------------

def get_client_segment(client_id: str) -> dict:
    """Returns segment {id, label}, lookalikes, and driving behavioral features."""
    c = _SEGMENTED_CLIENTS[client_id]
    return {
        "segment": c["segment"],
        "lookalikes": c["lookalikes"],
        "driving_features": {
            "login_frequency_change": c["login_frequency_change"],
            "email_open_rate_change": c["email_open_rate_change"],
            "days_since_last_contact": c["days_since_last_contact"],
            "withdrawals_last_90_days": c["withdrawals_last_90_days"],
            "portfolio_change_pct": c["portfolio_change_pct"],
            "life_events_count": len(c["life_events"]),
        },
    }


# ---------------------------------------------------------------------------
# Tool 2: compute_propensity
# ---------------------------------------------------------------------------

def compute_propensity(client_id: str) -> dict:
    """Returns attrition_risk, upsell_ready, revenue_impact, and fired rules."""
    c = _RAW_CLIENTS[client_id]
    return score_client(c)


# ---------------------------------------------------------------------------
# Tool 3: get_call_context (retrieval over call_log)
# ---------------------------------------------------------------------------

def get_call_context(client_id: str, query: str = "") -> dict:
    """Retrieve the most relevant past call-log notes for the client."""
    c = _RAW_CLIENTS[client_id]
    call_log = c.get("call_log", [])

    if not call_log:
        return {"notes": [], "last_contact_note": c.get("last_contact_note", "")}

    if not query:
        return {"notes": call_log[:2], "last_contact_note": c["last_contact_note"]}

    query_tokens = set(query.lower().split())

    def relevance(entry: dict) -> int:
        return len(query_tokens & set(entry["note"].lower().split()))

    ranked = sorted(call_log, key=relevance, reverse=True)
    return {"notes": ranked[:2], "last_contact_note": c["last_contact_note"]}


# ---------------------------------------------------------------------------
# Tool 4: get_product_catalog
# ---------------------------------------------------------------------------

_PRODUCTS = [
    {"id": "P01", "name": "Tax-Advantaged Bond Ladder", "fit": ["Disengaging", "Steady loyalist"], "life_events": ["retirement", "child_education"]},
    {"id": "P02", "name": "Real Estate Diversification Fund", "fit": ["Growth-minded", "New & exploring"], "life_events": ["property_purchase", "inheritance"]},
    {"id": "P03", "name": "ESG Impact Portfolio", "fit": ["Growth-minded", "New & exploring"], "life_events": ["inheritance", "business_sale"]},
    {"id": "P04", "name": "Education Savings Wrapper", "fit": ["Steady loyalist", "Disengaging"], "life_events": ["child_education"]},
    {"id": "P05", "name": "Private Equity Access Fund", "fit": ["Growth-minded"], "life_events": ["inheritance", "business_sale", "property_purchase"]},
    {"id": "P06", "name": "Succession & Legacy Plan", "fit": ["Steady loyalist"], "life_events": ["retirement", "business_sale"]},
]


def get_product_catalog(segment_label: str = "", life_events: list[str] | None = None) -> dict:
    """Return eligible products filtered by segment and/or life events."""
    results = []
    life_events = life_events or []
    for p in _PRODUCTS:
        seg_match = (not segment_label) or (segment_label in p["fit"])
        event_match = (not life_events) or any(e in p["life_events"] for e in life_events)
        if seg_match or event_match:
            results.append({"id": p["id"], "name": p["name"]})
    return {"products": results[:3]}


# ---------------------------------------------------------------------------
# Tool 5: get_market_context / get_market_sentiment
# ---------------------------------------------------------------------------

def get_market_context(topics: list[str] | None = None) -> dict:
    """Return 1-2 timely market notes relevant to the client's exposure.

    Prefers the live/cached feed (loaded into _MARKET_FEED at pipeline start);
    falls back to the curated static text if a sector isn't in the feed.
    """
    topics = topics or []

    live_by_sector: dict[str, str] = {}
    for entry in _MARKET_FEED:  # sorted most-recent-first
        sec = entry["sector"]
        if sec not in live_by_sector:
            live_by_sector[sec] = entry["signal"]

    notes = []
    for t in topics:
        signal = live_by_sector.get(t) or FALLBACK_SIGNAL_TEXT.get(t)
        if signal:
            notes.append({"topic": t, "signal": signal})
        if len(notes) >= 2:
            break
    return {"market_notes": notes}


def get_market_sentiment(topics: list[str] | None = None) -> dict:
    """Return the latest dated sentiment for each of the client's exposures."""
    topics = topics or []
    latest: dict[str, dict] = {}
    for entry in _MARKET_FEED:  # feed is sorted most-recent-first
        sec = entry["sector"]
        if sec in topics and sec not in latest:
            latest[sec] = entry
    return {"signals": list(latest.values())}


# ---------------------------------------------------------------------------
# Tool 6: get_transaction_history
# ---------------------------------------------------------------------------

def get_transaction_history(client_id: str) -> dict:
    """Return the monthly series plus a short summary of recent flows."""
    c = _RAW_CLIENTS[client_id]
    txns = c.get("transactions", [])
    recent = txns[-3:]
    recent_net = sum(t["net_flow"] for t in recent)
    return {
        "transactions": txns,
        "recent_net_flow": recent_net,
        "trend": "outflows" if recent_net < 0 else "inflows",
    }


# ---------------------------------------------------------------------------
# Tool 7: get_digital_behavior_trend
# ---------------------------------------------------------------------------

def get_digital_behavior_trend(client_id: str) -> dict:
    """Compare the earliest vs latest weeks to describe engagement direction."""
    c = _RAW_CLIENTS[client_id]
    beh = c.get("digital_behavior", [])
    if len(beh) < 2:
        return {"digital_behavior": beh, "direction": "flat", "login_delta": 0}
    first, last = beh[0], beh[-1]
    login_delta = last["logins"] - first["logins"]
    direction = "declining" if login_delta < -1 else ("rising" if login_delta > 1 else "flat")
    return {"digital_behavior": beh, "direction": direction, "login_delta": login_delta}


# ---------------------------------------------------------------------------
# Tool 8: recommend_rebalance (portfolio nudge)
# ---------------------------------------------------------------------------

def recommend_rebalance(client_id: str) -> dict:
    """Deterministic portfolio nudge from exposures, sentiment, and life events."""
    c = _RAW_CLIENTS[client_id]
    exposures = c.get("market_exposure", [])
    life_events = c.get("life_events", [])
    sentiment = get_market_sentiment(exposures)["signals"]

    bullish = [s["sector"] for s in sentiment if s["sentiment"] == "bullish"]
    bearish = [s["sector"] for s in sentiment if s["sentiment"] == "bearish"]

    def pretty(secs: list[str]) -> str:
        return ", ".join(s.replace("_", " ") for s in secs)

    if "inheritance" in life_events or "business_sale" in life_events:
        nudge = "New liquidity is a chance to build a diversified core allocation before deploying into higher-conviction sleeves."
    elif bearish and bullish:
        nudge = f"Consider trimming {pretty(bearish[:1])} and rotating toward {pretty(bullish[:1])}, which screens more favourably right now."
    elif bearish:
        nudge = f"{pretty(bearish[:1]).capitalize()} exposure faces headwinds; a defensive tilt may be worth a conversation."
    elif bullish:
        nudge = f"{pretty(bullish[:1]).capitalize()} momentum supports adding on any near-term pullback."
    else:
        nudge = "Allocation looks balanced; a periodic rebalance keeps risk aligned with the plan."

    return {"nudge": nudge, "bullish": bullish, "bearish": bearish}


# ---------------------------------------------------------------------------
# Tool registry (for agents to look up)
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "get_client_segment": get_client_segment,
    "compute_propensity": compute_propensity,
    "get_call_context": get_call_context,
    "get_product_catalog": get_product_catalog,
    "get_market_context": get_market_context,
    "get_market_sentiment": get_market_sentiment,
    "get_transaction_history": get_transaction_history,
    "get_digital_behavior_trend": get_digital_behavior_trend,
    "recommend_rebalance": recommend_rebalance,
}

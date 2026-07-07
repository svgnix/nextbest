"""Multi-agent orchestrator (LangGraph).

An Orchestrator agent reads a client's signals, decides which specialist
agents to consult, and each specialist appends to a shared reasoning trace
tagged with its own name. The Outreach agent then drafts and self-critiques
(reflection loop) before the orchestrator commits the recommendation.

Agents:
  - orchestrator   : plans the route + synthesises the framing
  - segmentation   : behavioural cluster + lookalikes
  - propensity     : attrition / upsell / revenue + engagement + flows
  - market         : dated market sentiment vs the client's exposures
  - portfolio      : rebalance nudge + eligible product
  - outreach       : draft -> critique reflection loop
"""

from __future__ import annotations

import re
import time

from langgraph.graph import END, StateGraph

from backend import telemetry
from backend.agents.state import AgentState
from backend.llm import chat, extract_json
from backend.prompts import CRITIQUE_SYSTEM, DRAFT_SYSTEM, PLANNER_SYSTEM
from backend.tools import (
    get_call_context,
    get_client_segment,
    get_digital_behavior_trend,
    get_market_sentiment,
    get_product_catalog,
    get_transaction_history,
    recommend_rebalance,
)

# Deterministic guardrail: a client-facing draft must never leak an internal
# metric or system term, even if the LLM critique is lenient.
_METRIC_LEAK_PATTERNS = [
    r"\d+\s?%",
    r"\battrition\b",
    r"\bupsell\b",
    r"\bpropensity\b",
    r"\bchurn\b",
    r"\brisk score\b",
    r"\bconfidence score\b",
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _local_metric_leak(draft: str) -> str | None:
    low = draft.lower()
    for pattern in _METRIC_LEAK_PATTERNS:
        match = re.search(pattern, low)
        if match:
            return match.group(0)
    return None


def _step(agent: str, tool: str, finding: str) -> dict:
    return {"agent": agent, "tool": tool, "finding": finding, "ts_ms": _now_ms()}


# ---------------------------------------------------------------------------
# Orchestrator: plan the route
# ---------------------------------------------------------------------------

def _route_for_framing(framing: str) -> list[str]:
    if framing == "re-engagement":
        return ["segmentation", "propensity", "market", "outreach"]
    if framing == "opportunity":
        return ["segmentation", "propensity", "portfolio", "market", "outreach"]
    return ["segmentation", "propensity", "outreach"]


def _orchestrator_plan(state: AgentState) -> dict:
    client = state["client"]
    prop = state["propensity"]

    context = (
        f"Client: {client['name']} (ID: {client['client_id']})\n"
        f"Attrition risk: {prop['attrition_risk']}%\n"
        f"Upsell readiness: {prop['upsell_ready']}%\n"
        f"Life events: {client['life_events']}\n"
        f"Days since last contact: {client['days_since_last_contact']}\n"
        f"Segment: {client.get('segment', {}).get('label', 'unknown')}\n"
    )

    response = chat(
        messages=[{"role": "user", "content": context + "\nPlan the tool calls for this client."}],
        system=PLANNER_SYSTEM,
        temperature=0.2,
        force_json=True,
        purpose="plan",
    )
    plan = extract_json(response.get("text", "")) or {}

    framing = plan.get("framing")
    if framing not in {"re-engagement", "opportunity", "check-in"}:
        att, ups = prop["attrition_risk"], prop["upsell_ready"]
        framing = "re-engagement" if (att >= 50 and att >= ups) else ("opportunity" if ups >= 50 else "check-in")

    consulted = _route_for_framing(framing)
    reasoning = plan.get("reasoning", "Routing based on the strongest signal.")

    finding = (
        f"Framing '{framing}'. Consulting {len(consulted) - 1} specialists: "
        f"{', '.join(a for a in consulted if a != 'outreach')}."
    )
    return {
        "framing": framing,
        "consulted": consulted,
        "plan_reasoning": reasoning,
        "tool_results": {},
        "reasoning_trace": [_step("orchestrator", "plan", finding)],
    }


# ---------------------------------------------------------------------------
# Segmentation agent
# ---------------------------------------------------------------------------

def _segmentation_agent(state: AgentState) -> dict:
    client = state["client"]
    result = get_client_segment(client["client_id"])
    seg = result.get("segment", {})
    finding = (
        f"Behavioural cluster '{seg.get('label', '?')}' "
        f"with {len(result.get('lookalikes', []))} look-alike clients."
    )
    tr = dict(state.get("tool_results", {}))
    tr["get_client_segment"] = result
    return {"tool_results": tr, "reasoning_trace": [_step("segmentation", "get_client_segment", finding)]}


# ---------------------------------------------------------------------------
# Propensity / Risk agent
# ---------------------------------------------------------------------------

def _propensity_agent(state: AgentState) -> dict:
    client = state["client"]
    prop = state["propensity"]

    rules = prop.get("attrition_rules_fired", []) + prop.get("upsell_rules_fired", [])
    top_rule = rules[0].split("(")[0].strip() if rules else "no strong signals"

    beh = get_digital_behavior_trend(client["client_id"])
    txn = get_transaction_history(client["client_id"])

    finding = (
        f"Attrition {prop['attrition_risk']}%, upsell {prop['upsell_ready']}% — "
        f"top driver: {top_rule}. Digital engagement {beh['direction']}, "
        f"net flows trending {txn['trend']}."
    )
    tr = dict(state.get("tool_results", {}))
    tr["digital_behavior"] = beh
    tr["transactions"] = txn
    return {"tool_results": tr, "reasoning_trace": [_step("propensity", "compute_propensity", finding)]}


# ---------------------------------------------------------------------------
# Market-signal agent
# ---------------------------------------------------------------------------

def _market_agent(state: AgentState) -> dict:
    if "market" not in state.get("consulted", []):
        return {}
    client = state["client"]
    signals = get_market_sentiment(client.get("market_exposure", [])).get("signals", [])
    if not signals:
        return {"reasoning_trace": [_step("market", "get_market_sentiment", "No timely signal for this book of exposures.")]}

    top = signals[0]
    insight = top["signal"]
    finding = f"{top['sector'].replace('_', ' ').title()} looks {top['sentiment']}: {insight[:70]}"
    tr = dict(state.get("tool_results", {}))
    tr["market"] = {"signals": signals}
    return {
        "market_insight": insight,
        "tool_results": tr,
        "reasoning_trace": [_step("market", "get_market_sentiment", finding)],
    }


# ---------------------------------------------------------------------------
# Portfolio-nudge agent
# ---------------------------------------------------------------------------

def _portfolio_agent(state: AgentState) -> dict:
    if "portfolio" not in state.get("consulted", []):
        return {}
    client = state["client"]
    rebalance = recommend_rebalance(client["client_id"])
    catalog = get_product_catalog(
        segment_label=client.get("segment", {}).get("label", ""),
        life_events=client.get("life_events"),
    )
    products = catalog.get("products", [])
    product = products[0]["name"] if products else None

    finding = f"Nudge: {rebalance['nudge'][:80]}"
    if product:
        finding += f" Eligible: {product}."

    tr = dict(state.get("tool_results", {}))
    tr["portfolio"] = {"rebalance": rebalance, "products": products}
    return {
        "portfolio_nudge": rebalance["nudge"],
        "recommended_product": product or "",
        "tool_results": tr,
        "reasoning_trace": [_step("portfolio", "recommend_rebalance", finding)],
    }


# ---------------------------------------------------------------------------
# Outreach agent: draft
# ---------------------------------------------------------------------------

def _outreach_draft(state: AgentState) -> dict:
    client = state["client"]
    framing = state.get("framing", "check-in")
    critique_feedback = state.get("critique_feedback", "")

    call_ctx = get_call_context(client["client_id"], query=" ".join(client.get("life_events", [])))
    tr = dict(state.get("tool_results", {}))
    tr["get_call_context"] = call_ctx

    parts = [
        f"Client name: {client['name']}",
        f"Framing: {framing}",
        f"Life events: {', '.join(client.get('life_events', [])) or 'none'}",
    ]
    if call_ctx.get("notes"):
        parts.append(f"Recent call note: \"{call_ctx['notes'][0]['note']}\"")
    if state.get("market_insight"):
        parts.append(f"Market context: {state['market_insight']}")
    if state.get("portfolio_nudge"):
        parts.append(f"Portfolio idea: {state['portfolio_nudge']}")
    if state.get("recommended_product"):
        parts.append(f"Relevant products: {state['recommended_product']}")
    if critique_feedback:
        parts.append(f"PREVIOUS DRAFT FAILED CRITIQUE. Fix this: {critique_feedback}")

    user_msg = "\n".join(parts) + "\n\nWrite the outreach message now."
    response = chat(
        messages=[{"role": "user", "content": user_msg}],
        system=DRAFT_SYSTEM,
        temperature=0.6,
        purpose="draft",
    )
    draft = response["text"].strip()

    return {
        "draft_message": draft,
        "tool_results": tr,
        "reasoning_trace": [_step("outreach", "draft_message", f"Drafted {framing} opener ({len(draft.split())} words).")],
    }


# ---------------------------------------------------------------------------
# Outreach agent: critique (reflection)
# ---------------------------------------------------------------------------

def _outreach_critique(state: AgentState) -> dict:
    draft = state.get("draft_message", "")
    client = state["client"]

    user_msg = (
        f"Client name: {client['name']}\n"
        f"Draft message:\n\"\"\"\n{draft}\n\"\"\"\n\n"
        "Score this draft against the checks."
    )
    response = chat(
        messages=[{"role": "user", "content": user_msg}],
        system=CRITIQUE_SYSTEM,
        temperature=0.1,
        force_json=True,
        purpose="critique",
    )
    critique = extract_json(response.get("text", ""))
    if not isinstance(critique, dict):
        critique = {"passed": True, "feedback": ""}

    passed = bool(critique.get("passed", True))
    feedback = critique.get("feedback", "")

    leak = _local_metric_leak(draft)
    if leak:
        passed = False
        telemetry.mark_metric_leak()
        if not feedback:
            feedback = (
                f"Draft leaks an internal metric/term ('{leak}'). Remove all numbers, "
                "percentages, and risk/score language — keep it human."
            )

    status = "passed" if passed else f"failed — {feedback}"
    return {
        "draft_passed_critique": passed,
        "critique_feedback": feedback,
        "critique_attempts": state.get("critique_attempts", 0) + 1,
        "reasoning_trace": [_step("outreach", "critique", f"Quality gate {status}.")],
    }


def _should_redraft(state: AgentState) -> str:
    if state.get("draft_passed_critique", False):
        return "end"
    if state.get("critique_attempts", 0) >= 3:
        return "end"
    return "redraft"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def _timed(name: str, fn):
    """Wrap a node so its wall-time is recorded to the active run telemetry."""

    def wrapped(state: AgentState) -> dict:
        t0 = time.perf_counter()
        try:
            return fn(state)
        finally:
            telemetry.record_node(name, (time.perf_counter() - t0) * 1000)

    return wrapped


def build_agent_graph():
    graph = StateGraph(AgentState)

    graph.add_node("plan", _timed("plan", _orchestrator_plan))
    graph.add_node("segmentation", _timed("segmentation", _segmentation_agent))
    graph.add_node("propensity", _timed("propensity", _propensity_agent))
    graph.add_node("market", _timed("market", _market_agent))
    graph.add_node("portfolio", _timed("portfolio", _portfolio_agent))
    graph.add_node("draft", _timed("draft", _outreach_draft))
    graph.add_node("critique", _timed("critique", _outreach_critique))

    graph.set_entry_point("plan")
    graph.add_edge("plan", "segmentation")
    graph.add_edge("segmentation", "propensity")
    graph.add_edge("propensity", "market")
    graph.add_edge("market", "portfolio")
    graph.add_edge("portfolio", "draft")
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges("critique", _should_redraft, {"end": END, "redraft": "draft"})

    return graph.compile()


_GRAPH = None


def run_orchestrator_for_client(client: dict, propensity: dict) -> dict:
    """Run the full multi-agent loop for one client.

    Returns the final state with an extra `telemetry` key summarising the run
    (latency, per-node timing, token usage, live/mock mode, guard hits).
    """
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_agent_graph()

    initial: AgentState = {
        "client": client,
        "propensity": propensity,
        "consulted": [],
        "framing": "",
        "plan_reasoning": "",
        "tool_results": {},
        "market_insight": "",
        "portfolio_nudge": "",
        "recommended_product": "",
        "draft_message": "",
        "draft_passed_critique": False,
        "critique_feedback": "",
        "critique_attempts": 0,
        "reasoning_trace": [],
    }

    tel = telemetry.start()
    try:
        final = _GRAPH.invoke(initial)
    finally:
        telemetry.stop()
    final["telemetry"] = tel.summary()
    return final

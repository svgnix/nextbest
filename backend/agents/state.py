"""Shared blackboard state for the multi-agent graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    # Inputs
    client: dict
    propensity: dict

    # Orchestrator decisions
    consulted: list[str]
    framing: str
    plan_reasoning: str

    # Specialist outputs
    tool_results: dict[str, Any]
    market_insight: str
    portfolio_nudge: str
    recommended_product: str

    # Outreach loop
    draft_message: str
    draft_passed_critique: bool
    critique_feedback: str
    critique_attempts: int

    # The collaborative record every agent appends to (reducer merges lists)
    reasoning_trace: Annotated[list[dict], operator.add]

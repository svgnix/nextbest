"""Per-run agent telemetry — lightweight, in-process observability.

The multi-agent graph runs synchronously per client. This module collects a
single run's signals (LLM calls with token usage + latency, per-node timing,
compliance guard hits) into a context-local accumulator so nothing has to be
threaded through the LangGraph state. `llm.chat` records each call; the
orchestrator records node timings; `run_pipeline` reads the summary and
persists it as an AgentRun row.

Lives at the package root (not under agents/) so importing it never triggers
the agents package __init__ — that would create an llm <-> agents import cycle.
Kept deliberately dependency-free (stdlib only) so it never becomes a second
framework — it is just a struct + a contextvar.
"""

from __future__ import annotations

import contextvars
import time
from typing import Optional

_current: contextvars.ContextVar[Optional["RunTelemetry"]] = contextvars.ContextVar(
    "nb_run_telemetry", default=None
)


class RunTelemetry:
    """Accumulates one client's agent run."""

    def __init__(self) -> None:
        self.llm_calls: list[dict] = []
        self.node_timings: dict[str, float] = {}  # node name -> cumulative ms
        self.metric_leak_caught: bool = False
        self._t0 = time.perf_counter()

    # -- recording -------------------------------------------------------
    def add_llm(
        self,
        purpose: str,
        model: str,
        mode: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        self.llm_calls.append({
            "purpose": purpose,
            "model": model,
            "mode": mode,
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "latency_ms": round(latency_ms, 1),
        })

    def add_node(self, node: str, ms: float) -> None:
        self.node_timings[node] = round(self.node_timings.get(node, 0.0) + ms, 1)

    # -- derived ---------------------------------------------------------
    @property
    def prompt_tokens(self) -> int:
        return sum(c["prompt_tokens"] for c in self.llm_calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c["completion_tokens"] for c in self.llm_calls)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def mode(self) -> str:
        """A run is 'live' if any call hit a real provider, else 'mock'."""
        if not self.llm_calls:
            return "mock"
        return "live" if any(c["mode"] == "live" for c in self.llm_calls) else "mock"

    def summary(self) -> dict:
        return {
            "total_ms": round((time.perf_counter() - self._t0) * 1000, 1),
            "node_timings": dict(self.node_timings),
            "llm_calls": len(self.llm_calls),
            "llm_call_detail": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "mode": self.mode,
            "metric_leak_caught": self.metric_leak_caught,
        }


# ---------------------------------------------------------------------------
# Module API
# ---------------------------------------------------------------------------

def start() -> RunTelemetry:
    """Begin a fresh run; installs it as the current collector."""
    tel = RunTelemetry()
    _current.set(tel)
    return tel


def stop() -> None:
    """Clear the current collector."""
    _current.set(None)


def current() -> Optional[RunTelemetry]:
    return _current.get()


def record_llm(**kwargs) -> None:
    """Called by llm.chat for every completion; no-ops outside a run."""
    tel = _current.get()
    if tel is not None:
        tel.add_llm(**kwargs)


def record_node(node: str, ms: float) -> None:
    tel = _current.get()
    if tel is not None:
        tel.add_node(node, ms)


def mark_metric_leak() -> None:
    tel = _current.get()
    if tel is not None:
        tel.metric_leak_caught = True

"""Agent evaluation harness.

Scores the quality of the multi-agent pipeline over the already-scored book:

  Deterministic (always, no LLM):
    - draft coverage, critique pass rate, metric-leak rate
    - average redrafts (reflection-loop cost)
    - specialist coverage (did each consulted agent actually contribute a finding?)
    - confidence distribution, latency (p50/p95), token spend

  LLM-as-judge (only when an API key is configured):
    - an independent model scores each draft 1-5 on personalization, tone,
      actionability, and groundedness, plus a compliance flag.

Run it:  python -m backend.eval           (writes data/eval_report.json)
The API serves the saved report; the pipeline must have run first.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone

from backend import llm
from backend.agents.orchestrator import _local_metric_leak, _route_for_framing
from backend.config import DATA_DIR, TOP_N_DRAFT
from backend.db import AgentRun, Client, ScoredAction, SessionLocal, init_db
from backend.prompts import JUDGE_SYSTEM

REPORT_PATH = DATA_DIR / "eval_report.json"


# ---------------------------------------------------------------------------
# Small stats helpers
# ---------------------------------------------------------------------------

def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return round(s[int(k)], 1)
    return round(s[lo] * (hi - k) + s[hi] * (k - lo), 1)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


# ---------------------------------------------------------------------------
# Deterministic metrics
# ---------------------------------------------------------------------------

def _deterministic(db) -> dict:
    drafted = (
        db.query(ScoredAction)
        .filter(ScoredAction.draft_message != "")
        .order_by(ScoredAction.priority_rank)
        .all()
    )
    runs = db.query(AgentRun).all()

    n = len(drafted)
    passed = sum(1 for a in drafted if a.draft_passed_critique)
    leaks = sum(1 for a in drafted if _local_metric_leak(a.draft_message or ""))

    # Specialist coverage: of the specialists the orchestrator planned to consult,
    # how many actually emitted a finding in the reasoning trace?
    coverage_ratios = []
    for a in drafted:
        expected = [s for s in _route_for_framing(a.framing or "check-in") if s != "outreach"]
        agents_seen = {step.get("agent") for step in (a.reasoning_trace or [])}
        if expected:
            coverage_ratios.append(sum(1 for e in expected if e in agents_seen) / len(expected))

    confidences = [a.confidence for a in drafted if a.confidence is not None]
    conf_buckets = Counter()
    for c in confidences:
        band = "90-100" if c >= 90 else "80-89" if c >= 80 else "70-79" if c >= 70 else "<70"
        conf_buckets[band] += 1

    framing_dist = Counter(a.framing or "check-in" for a in drafted)

    latencies = [r.total_ms for r in runs if r.total_ms]
    redrafts = [r.redrafts for r in runs]
    tokens = [r.total_tokens for r in runs]

    return {
        "top_n": TOP_N_DRAFT,
        "runs": len(runs),
        "drafted": n,
        "draft_coverage": round(n / TOP_N_DRAFT, 3) if TOP_N_DRAFT else 0.0,
        "critique_pass_rate": round(passed / n, 3) if n else 0.0,
        "metric_leak_rate": round(leaks / n, 3) if n else 0.0,
        "avg_redrafts": _avg(redrafts),
        "specialist_coverage": _avg(coverage_ratios),
        "framing_distribution": [
            {"label": k, "count": v} for k, v in framing_dist.most_common()
        ],
        "confidence": {
            "avg": _avg(confidences),
            "min": min(confidences) if confidences else 0,
            "max": max(confidences) if confidences else 0,
            "distribution": [
                {"label": b, "count": conf_buckets.get(b, 0)}
                for b in ["<70", "70-79", "80-89", "90-100"]
            ],
        },
        "latency_ms": {
            "avg": _avg(latencies),
            "p50": _pct(latencies, 0.5),
            "p95": _pct(latencies, 0.95),
        },
        "tokens": {
            "total": sum(tokens),
            "avg_per_run": _avg(tokens),
            "prompt": sum(r.prompt_tokens for r in runs),
            "completion": sum(r.completion_tokens for r in runs),
        },
    }


# ---------------------------------------------------------------------------
# LLM-as-judge (optional)
# ---------------------------------------------------------------------------

_DIMENSIONS = ["personalization", "tone", "actionability", "groundedness"]


def _judge_one(action: ScoredAction, client: Client | None) -> dict | None:
    life_events = ", ".join(client.life_events or []) if client else ""
    note = (client.last_contact_note if client else "") or ""
    context = (
        f"Client name: {action.name}\n"
        f"Framing: {action.framing}\n"
        f"Life events: {life_events or 'none'}\n"
        f"Recent call note: {note or 'none'}\n"
        f"Market context available: {action.market_insight or 'none'}\n\n"
        f"Draft message:\n\"\"\"\n{action.draft_message}\n\"\"\"\n\n"
        "Score this draft."
    )
    resp = llm.chat(
        messages=[{"role": "user", "content": context}],
        system=JUDGE_SYSTEM,
        temperature=0.0,
        force_json=True,
        purpose="judge",
    )
    scores = llm.extract_json(resp.get("text", ""))
    if not isinstance(scores, dict):
        return None

    clean = {}
    for d in _DIMENSIONS:
        try:
            clean[d] = max(1, min(5, int(scores.get(d, 0))))
        except (TypeError, ValueError):
            clean[d] = 0
    clean["overall"] = round(sum(clean[d] for d in _DIMENSIONS) / len(_DIMENSIONS), 2)
    clean["compliant"] = bool(scores.get("compliant", True))
    clean["comment"] = str(scores.get("comment", ""))[:200]
    return clean


def _judge(db) -> dict:
    drafted = (
        db.query(ScoredAction)
        .filter(ScoredAction.draft_message != "")
        .order_by(ScoredAction.priority_rank)
        .all()
    )

    per_client = []
    for a in drafted:
        client = db.get(Client, a.client_id)
        try:
            scored = _judge_one(a, client)
        except Exception as e:  # noqa: BLE001 — one bad call shouldn't sink the report
            print(f"    Judge error for {a.name}: {e}")
            scored = None
        if not scored:
            continue
        per_client.append({
            "client_id": a.client_id,
            "name": a.name,
            "framing": a.framing,
            **scored,
        })

    if not per_client:
        return {"scored": 0, "averages": {}, "compliant_rate": 0.0, "per_client": []}

    averages = {
        d: _avg([p[d] for p in per_client]) for d in _DIMENSIONS + ["overall"]
    }
    compliant_rate = round(
        sum(1 for p in per_client if p["compliant"]) / len(per_client), 3
    )
    return {
        "scored": len(per_client),
        "averages": averages,
        "compliant_rate": compliant_rate,
        "per_client": per_client,
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def compute_report(db, include_judge: bool = False) -> dict:
    """Build the eval report from the DB. Does not write to disk."""
    runs = db.query(AgentRun).all()
    modes = {r.mode for r in runs}
    mode = "none" if not modes else ("mixed" if len(modes) > 1 else next(iter(modes)))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "deterministic": _deterministic(db),
        "judge": None,
    }
    if include_judge:
        report["judge"] = _judge(db)
    return report


def run_eval() -> dict:
    init_db()
    db = SessionLocal()
    try:
        if not db.query(ScoredAction).filter(ScoredAction.draft_message != "").count():
            print("No drafted actions. Run `python -m backend.run_pipeline` first.")
            return {}

        use_judge = llm.has_api_key()
        print("Computing deterministic metrics...")
        if use_judge:
            print("LLM key found — running LLM-as-judge over the drafts (this uses tokens)...")
        else:
            print("No LLM key — skipping LLM-as-judge (deterministic metrics only).")

        report = compute_report(db, include_judge=use_judge)
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

        det = report["deterministic"]
        print(
            f"\nDone. {det['drafted']} drafts | "
            f"pass rate {det['critique_pass_rate']:.0%} | "
            f"leak rate {det['metric_leak_rate']:.0%} | "
            f"avg redrafts {det['avg_redrafts']} | "
            f"p95 latency {det['latency_ms']['p95']}ms"
        )
        if report["judge"]:
            print(f"Judge overall: {report['judge']['averages'].get('overall')}/5 "
                  f"({report['judge']['scored']} drafts)")
        print(f"Report written to {REPORT_PATH.name}.")
        return report
    finally:
        db.close()


if __name__ == "__main__":
    run_eval()

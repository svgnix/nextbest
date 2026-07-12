# CLAUDE.md — NextBest

> Read this first, then `SPEC.md` (what to build) and `DESIGN.md` (how the frontend must look).
> This is a 5-day hackathon MVP for the **PwC Industry Innovation Hackathon 2026** (Team Compass).
> The theme is **Agentic AI**. The single most important thing: NextBest must read as a real agent that
> *reasons its way to a decision*, not a scripted pipeline that fills a template. Keep that framing central.

> **Status — the build has evolved beyond this original plan; `README.md` is the source of truth for the
> system as built.** The core intent is unchanged, but concretely: ~300 clients across 3 advisors (not 50);
> **6** data sources; persistence in **SQLite** via SQLAlchemy; a **FastAPI** service instead of static
> JSON; the agent is a **multi-agent LangGraph orchestrator** (`backend/agents/orchestrator.py`, not a flat
> `agent.py`) with **conditional edges** that branch on the plan; plus a **RAG book copilot**, an
> **eval/observability** harness, and a trained **XGBoost** propensity model (optional drop-in for the rule
> engine). The nine-page advisor suite is described in `README.md`.

---

## What NextBest is

An AI "next best action" layer for bank/wealth **relationship managers (RMs)**. An RM carries 200–300
high-net-worth clients and can't proactively reach them all. Every morning NextBest tells the RM **who to
contact, why, and what to open with** — a ranked daily dispatch, each item carrying a confidence score, a
plain-language rationale, and an editable draft message the RM can send, edit, or skip. A human is always
in the loop.

The differentiator (straight from the pitch deck): *most tools stop at insight on a dashboard; NextBest
closes the loop to a specific recommended action.* The agent is how that loop closes.

## Architecture in one line

```
Synthetic data (6 sources) → SQLite → engines (segmentation + propensity)
  → multi-agent orchestrator (plan → specialists → draft ⇄ critique) → FastAPI → React SPA
```

The three "engines" from the pitch are preserved but are now **tools the agent calls**, not a fixed
pipeline: (1) behavioral **segmentation**, (2) attrition/upsell **propensity**, (3) **GenAI** outreach
grounded on call-log retrieval. The orchestrator's plan drives conditional edges, so the path taken
changes per client. Full behavioural detail in `SPEC.md`; full system detail in `README.md`.

## Stack (do not substitute without a reason)

- **Backend / agent:** Python 3.11+. `pydantic` (schemas), `scikit-learn` (segmentation), `langgraph`
  (multi-agent graph), `SQLAlchemy` + **SQLite** (persistence), `FastAPI` + `uvicorn` (API).
  `xgboost` is **implemented** as a learned drop-in for the propensity rules (`backend/propensity_model.py`,
  off by default — see README §Propensity).
- **LLM:** the user's own API key, read from env — provider-agnostic wrapper in `backend/llm.py`.
  Provider Anthropic or OpenAI-compatible (PwC GenAI proxy). Deterministic **mock mode** when no key.
  **Never hardcode a key. Never commit `.env`.** Do **not** use AWS Bedrock — calling the API directly.
- **Frontend:** **React + Vite + TypeScript**, hand-written CSS (CSS Modules or plain CSS with tokens).
  `framer-motion` for the small amount of motion in `DESIGN.md`. **No component library** (no MUI,
  Chakra, Ant, default shadcn) — a kit will make it look generic, which the brief explicitly forbids.
- **Data contract:** the frontend calls the **FastAPI** service (`/api/*`, proxied by Vite in dev); the
  scored book lives in SQLite. `run_pipeline.py` also writes `backend/data/scored_clients.json` as a
  debug snapshot. Keep `schemas.py` and `frontend/src/types.ts` in sync — that's the contract.

## Repo layout (as built)

```
nextbest/
├── CLAUDE.md            # this file
├── SPEC.md              # functional + technical spec  (source of truth for behavior)
├── DESIGN.md            # frontend visual direction     (source of truth for look/feel)
├── README.md            # quickstart + full system reference (source of truth as built)
├── .github/workflows/   # CI — backend pytest + frontend build
├── backend/
│   ├── schemas.py          # Client, ReasoningStep, NextBestAction, API shapes (pydantic)
│   ├── config.py           # seed, sizes, DB path, flags (USE_XGB_PROPENSITY, ...)
│   ├── generate_data.py    # Component 1 — ~300 clients, 6 data sources, hero clients
│   ├── db.py / seed.py     # SQLAlchemy models + load JSON → SQLite (nextbest.db)
│   ├── segment.py          # Engine 1 — behavioral clustering (KMeans) + look-alikes
│   ├── propensity.py       # Engine 2 — attrition + upsell + revenue-at-stake (rules)
│   ├── propensity_model.py # Engine 2 (learned) — XGBoost drop-in trained on the rule policy
│   ├── tools.py            # agent tools (get_client_segment, compute_propensity, ...)
│   ├── llm.py / prompts.py # provider-agnostic chat (+ mock mode) + system prompts
│   ├── telemetry.py        # per-run agent telemetry (latency, tokens, redrafts)
│   ├── agents/             # multi-agent core: orchestrator.py (conditional graph) + state.py
│   ├── rag/                # Book Assistant: corpus, vector store, index, chat
│   ├── api/                # FastAPI service (main.py + serializers.py)
│   ├── eval.py             # evaluation harness (deterministic metrics + LLM-as-judge)
│   ├── run_pipeline.py     # engines → agents → DB (+ scored_clients.json snapshot)
│   ├── tests/              # pytest: engines, model, pipeline/guardrail
│   ├── requirements.txt
│   └── .env.example
└── frontend/            # Vite React TS SPA (9 pages) — implement strictly against DESIGN.md
    └── src/{api,pages,layout,components,lib,styles}
```

## Build order (phased — commit after each phase)

1. **Scaffold + schemas.** Repo layout, `requirements.txt`, `.env.example`, `schemas.py`. Nail the
   `NextBestAction` schema first — it is the contract every later stage and the whole UI depend on.
2. **Data generator.** `generate_data.py` → `clients.json`. All five data sources; 4–5 hand-designed
   "hero" clients so the ranked demo tells a clear story (see SPEC §Hero clients). Everything downstream
   is only as good as this.
3. **Engines.** `segment.py` (clustering) + `propensity.py` (attrition, upsell, revenue_impact). Pure,
   deterministic, unit-testable. No LLM here.
4. **Agent core.** `llm.py`, `tools.py`, `agent.py`. Tool-calling loop + reflection (draft → critique →
   regenerate on fail). `run_pipeline.py` writes `scored_clients.json` with full reasoning traces.
   Draft messages only for the top ~10 by priority to save time/tokens.
5. **Frontend.** Build the dashboard exactly to `DESIGN.md`. Read the JSON, render the ranked feed, the
   reasoning trace, and the draft editor. This is what the audience sees — spend real effort here.
6. **Polish + demo.** Loading/empty/error states with voice, hero-client walkthrough, keyboard focus,
   reduced-motion. Rehearse the sub-60-second story.

## Conventions

- Backend is deterministic where it can be: seed all RNG (`SEED = 42`) so the demo is reproducible.
- One JSON is the source of truth for the UI. If a field isn't in `scored_clients.json`, the UI can't
  show it — keep `schemas.py` and the UI's TS types in sync.
- Type the frontend end-to-end. Mirror the Pydantic schema as a TS `type` in `frontend/src/types.ts`.
- Buttons use active voice and keep their name through the flow (`Accept` → toast "Accepted"). See
  DESIGN.md microcopy.
- Keep secrets in `.env`; ship `.env.example` only.

## Guardrails / non-goals

- **Synthetic data only.** No real client data — that's what removes the compliance blocker and is the
  stated MVP scope. Say so in the demo.
- The drafted message must **never mention scores, risk, or internal metrics** — that rule is enforced by
  the critique step (SPEC §Reflection). If a draft leaks a metric, the agent must regenerate.
- Not building: auth, multi-tenant, cloud deployment/scaling, real integrations. Persistence is a single
  local **SQLite** file — no server DB, no migrations. It all runs on a laptop.
- Don't over-engineer the agent into separate services — one LangGraph graph with clear nodes. Don't add a
  second agent framework. Complexity must earn its place.

## What "done" looks like (demo bar)

An RM opens the dashboard in the morning, sees clients ranked by urgency with the most at-risk on top
(retention-first tiering), clicks the top client (Priya Mehta — 80% attrition risk, not contacted in
94 days, ranked #1), sees exactly
*why* she's flagged (the agent's reasoning trace) and *what to say* (the draft), clicks **Accept**, and
the message is ready — the whole thing under 60 seconds and understandable in the first 30 with no
narration. If a viewer who saw the pitch can point at the running app and tick off all three engines
(segmentation, propensity, GenAI) plus the agentic loop, it's done.

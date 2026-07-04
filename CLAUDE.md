# CLAUDE.md — NextBest

> Read this first, then `SPEC.md` (what to build) and `DESIGN.md` (how the frontend must look).
> This is a 5-day hackathon MVP for the **PwC Industry Innovation Hackathon 2026** (Team Compass).
> The theme is **Agentic AI**. The single most important thing: NextBest must read as a real agent that
> *reasons its way to a decision*, not a scripted pipeline that fills a template. Keep that framing central.

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
Synthetic data (5 sources)  →  Agent core (LangGraph)  →  Ranked action feed  →  RM dashboard UI
                                 orchestrates 3 engines
                                 + reflection loop
```

The three "engines" from the pitch are preserved but are now **tools the agent calls**, not a fixed
pipeline: (1) behavioral **segmentation**, (2) attrition/upsell **propensity**, (3) **GenAI** outreach
grounded on call-log retrieval. Full detail in `SPEC.md`.

## Stack (do not substitute without a reason)

- **Backend / agent:** Python 3.11+. `pydantic` (schemas), `scikit-learn` (segmentation), `langgraph`
  (agent graph). `xgboost` optional (see propensity note in SPEC).
- **LLM:** the user's own API key, read from env — provider-agnostic wrapper in `backend/llm.py`.
  Default provider Anthropic; OpenAI supported. **Never hardcode a key. Never commit `.env`.**
  Do **not** use AWS Bedrock — the user is calling their own API directly.
- **Frontend:** **React + Vite + TypeScript**, hand-written CSS (CSS Modules or plain CSS with tokens).
  `framer-motion` for the small amount of motion in `DESIGN.md`. **No component library** (no MUI,
  Chakra, Ant, default shadcn) — a kit will make it look generic, which the brief explicitly forbids.
- **Data contract:** stages communicate via JSON files. The frontend reads
  `backend/data/scored_clients.json`. For the demo, serve it statically (Vite public dir) or via a tiny
  FastAPI endpoint — no real backend scaling needed.

## Repo layout (create this)

```
nextbest/
├── CLAUDE.md            # this file
├── SPEC.md              # functional + technical spec  (source of truth for behavior)
├── DESIGN.md            # frontend visual direction     (source of truth for look/feel)
├── README.md            # quickstart (generate)
├── backend/
│   ├── schemas.py       # Client, Scores, ReasoningStep, NextBestAction  (pydantic)
│   ├── generate_data.py # Component 1 — 50 synthetic clients, 5 data sources, hero clients
│   ├── segment.py       # Engine 1 — behavioral clustering (KMeans), assigns segment
│   ├── propensity.py    # Engine 2 — attrition + upsell scoring, revenue_impact
│   ├── tools.py         # agent tools (get_client_segment, compute_propensity, ...)
│   ├── llm.py           # provider-agnostic chat + tool-calling client (reads env)
│   ├── agent.py         # Engine 3 core — LangGraph: plan → tools → draft → critique loop
│   ├── run_pipeline.py  # runs 1→2→3, writes data/scored_clients.json
│   ├── data/            # clients.json, scored_clients.json
│   ├── requirements.txt
│   └── .env.example     # LLM_PROVIDER=anthropic  ANTHROPIC_API_KEY=...
└── frontend/            # Vite React TS app — implement strictly against DESIGN.md
    ├── src/
    ├── public/scored_clients.json   # symlink/copy of backend output for the demo
    └── package.json
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
- Not building: auth, a database, multi-tenant, deployment, real integrations. It runs on a laptop.
- Don't over-engineer the agent into three separate services — one graph with clear nodes. Don't add a
  second framework. Complexity must earn its place.

## What "done" looks like (demo bar)

An RM opens the dashboard in the morning, sees ~5 clients ranked by urgency with the most at-risk on top,
clicks the top client (e.g. Priya Mehta — 78% attrition risk, not contacted in 94 days), sees exactly
*why* she's flagged (the agent's reasoning trace) and *what to say* (the draft), clicks **Accept**, and
the message is ready — the whole thing under 60 seconds and understandable in the first 30 with no
narration. If a viewer who saw the pitch can point at the running app and tick off all three engines
(segmentation, propensity, GenAI) plus the agentic loop, it's done.

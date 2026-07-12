# NextBest

An AI **"next best action"** personalisation platform for bank/wealth relationship managers (RMs).
Built for the Apex Wealth *"Know Your Wealth"* brief: segment clients beyond AUM, predict attrition and
upsell, and give advisors a tool they'll actually use — a persistent, multi-page workspace driven by a
**multi-agent** system that shows its reasoning and closes the loop from insight to a ready-to-send draft.

> An RM carries 200–300 high-net-worth clients and can't proactively reach them all. Every morning
> NextBest tells the RM **who to contact, why, and what to open with** — a ranked daily dispatch, each
> item carrying a confidence score, a plain-language rationale, and an editable draft the RM can send,
> edit, or skip. A human is always in the loop.

**The differentiator:** most tools stop at insight on a dashboard; NextBest closes the loop to a
specific recommended action — and the *agent* is how that loop closes.

Architecture in one line:

```
Synthetic data (6 sources) → SQLite → engines (segmentation + propensity)
  → multi-agent orchestrator (plan → specialists → draft → critique) → FastAPI → React SPA
```

---

## Table of contents

- [What NextBest does](#what-nextbest-does)
- [Tech stack](#tech-stack)
- [Backend architecture](#backend-architecture)
- [Frontend UI flow](#frontend-ui-flow)
- [The multi-agent system](#the-multi-agent-system)
- [The pages (advisor suite)](#the-pages-advisor-suite)
- [Evaluation & observability](#evaluation--observability)
- [Setup guide](#setup-guide)
- [Regenerating data / re-scoring](#regenerating-data--re-scoring)
- [Running the tests](#running-the-tests)
- [Verifying the agent is using the LLM](#verifying-the-agent-is-using-the-llm)
- [Troubleshooting](#troubleshooting)
- [Repo layout](#repo-layout)

---

## What NextBest does

1. **Segments the whole book beyond AUM** — behavioural KMeans clustering (engagement, flows, tenure,
   life events) puts every client into one of four segments with look-alike neighbours.
2. **Predicts attrition & upsell** — a transparent, rule-based propensity engine scores every client for
   churn risk, upsell readiness, and revenue impact, and lists exactly which rules fired. A pair of
   **XGBoost** models trained on the same feature interface can be swapped in (`USE_XGB_PROPENSITY=1`)
   to demonstrate the learned drop-in, with feature importances exposed for a data-driven view.
3. **Reasons its way to an action** — a LangGraph multi-agent orchestrator consults specialist agents,
   grounds an outreach draft on the client's call history and market signals, and self-critiques it for
   compliance before committing.
4. **Closes the loop** — the RM sees a ranked morning feed and can **Accept / Edit / Skip** each draft;
   every action persists to the database.
5. **Answers questions about the book** — a retrieval-grounded copilot cites its sources from call notes,
   life events, market signals, and the agent's own rationale.
6. **Evaluates and observes itself** — every agent run is instrumented (latency, tokens, redrafts,
   compliance guard hits) and an evaluation harness grades output quality (deterministic checks plus an
   optional LLM-as-judge), all surfaced on an in-app dashboard.

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent core | Python 3.11+, **LangGraph** (multi-agent graph) |
| ML engines | **scikit-learn** (KMeans segmentation, nearest-neighbours look-alikes) + optional **XGBoost** propensity models (learned drop-in for the rule engine) |
| Schemas | **pydantic** (typed contracts shared across every stage) |
| Persistence | **SQLAlchemy** + **SQLite** (one local DB file) |
| LLM | Provider-agnostic wrapper (PwC GenAI Shared Service / OpenAI / Anthropic / any OpenAI-compatible gateway) with a deterministic **mock mode** |
| Retrieval (copilot) | Dense embeddings when a key is present, deterministic `HashingVectorizer` fallback otherwise |
| Eval & observability | In-repo telemetry collector + evaluation harness (deterministic metrics + optional LLM-as-judge); no external tracing service |
| API | **FastAPI** + Uvicorn |
| Frontend | **React + Vite + TypeScript**, `react-router`, hand-built CSS + SVG charts (no component library) |

---

## Backend architecture

The backend is a linear, reproducible pipeline (deterministic engines) that feeds an agentic loop
(the LLM-driven orchestrator), with a FastAPI layer serving the React app from one SQLite database.

```mermaid
flowchart TB
    subgraph DATA["1 · Data layer (seeded, reproducible)"]
        GEN["generate_data.py<br/>6 synthetic sources:<br/>profiles · transactions · call logs<br/>life events · market signals · digital behaviour"]
        SEED["seed.py<br/>load JSON → DB"]
        DB[("SQLite<br/>nextbest.db<br/>advisors · clients · market_signals<br/>scored_actions · advisor_actions")]
        GEN --> SEED --> DB
    end

    subgraph PIPE["2 · run_pipeline.py — scoring pipeline"]
        SEG["Engine 1 · segment.py<br/>KMeans k=4 + look-alikes"]
        PROP["Engine 2 · propensity.py<br/>attrition · upsell · revenue impact"]
        RANK["classify + rank<br/>URGENT / OPPORTUNITY / WATCHLIST<br/>blended priority score"]
        SEG --> PROP --> RANK
    end

    subgraph AGENT["3 · Multi-agent orchestrator (LangGraph)"]
        ORCH["Orchestrator: plan route + framing"]
        SPEC["Specialists:<br/>segmentation · propensity<br/>market · portfolio"]
        OUT["Outreach: draft ⇄ critique<br/>(reflection loop, ≤3x)"]
        ORCH --> SPEC --> OUT
    end

    TOOLS["tools.py<br/>get_client_segment · compute_propensity<br/>get_call_context · get_market_sentiment<br/>recommend_rebalance · get_product_catalog ..."]
    LLM["llm.py<br/>provider-agnostic chat<br/>(+ mock mode, OS trust store)"]
    TELE["telemetry.py<br/>per-run latency · tokens<br/>node timing · redrafts"]

    subgraph EVALS["5 · Evaluation & observability"]
        EVAL["eval.py<br/>deterministic metrics<br/>+ optional LLM-as-judge"]
        REPORT["eval_report.json"]
        EVAL --> REPORT
    end

    subgraph API["6 · FastAPI service (api/main.py)"]
        EP["/api/dispatch · /api/clients · /api/segments<br/>/api/book/analytics · /api/market · /api/campaigns<br/>/api/agent/activity · /api/actions · /api/chat<br/>/api/agent/metrics · /api/agent/runs · /api/eval/report"]
        RAG["RAG copilot<br/>VectorStore (dense or hashing) → retrieve → cite"]
    end

    UI["React SPA"]

    DB --> SEG
    RANK --> ORCH
    SPEC -. calls .-> TOOLS
    OUT -. calls .-> LLM
    ORCH -. calls .-> LLM
    LLM -. records .-> TELE
    AGENT -. node timing .-> TELE
    TOOLS --> DB
    AGENT -->|scored_actions + reasoning traces + AgentRun telemetry| DB
    DB --> EVAL
    REPORT --> EP
    DB --> EP
    DB --> RAG
    EP --> UI
    RAG --> UI
```

**Flow of control**

1. `seed.py` generates six synthetic data sources and loads ~300 clients across 3 advisors into SQLite.
2. `run_pipeline.py` loads the book, runs the two **deterministic engines** over *every* client, then
   classifies and ranks each one (`URGENT` / `OPPORTUNITY` / `WATCHLIST`) by a blended priority score.
3. For the top `TOP_N_DRAFT` clients it invokes the **LangGraph orchestrator**: an orchestrator plans a
   route, specialist agents append findings to a shared reasoning trace, and an outreach agent drafts and
   self-critiques a compliance-safe message. Results (draft, framing, trace, confidence) are written back
   to `scored_actions`.
4. Throughout the run, `telemetry.py` captures per-node timing and every LLM call's token/latency; the
   pipeline persists one `AgentRun` row per client. `eval.py` then grades the book (deterministic
   metrics + optional LLM-as-judge) into `eval_report.json`.
5. **FastAPI** serves the scored book, telemetry, and eval report to the frontend and persists advisor
   Accept/Edit/Skip actions. A separate **RAG copilot** answers grounded questions over the same records.

---

## Frontend UI flow

A single-page React app (`react-router`) wrapped in a persistent `AppShell` (left nav + advisor
identity). Every page calls the typed API client (`src/api/client.ts`), which proxies `/api` to the
FastAPI backend. The primary demo journey is highlighted.

```mermaid
flowchart LR
    START(["RM opens app"]) --> SHELL{{"AppShell<br/>persistent left nav"}}

    SHELL --> DISPATCH["Morning Dispatch /<br/>ranked daily feed"]
    SHELL --> BOOK["Book Analytics /book<br/>AUM · revenue at risk · upsell pipeline"]
    SHELL --> CLIENTS["Clients /clients<br/>searchable/filterable roster"]
    SHELL --> SEGMENTS["Segments /segments<br/>4 clusters + playbooks"]
    SHELL --> MARKET["Market Signals /market<br/>sentiment feed"]
    SHELL --> CAMPAIGNS["Campaigns /campaigns<br/>outreach queue + statuses"]
    SHELL --> ASSIST["Book Assistant /assistant<br/>grounded copilot + citations"]
    SHELL --> ACTIVITY["Agent Activity /agent<br/>multi-agent reasoning log"]
    SHELL --> EVAL["Agent Eval /eval<br/>telemetry + quality metrics + LLM-judge"]

    DISPATCH -->|click a client| C360["Client 360 /clients/:id"]
    CLIENTS -->|click a client| C360
    SEGMENTS -->|drill into member| C360

    subgraph C360V["Client 360 view"]
        PROFILE["profile · portfolio trend · transactions<br/>call log + life-event timeline · digital engagement<br/>segment + look-alikes"]
        REC["agent recommendation<br/>+ multi-agent reasoning trace<br/>+ editable draft"]
        ASK["'Ask about this client'<br/>grounded copilot panel"]
    end
    C360 --> C360V

    DISPATCH -->|Accept / Edit / Skip| PERSIST["POST /api/actions/:id<br/>persists + toast"]
    REC -->|Accept / Edit / Skip| PERSIST
    CAMPAIGNS -->|Accept / Skip| PERSIST

    classDef primary fill:#1f6feb,stroke:#1f6feb,color:#fff;
    class DISPATCH,C360,PERSIST primary;
```

**The sub-60-second demo path (highlighted):** open **Morning Dispatch** → the most at-risk client is on
top → click into **Client 360** → read *why* she's flagged (the reasoning trace) and *what to say* (the
draft) → click **Accept** → the message is ready and the action persists.

---

## The multi-agent system

An **Orchestrator** agent reads each client's signals and decides which specialists to consult; each
specialist appends to a shared reasoning trace tagged with its own name, then an **Outreach** agent
drafts and self-critiques (reflection loop) before the recommendation is committed.

| Agent | Role |
|---|---|
| Orchestrator | Plans the route + framing (`re-engagement` / `opportunity` / `check-in`), synthesises the recommendation |
| Segmentation | Behavioural cluster (KMeans) + look-alike clients |
| Propensity / Risk | Attrition, upsell, revenue impact + engagement & net-flow trends |
| Market-Signal | Dated market sentiment vs the client's exposures |
| Portfolio-Nudge | Rebalance idea + eligible product from the catalog |
| Outreach | Draft → critique → regenerate (compliance-safe messaging) |

**The reflection loop & compliance guardrail.** The outreach draft must **never** mention scores, risk,
percentages, or internal metrics. The critique step scores the draft, and a deterministic regex
guardrail (`_METRIC_LEAK_PATTERNS`) catches any leaked number or term even if the LLM critique is
lenient — a failed check triggers a redraft (up to 3 attempts). This shows in the trace as an
`outreach · critique` step marked *failed*, followed by another `draft_message` step.

The orchestrator's plan drives **conditional edges** in the graph — the path taken changes with the
client, it is not a fixed pipeline. An opportunity routes through the portfolio-nudge agent, a
re-engagement goes straight to the market agent, and a light check-in skips both specialists.

```mermaid
flowchart LR
    P[plan] --> S[segmentation] --> R[propensity]
    R -->|opportunity| PF[portfolio] --> M[market]
    R -->|re-engagement| M
    R -->|check-in| D[draft]
    M --> D
    D --> C{critique<br/>passed?}
    C -->|yes| E([commit])
    C -->|no & < 3 tries| D
    C -->|no & 3 tries| E
```

---

## The pages (advisor suite)

- **Morning Dispatch** — the ranked daily feed; Accept / Edit / Skip persist to the DB.
- **Book Analytics** — AUM, revenue at risk, upsell pipeline, segment mix, top movers.
- **Clients** — the full searchable/filterable book roster.
- **Client 360** — profile, portfolio trend, transactions, call-log + life-event timeline, digital
  engagement, segment + look-alikes, the agent's recommendation with its multi-agent trace, and an
  **"Ask about this client"** grounded copilot panel.
- **Segments** — the four behavioural clusters, characteristics, and playbooks.
- **Market Signals** — the sentiment feed the Market agent reasons over.
- **Campaigns** — the outreach queue with accept/skip statuses.
- **Book Assistant** — a retrieval-grounded copilot that answers questions about your book (call notes,
  life events, market signals, agent rationale) and cites every source; says so when records don't
  support an answer, and never drafts client-facing messages.
- **Agent Activity** — the full chronological multi-agent reasoning log.
- **Agent Eval** — evaluation & observability: runtime telemetry (latency, tokens, per-node timing,
  framing mix, reflection-loop redrafts) alongside quality metrics (compliance, critique pass rate,
  specialist coverage, confidence) and per-draft LLM-as-judge scores.

---

## Evaluation & observability

NextBest treats the agent as something to be **measured**, not just run. This is deliberately
lightweight and in-repo — no external tracing service, no second framework — so it runs entirely on a
laptop (in keeping with the project's constraints).

**Observability (runtime telemetry).** A tiny context-local collector (`backend/telemetry.py`) records
each agent run as it happens: `llm.py` logs every completion (token usage, latency, live/mock, and its
purpose — plan/draft/critique/judge), and the orchestrator times each graph node. `run_pipeline.py`
persists one `AgentRun` row per client (total latency, per-node timing, token spend, redraft count,
compliance-guard hits, live/mock mode).

**Evaluation (output quality).** `backend/eval.py` grades the scored book:

- **Deterministic** (always, no LLM): draft coverage, critique pass rate, **metric-leak rate**
  (compliance), average redrafts, specialist coverage (did each consulted agent actually contribute a
  finding?), confidence distribution, latency p50/p95, and token spend.
- **LLM-as-judge** (only when an API key is set): an independent model scores each draft 1–5 on
  personalization, tone, actionability, and groundedness, plus a compliance flag.

Both are exposed via the API (`/api/agent/metrics`, `/api/agent/runs`, `/api/eval/report`) and rendered
on the **Agent Eval** page. Run it with:

```powershell
python -m backend.eval    # writes data/eval_report.json (judge scores included when a key is set)
```

The Agent Eval page always shows deterministic metrics live; running `backend.eval` adds the saved
LLM-as-judge scores.

---

## Setup guide

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- An LLM API key (optional — without one the agent runs in deterministic **mock mode**, enough to see the
  whole app). Supported: PwC GenAI Shared Service, OpenAI, Anthropic, or any OpenAI-compatible gateway.

### At a glance

```
Backend:   venv → pip install → (optional .env) → seed → run_pipeline → (optional rag.index) → uvicorn
Frontend:  npm install → npm run dev
```

### 1. Backend setup

Run everything from the **repository root** (the backend uses `backend.` package imports).

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure the LLM (optional — create `backend/.env`)

```powershell
Copy-Item backend/.env.example backend/.env   # PowerShell
```

Pick one provider (see `.env.example` for the full set). Leave keys blank to use **mock mode**.
The `.env` file holds a live secret — it is git-ignored and must never be committed.

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai` or `anthropic` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | your key (blank ⇒ mock mode) |
| `OPENAI_BASE_URL` | point at the PwC GenAI proxy or any OpenAI-compatible gateway |
| `OPENAI_MODEL` | e.g. `azure.gpt-4o-mini` (drafts) |
| `OPENAI_EMBED_MODEL` | embeddings model for the Book Assistant index |

### 3. Seed the database, then run the pipeline

```powershell
python -m backend.seed          # generates synthetic data + builds nextbest.db
python -m backend.run_pipeline  # engines + multi-agent scoring -> writes to the DB
```

`seed` creates ~300 clients across 3 advisors with 6 data sources (profiles, transactions, call logs,
life events, market sentiment, digital behaviour). `run_pipeline` scores the whole book and runs the
multi-agent orchestrator for the top-priority clients. With a real key you'll see per-client drafting
and critiquing; the run takes a few minutes. It also records per-run telemetry (see
[Evaluation & observability](#evaluation--observability)) that powers the **Agent Eval** page.

Optionally grade the results:

```powershell
python -m backend.eval    # deterministic quality metrics (+ LLM-as-judge when a key is set)
```

### 4. (Optional) Build the RAG index for the Book Assistant

```powershell
python -m backend.rag.index    # embeds the book -> data/rag_index.npz + .json
```

The **Book Assistant** copilot answers grounded questions about your book and cites its sources.
This step builds a dense embedding index and only runs when an OpenAI-compatible key is set. Without
a key (or without an embeddings model on the proxy) it no-ops with a message — the API then serves the
copilot via a deterministic scikit-learn `HashingVectorizer` fallback, so it always works. Re-run this
after regenerating data to refresh the index.

### 5. Start the API

```powershell
uvicorn backend.api.main:app --port 8000
```

### 6. Start the frontend (new terminal)

```powershell
cd frontend
npm install        # first time only
npm run dev
```

Open the URL it prints (default **http://localhost:5173/**). The dev server proxies `/api` to
`http://127.0.0.1:8000`, so both must be running.

---

## Regenerating data / re-scoring

```powershell
python -m backend.generate_data     # optional: regenerate the JSON (seeded, reproducible)
python -m backend.seed              # rebuild the DB from JSON (drops + recreates tables)
python -m backend.propensity_model  # optional: train the XGBoost propensity models (+ metrics)
python -m backend.run_pipeline      # re-score + re-draft (records agent telemetry)
python -m backend.eval              # re-grade quality (writes eval_report.json)
python -m backend.rag.index         # refresh the Book Assistant index (only with a key)
```

**Propensity: rules vs learned model.** The rule engine is the transparent default (it lists the exact
rules that fired). To score the book with the trained **XGBoost** models instead, train them once with
`python -m backend.propensity_model`, then run the pipeline with `USE_XGB_PROPENSITY=1`. The models
learn the rule scoring policy from the shared `features_for()` interface, so the agent, ranking, and UI
are unchanged — and the fired-rule explanations are still computed either way. Model fit quality and
feature importances are served at `GET /api/model/propensity`.

## Running the tests

```powershell
python -m pytest backend/tests/ -v
```

Pure, deterministic checks on the segmentation and propensity engines (no LLM calls).

---

## Verifying the agent is using the LLM

Open the **Agent Activity** page or inspect a top client's trace on **Client 360**:

- **Mock** drafts are fixed sentences and identical every run.
- **Live** drafts are freshly worded and vary between runs.
- The **reflection loop** shows as an `outreach · critique` step marked "failed" followed by another
  `draft_message` step (the agent regenerating up to 3 times).

## Troubleshooting

- **`ModuleNotFoundError: No module named 'backend'`.** Run from the **repo root**, not inside `backend/`.
- **API page shows "Couldn't reach the agent service".** Start `uvicorn backend.api.main:app --port 8000`.
- **Empty feed / 404s.** You skipped a step — run `python -m backend.seed` then `python -m backend.run_pipeline`.
- **`CERTIFICATE_VERIFY_FAILED` on a corporate network.** Handled via `truststore` in `backend/llm.py`;
  just ensure `pip install -r backend/requirements.txt` ran (PwC endpoints also need the VPN).
- **Port already in use.** Vite will pick the next free port; for the API pass `--port 8001` and update
  the proxy target in `frontend/vite.config.ts`.

---

## Repo layout

```
nextbest/
├── backend/
│   ├── schemas.py          # pydantic contracts (NextBestAction, ReasoningStep, ...)
│   ├── config.py           # seed, sizes, DB path, RAG settings
│   ├── generate_data.py    # synthetic 6-source dataset (seeded)
│   ├── db.py               # SQLAlchemy models (SQLite)
│   ├── seed.py             # generate + load into the DB
│   ├── segment.py          # Engine 1 — KMeans behavioural segmentation
│   ├── propensity.py       # Engine 2 — attrition / upsell / revenue scoring
│   ├── tools.py            # agent tools (segment, propensity, market, rebalance, ...)
│   ├── llm.py              # provider-agnostic LLM client (+ mock mode, telemetry, OS trust store)
│   ├── prompts.py          # orchestrator / draft / critique / RAG / judge prompts
│   ├── telemetry.py        # per-run agent telemetry collector (observability)
│   ├── agents/             # multi-agent core (orchestrator + specialists + state)
│   ├── rag/                # Book Assistant: corpus, vector store, index, chat
│   ├── run_pipeline.py     # engines + agents -> DB (persists AgentRun telemetry)
│   ├── eval.py             # evaluation harness (deterministic metrics + LLM-as-judge)
│   ├── api/                # FastAPI service (main.py + serializers)
│   └── tests/              # deterministic engine tests
└── frontend/               # Vite + React + TS multi-page SPA
    └── src/{api,pages,layout,components,lib,styles}
```

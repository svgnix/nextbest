# NextBest

An AI **"next best action"** personalisation platform for bank/wealth relationship managers (RMs).
Built for the Apex Wealth *"Know Your Wealth"* brief: segment clients beyond AUM, predict attrition and
upsell, and give advisors a tool they'll actually use — a persistent, multi-page workspace driven by a
**multi-agent** system that shows its reasoning and closes the loop from insight to a ready-to-send draft.

Architecture in one line:

```
Synthetic data (6 sources) → SQLite → engines (segmentation + propensity)
   → multi-agent orchestrator (plan → specialists → draft → critique) → FastAPI → React SPA
```

- **Backend / agent:** Python 3.11+, `pydantic`, `scikit-learn`, `langgraph`, `sqlalchemy`, `fastapi`.
- **Frontend:** React + Vite + TypeScript, `react-router`, hand-built CSS + SVG charts (no component library).
- **Persistence:** one local SQLite DB (`backend/data/nextbest.db`); advisor actions/feedback persist.

## The multi-agent system

An **Orchestrator** agent reads each client's signals and decides which specialists to consult; each
specialist appends to a shared reasoning trace tagged with its own name, then an **Outreach** agent
drafts and self-critiques (reflection loop) before the recommendation is committed.

| Agent | Role |
|---|---|
| Orchestrator | Plans the route + framing, synthesises the recommendation |
| Segmentation | Behavioural cluster (KMeans) + look-alike clients |
| Propensity / Risk | Attrition, upsell, revenue impact + engagement/flow trends |
| Market-Signal | Dated market sentiment vs the client's exposures |
| Portfolio-Nudge | Rebalance idea + eligible product |
| Outreach | Draft → critique → regenerate (compliance-safe messaging) |

## The pages (advisor suite)

- **Morning Dispatch** — the ranked daily feed; Accept / Edit / Skip persist to the DB.
- **Book Analytics** — AUM, revenue at risk, upsell pipeline, segment mix, top movers.
- **Clients** — the full searchable/filterable book roster.
- **Client 360** — profile, portfolio trend, transactions, call-log + life-event timeline, digital
  engagement, segment + look-alikes, and the agent's recommendation with its multi-agent trace.
- **Segments** — the four behavioural clusters, characteristics, and playbooks.
- **Market Signals** — the sentiment feed the Market agent reasons over.
- **Campaigns** — the outreach queue with accept/skip statuses.
- **Agent Activity** — the full chronological multi-agent reasoning log.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- An LLM API key (optional — without one the agent runs in deterministic **mock mode**, enough to see the
  whole app). Supported: PwC GenAI Shared Service, OpenAI, Anthropic, or any OpenAI-compatible gateway.

---

## 1. Backend setup

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

## 2. Configure the LLM (optional — create `backend/.env`)

```powershell
Copy-Item backend/.env.example backend/.env   # PowerShell
```

Pick one provider (see `.env.example` for the full set). Leave keys blank to use **mock mode**.
The `.env` file holds a live secret — it is git-ignored and must never be committed.

## 3. Seed the database, then run the pipeline

```powershell
python -m backend.seed          # generates synthetic data + builds nextbest.db
python -m backend.run_pipeline  # engines + multi-agent scoring -> writes to the DB
```

`seed` creates ~300 clients across 3 advisors with 6 data sources (profiles, transactions, call logs,
life events, market sentiment, digital behaviour). `run_pipeline` scores the whole book and runs the
multi-agent orchestrator for the top-priority clients. With a real key you'll see per-client drafting
and critiquing; the run takes a few minutes.

## 4. Start the API

```powershell
uvicorn backend.api.main:app --port 8000
```

## 5. Start the frontend (new terminal)

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
python -m backend.generate_data   # optional: regenerate the JSON (seeded, reproducible)
python -m backend.seed            # rebuild the DB from JSON (drops + recreates tables)
python -m backend.run_pipeline    # re-score + re-draft
```

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
│   ├── schemas.py          # pydantic contracts
│   ├── config.py           # seed, sizes, DB path
│   ├── generate_data.py    # synthetic 6-source dataset (seeded)
│   ├── db.py               # SQLAlchemy models (SQLite)
│   ├── seed.py             # generate + load into the DB
│   ├── segment.py          # Engine 1 — KMeans behavioural segmentation
│   ├── propensity.py       # Engine 2 — attrition / upsell / revenue scoring
│   ├── tools.py            # agent tools (segment, propensity, market, rebalance, ...)
│   ├── llm.py              # provider-agnostic LLM client (+ OS trust store)
│   ├── prompts.py          # orchestrator / draft / critique prompts
│   ├── agents/             # multi-agent core (orchestrator + specialists)
│   ├── run_pipeline.py     # engines + agents -> DB
│   ├── api/                # FastAPI service
│   └── tests/
└── frontend/               # Vite + React + TS multi-page SPA
    └── src/{api,pages,layout,components,lib,styles}
```

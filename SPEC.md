# SPEC.md — NextBest functional & technical spec

Source of truth for **behavior**. Pair with `DESIGN.md` for look/feel and `CLAUDE.md` for stack/order.

---

## 1. Context (why this exists)

- Users: bank/wealth **relationship managers (RMs)**, each with 200–300 high-net-worth clients.
- Problem: RMs can't proactively serve everyone; most firms still segment by AUM alone; insight in the
  data never reaches the RM in time, so clients quietly split assets and leave.
- Product: a daily, ranked "next best action" feed. Each item = who + why + a draft opener, with a
  confidence score and a rationale the RM can act on or override.
- Differentiator: closes the loop from *insight* to *recommended action*, human always in control.

The system is agentic: a planner reasons over each client, decides which tools/engines to consult,
drafts an opener, critiques it, and commits a structured decision. The three "engines" below are
implemented as **tools** the agent calls.

---

## 2. Component 1 — Synthetic data generator (`generate_data.py`)

Generate **50** realistic HNW client records → `data/clients.json`. Seed RNG (`SEED=42`).
Cover all **five data sources** from the pitch. Field set:

| Field | Type | Source group | Notes |
|---|---|---|---|
| `client_id` | str | — | `C001`…`C050` |
| `name` | str | — | realistic full names (use `faker`) |
| `portfolio_value` | int (USD) | transactions | ~$1M–$50M, right-skewed |
| `portfolio_change_pct` | float | transactions | last 90d, e.g. `+22.0` |
| `withdrawals_last_90_days` | int (USD) | transactions | 0..large |
| `account_tenure_years` | float | transactions | 0.2..25 |
| `last_contact_note` | str | call logs | 1–2 sentence CRM note |
| `call_log` | list[{date, note}] | call logs | 1–4 past notes (feeds retrieval) |
| `days_since_last_contact` | int | call logs | 0..180 |
| `life_events` | list[str] | life events | e.g. `property_purchase`, `child_education`, `inheritance`, `retirement`, `business_sale` |
| `login_frequency_change` | float (%) | digital behaviour | last 30d, e.g. `-40.0` |
| `email_open_rate_change` | float (%) | digital behaviour | last 30d, e.g. `-55.0` |
| `market_exposure` | list[str] | market signals | sectors/asset classes the client is exposed to, e.g. `["tech_equities","muni_bonds"]` |

**Internal consistency matters.** A client flagged `property_purchase` should plausibly have a positive
`portfolio_change_pct` and recent withdrawals; a churning client should show declining logins/opens,
large withdrawals, and a high `days_since_last_contact`. Random-but-incoherent records make the demo
look fake.

### Hero clients (design these by hand)

Include 4–5 fixed clients so the ranked feed tells an obvious story. At minimum, matching the pitch deck:

- **Priya Mehta** — clear **attrition**: `days_since_last_contact≈94`, logins/opens down sharply, a
  recent large withdrawal; `last_contact_note` mentions her daughter's education fund. Should land ~78%
  attrition risk and rank #1.
- **Arjun Rao** — clear **upsell**: `portfolio_change_pct≈+22`, `life_events` includes
  `property_purchase`; should land ~61% upsell readiness.
- **The Sharma family** — **watchlist**: mild engagement dip, nothing urgent.

---

## 3. Engine 1 — Segmentation (`segment.py`)

Behavioral clustering, **not** AUM bands. This is a named pillar of the pitch — don't skip it.

- Feature vector per client from *behavioral* signals only: `login_frequency_change`,
  `email_open_rate_change`, `days_since_last_contact`, `withdrawals_last_90_days` (log-scaled),
  `portfolio_change_pct`, number of recent life events. Standardize features.
- `KMeans` (k=4, seeded). Assign each client a `segment_id` and a human label derived from the cluster's
  centroid character, e.g. `"Disengaging"`, `"Growth-minded"`, `"Steady loyalist"`, `"New & exploring"`.
- Also compute, per client, 2–3 **look-alike** `client_id`s (nearest neighbors in feature space) so the
  agent can reason "clients like this responded well to X."
- Output added to each record: `segment` (`{id, label}`), `lookalikes: [client_id,...]`.

Keep it deterministic and explainable — the label and the driving features must be surfaceable in the UI.

---

## 4. Engine 2 — Propensity (`propensity.py`)

Two scores per client, each 0–100, plus a revenue term. **Rule-based baseline** (transparent), with an
optional model swap noted below.

### Attrition risk (higher = more likely to leave)
```
+40  days_since_last_contact > 90
+20  60 < days_since_last_contact <= 90
+20  login_frequency_change < -30
+15  email_open_rate_change  < -40
+25  withdrawals_last_90_days > 100_000
+10  account_tenure_years < 2
cap at 100
```

### Upsell readiness (higher = more receptive to a new product)
```
+35  portfolio_change_pct > 15
+30  life_events includes property_purchase
+25  life_events includes inheritance
+15  days_since_last_contact < 30
+10  account_tenure_years > 5
cap at 100
```

### Revenue impact (for ranking — from the pitch's "ranked by revenue impact and attrition risk")
```
revenue_impact = round( (upsell_ready/100) * portfolio_value )   # USD upside proxy
```
A high-upsell $30M client must outrank a high-upsell $2M client. Expose both the raw number and a
0–100 normalized `revenue_impact_score` (min-max across the book) for display.

### Emit, per client
`attrition_risk`, `upsell_ready`, `revenue_impact` (USD), `revenue_impact_score` (0–100), and a list of
the **rules that fired** (short strings) so the rationale and UI can cite concrete drivers.

### Propensity model note (feasibility talking point)
The pitch names XGBoost. For the MVP keep the rules — they're fully explainable to the RM and need no
labeled data (no compliance blocker). Structure `propensity.py` so the scoring function has a clean input
interface (`features_for(client) -> dict`), so an `xgboost` model can be dropped in later **without
changing the agent or UI**. Optionally train a tiny `xgboost` model on rule-generated labels as a "the
model is real" flourish, but only after everything else works, and label it honestly as such.

---

## 5. Engine 3 — Agent core (`agent.py`, `tools.py`, `llm.py`)

A per-client agent loop: **plan → call tools → draft → critique → (loop on fail) → commit**. Build with
LangGraph (nodes + conditional edges) so the reflection loop is an explicit cycle you can also show in
the pitch. A hand-rolled loop over the provider SDK's tool-calling is an acceptable alternative if
LangGraph fights you — keep the same node structure.

### Tools (the tool belt)
Expose these as tools the planner can call. First three = the three pitched engines.

| Tool | Signature | Returns |
|---|---|---|
| `get_client_segment` | `(client_id)` | segment `{id,label}`, lookalikes, driving features |
| `compute_propensity` | `(client_id)` | attrition_risk, upsell_ready, revenue_impact, fired rules |
| `get_call_context` | `(client_id, query)` | most relevant past call-log notes (retrieval over `call_log`) |
| `get_product_catalog` | `(filters)` | bank products eligible given segment / life events |
| `get_market_context` | `(topics)` | 1–2 short, timely notes for the client's `market_exposure` (5th data source) |

`get_call_context` is the "RAG over call logs" layer from the pitch. For 1–4 notes per client a simple
embedding-similarity or keyword rank is enough; a tiny in-memory vector store is the stretch version.

### Planner
Given a client record, the planner decides which tools to call and in what order. It **branches**: a
high-attrition client pulls call context and frames a re-engagement; a high-upsell client pulls product
catalog + market context and frames an opportunity; a watchlist client stays light. This branching *is*
the agentic substance — don't collapse it into a fixed call order.

### Draft
Compose a short (2–3 sentence) opener. Prompt lives in the system message; template variables: name,
retrieved call context, life events, and the chosen reason. Hard rule in the system prompt: warm,
professional, human; **never mention scores, risk, or internal metrics.**

### Reflection (the loop)
A `critique` node scores the draft against explicit checks:
1. Leaks no score/risk/internal metric.
2. References something real about the client (personalized, not generic).
3. Tone: warm + professional, no salesy pressure.
4. Length ≤ ~3 sentences.

If any check fails, return to `draft` with the critique as feedback and regenerate (max 2 retries, then
keep best). Record the pass/fail. This is the reflection pattern and is the most defensible agentic
element — implement it, don't fake it.

### `llm.py`
Provider-agnostic. Read `LLM_PROVIDER` (`anthropic`|`openai`) and the matching key from env. Expose one
`chat(messages, tools=None) -> {text, tool_calls}` used by every node. No key literals in code.

---

## 6. `NextBestAction` schema (`schemas.py`) — the contract

Every later stage and the entire UI depend on this. Emit one per client into `scored_clients.json`.

```python
class ReasoningStep(BaseModel):
    tool: str            # e.g. "compute_propensity"
    finding: str         # one short plain-language sentence of what it returned
    ts_ms: int           # for the animated timeline in the UI

class NextBestAction(BaseModel):
    client_id: str
    name: str
    action_type: Literal["URGENT", "OPPORTUNITY", "WATCHLIST"]
    attrition_risk: int          # 0-100
    upsell_ready: int            # 0-100
    revenue_impact: int          # USD
    revenue_impact_score: int    # 0-100 (normalized across book)
    priority_rank: int           # 1 = most important
    confidence: int              # 0-100, agent's confidence in the recommendation
    segment: dict                # {id, label}
    headline: str                # e.g. "Reconnect before she moves the education fund"
    rationale: str               # plain-language "why this, why now" (no internal metrics)
    reasons: list[str]           # concrete drivers cited (fired rules, life events)
    draft_message: str           # the editable opener
    draft_passed_critique: bool
    reasoning_trace: list[ReasoningStep]
```

### Ranking rule
`action_type`: `URGENT` if attrition_risk > upsell_ready and attrition_risk ≥ 50; `OPPORTUNITY` if
upsell_ready ≥ attrition_risk and upsell_ready ≥ 50; else `WATCHLIST`.
`priority_rank`: sort descending by a blended score
`0.6 * max(attrition_risk, upsell_ready) + 0.4 * revenue_impact_score`, so both urgency and money matter
(matches the pitch's "ranked by revenue impact and attrition risk"). Assign 1..N after sorting.

`confidence`: derive from signal strength/agreement (e.g. how many rules fired, whether call context was
found, whether the draft passed critique on the first try). Keep the formula simple and documented.

---

## 7. Component 4 — RM dashboard (frontend)

Behavior only here; the *look* is governed entirely by `DESIGN.md`.

Reads `scored_clients.json`. Renders the ranked feed (most urgent first). Per client, collapsed view shows
name, `action_type` badge, the leading metric (e.g. "78% attrition risk"), `headline`, and the draft in an
editable field with **Accept · Edit · Skip**. Expanding a client reveals:

- the **reasoning trace** (`reasoning_trace`) as a stepped timeline — segment → propensity → call context
  → market/product → draft → critique — this is the agent "showing its work";
- the **confidence** indicator;
- `rationale` in full and the `reasons` chips;
- the full draft editor.

Buttons are cosmetic for the demo (no persistence needed) but must feel functional: Accept marks the card
done with a toast, Skip dismisses it, Edit focuses the textarea. Filtering/sorting done client-side in JS.

### Frontend data contract
`scored_clients.json` = a JSON array of `NextBestAction` objects, pre-sorted by `priority_rank`. Mirror
the schema as a TS type in `frontend/src/types.ts`. If a field the UI needs isn't present, fix the
backend — don't invent it in the frontend.

---

## 8. Out of scope
Auth, databases, real integrations, deployment/scaling, multi-user. Local demo only. Synthetic data only.

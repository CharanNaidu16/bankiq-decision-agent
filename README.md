# BankIQ — Enterprise Decision Intelligence Agent for Banking

> Ask a banking question in plain English. A triage router decides how to answer it:
> a genuine KPI investigation sends five autonomous agents across seven datasets to
> build a causal evidence chain with confidence scores, quantify revenue at risk, and
> deliver a board-ready executive report — streamed live. Simpler questions take
> cheaper paths, and unsafe requests are refused.

BankIQ turns a one-line question from a CEO or COO —

> *"Why did our loan approval rate drop 18% in the South zone last quarter?"*

— into a structured, defensible investigation in under ~90 seconds. A quick factual
lookup ("What was NPS in North in Q2?") or a concept question ("What is NPA?") is
answered in a single step instead, and write/destructive/jailbreak requests are
declined by a read-only guardrail.

---

## Problem statement

Banking leaders see a KPI move and need to know **why**, **how much it will cost**,
and **what to do** — fast, and with evidence. Today that means days of analyst work
stitching together loan, customer, branch, staffing, risk, product, and event data.
BankIQ automates that investigation as a pipeline of specialized LLM agents that
reason over the data and produce an executive narrative with a quantified causal
chain, not just a dashboard.

---

## Architecture

```
                    ┌──────────────────────────────────────────────────────────┐
                    │                     React + Vite UI                        │
                    │   QuestionInput → AgentProgressTracker → ExecutiveReport   │
                    └───────────────▲───────────────────────────┬───────────────┘
                                    │  Server-Sent Events (SSE)  │ POST /api/investigate
                                    │  agent_progress · report   │ { "question": "..." }
                    ┌───────────────┴───────────────────────────▼───────────────┐
                    │                    FastAPI backend                         │
                    │              InvestigationPipeline (async)                 │
                    │                                                            │
                    │                  ┌───────────────┐                         │
                    │   question  ───► │ Triage Router │  classify (1 LLM call)  │
                    │                  └───────┬───────┘                         │
                    │        ┌─────────────────┼───────────────┬─────────────┐   │
                    │        ▼                 ▼               ▼             ▼   │
                    │  investigation      simple_query    out_of_scope   rejected│
                    │  (full pipeline)    (Quick Answer)  (Assistant)   (refused)│
                    │        │                                                   │
                    │        ▼  full five-agent investigation                    │
                    │  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌────┐│
                    │  │ Intent │→ │  Data    │→ │  Root    │→ │ Impact │→ │Exec ││
                    │  │ Agent  │  │ Analyst  │  │  Cause   │  │Forecast│  │Rep. ││
                    │  └────────┘  └──────────┘  └──────────┘  └────────┘  └────┘│
                    │       │  typed Pydantic context bus flows left → right     │
                    │       ▼            ▼             ▼            ▼        ▼    │
                    │  ┌──────────────────────┐   ┌─────────────────────────┐   │
                    │  │  DatasetRepository    │   │     GroqLlmClient        │  │
                    │  │  (pandas: load/slice/ │   │  openai SDK → Groq Cloud │  │
                    │  │   serialize 7 CSVs)   │   │  (llama-3.3-70b JSON)    │  │
                    │  └──────────┬───────────┘   └─────────────────────────┘   │
                    └─────────────┼──────────────────────────────────────────────┘
                                  ▼
        loan_performance · customer_metrics · branch_operations · staffing ·
        risk_metrics · product_performance · event_log   (synthetic CSVs)
```

**Design principles**

- **Triage-first routing.** A lightweight Triage Router classifies every question in
  one LLM call and dispatches it to the cheapest path that can answer it — only true
  KPI investigations pay for the full five-agent pipeline.
- **Read-only guardrails.** Any request to write, modify, or delete data, change the
  app/config, or jailbreak the system is classified `rejected` and answered with a
  fixed, server-controlled message — never model-generated, so a crafted prompt can't
  coax a harmful or leaky reply.
- **Stateless agents.** Each agent is a class with a single `run()` coroutine. It
  holds no per-request state; everything arrives as a typed Pydantic model.
- **Typed context bus.** `InvestigationContext` accumulates each stage's result for
  the next stage — no untyped dicts cross agent boundaries.
- **Pure-LLM reasoning.** `DatasetRepository` only loads, filters, and serializes
  the CSVs to markdown; the LLM computes deltas, anomalies, and the causal chain.
- **Live streaming.** The pipeline is an async generator; each agent emits a
  `started`/`completed` (or `failed`) SSE event, then a terminal `report` event.
- **Graceful degradation.** Any agent failure is caught, logged with Rich, surfaced
  as a `failed` event, and replaced by a typed degraded result — the client always
  receives a report, never a raw 500. If the triage call itself can't run (the LLM is
  rate-limited or misconfigured), BankIQ returns one honest "temporarily unavailable"
  report instead of fanning out to five more doomed LLM calls.
- **Share-ready output.** A finished report can be copied to the clipboard or emailed
  directly from the UI to one or more recipients (with Cc) via a configured SMTP
  account — the "Email report" control is shown only when SMTP credentials are present.

---

## How a question is routed

The Triage Router runs first and labels each message with exactly one category. Every
path ends in the same terminal `report` SSE event, so the streaming contract — and the
UI — is identical regardless of which path ran.

| Category        | Path                        | What runs                                                        | Cost          |
|-----------------|-----------------------------|------------------------------------------------------------------|---------------|
| `investigation` | Full five-agent pipeline    | Intent → Data Analyst → Root Cause → Impact Forecast → Exec Report | ~6 LLM calls  |
| `simple_query`  | Quick Answer                | Intent (to scope the slice) → single data-grounded answer        | ~2 LLM calls  |
| `out_of_scope`  | BankIQ Assistant            | One LLM call; answers banking/finance/economics, declines the rest | 1 LLM call    |
| `rejected`      | Refusal                     | No further LLM calls; fixed read-only guardrail message          | 0 extra calls |

When a banking question is genuinely ambiguous between `investigation` and
`simple_query`, triage prefers `investigation` — a richer answer is safer than a wrong
refusal.

---

## Tech stack

| Layer     | Technology                                                            |
|-----------|-----------------------------------------------------------------------|
| Backend   | Python 3.11+, FastAPI, sse-starlette, Pydantic v2, pandas, Rich        |
| LLM       | Groq Cloud via the OpenAI-compatible SDK (`llama-3.3-70b-versatile`)   |
| Email     | Standard-library `smtplib` over STARTTLS (e.g. Gmail SMTP, optional)   |
| Frontend  | React 18, Vite, TypeScript (native `fetch` + `ReadableStream` for SSE) |

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS/Linux:         source .venv/bin/activate
pip install -r requirements.txt
```

Configure credentials (from the project root):

```bash
cp .env.example .env      # then edit GROQ_API_KEY (get one at https://console.groq.com/keys)
```

The seven datasets ship with the repository (in `backend/data/`), so no data step is
needed — just run the API:

```bash
uvicorn app.main:app --reload          # http://127.0.0.1:8000
```

> **Optional — emailing reports.** To enable the "Email report" button, also set the
> `SMTP_*` values in `.env` (for Gmail, use your address as `SMTP_USERNAME` and a
> 16-character **App Password** as `SMTP_PASSWORD`). Leave them blank to run without
> email — the rest of BankIQ is unaffected and the button simply stays hidden.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173  (proxies /api → :8000)
```

Open http://localhost:5173 and ask a question.

> **No API key?** BankIQ still runs and returns a clearly-labeled *degraded* report
> instead of crashing, so the UI and pipeline can be demonstrated end to end.

---

## Test scenarios in the data

The synthetic datasets span **seven zones** across four quarters of 2025. Five zones
(North, East, West, Central, plus the headline **South**) are stable baselines apart
from South's Q3 crisis. Two additional zones exist specifically to exercise the
pipeline across **different positive and negative outcomes** with *distinct* root
causes, so you can confirm the agents discriminate rather than pattern-match:

| Zone        | Outcome              | What's in the data                                                                                   | Triggering events                                              |
|-------------|----------------------|------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| **South**   | 🔴 Negative — staffing | Q3 collapse: 3 senior underwriters resign → training 89%→31%, processing 3→9 days, approvals −18%      | `EVT-2025-0814-STH`, `EVT-2025-0820-STH`                        |
| **Southeast** | 🔴 Negative — fraud/compliance | Q4 collapse: fraud ring in Business Loans → fraud cases 6→22, compliance flags 5→19, audit 87→64, NPA 3.05%→5.2% | `EVT-2025-1105-STE`, `EVT-2025-1118-STE`                        |
| **Northwest** | 🟢 Positive — turnaround | Weak Q1 → strong Q4: approvals 67.5%→76.2%, NPS 58→78, churn 11.5%→6.5%, training 72%→95.5%             | `EVT-2025-0410-NWS` (digital platform), `EVT-2025-0815-NWS` (upskilling) |

South and Southeast share similar surface symptoms (declining approvals, falling NPS)
but **different root causes** — staffing vs. fraud — which is the key discrimination
test. Northwest exercises the positive/improvement path.

## Example queries

The five scenarios below are full **investigations**. To see the other routing paths,
try a factual lookup like *"What was the NPS in North in Q2 2025?"* (Quick Answer), a
concept question like *"What is NPA?"* (BankIQ Assistant), or a write attempt like
*"Delete all loan records for the North zone."* (refused by the read-only guardrail).

### 1. Approval-rate drop (the headline scenario)
```
Why did our loan approval rate drop 18% in the South zone last quarter?
```
**Expected:** Root cause = the **Aug 14 2025 resignation of 3 senior underwriters**
in South; causal chain through staffing collapse → training failure (89% → 31%) →
processing delays (3 → 9 days) → Personal-Loan approval −31% / overall −18% →
NPS 72 → 41 → rising NPA. Headline exposure ≈ **₹6 Cr** (₹4.2 Cr lost disbursement
+ ₹1.8 Cr NPA).

### 2. Customer experience collapse
```
What is driving the NPS collapse and customer churn in the South zone?
```
**Expected:** Same triggering event, framed around customer impact — NPS 72 → 41,
complaints tripled, churn spike, branch wait times +40% — traced back to the
understaffed Personal-Loan desk.

### 3. Financial exposure
```
Quantify the revenue and NPA exposure from the South zone Personal Loan slowdown.
```
**Expected:** 30/60/90-day projections in ₹ Cr, leading with ~₹4.2 Cr lost
Personal-Loan disbursement and ~₹1.8 Cr NPA provisioning, plus recommended actions
with named owners.

### 4. A different crisis — fraud, not staffing (root-cause discrimination)
```
Why did the Southeast zone deteriorate in Q4, and what is the root cause?
```
**Expected:** Root cause = the **Nov 2025 Business-Loan fraud ring**
(`EVT-2025-1105-STE`) and the follow-on regulatory review — *not* staffing. Causal
chain through fraud cases 6 → 22 → compliance flags 5 → 19 / audit score 87 → 64 →
Business-Loan default 4.1% → 8.2% → tightened approvals and NPS 70 → 55. This should
read clearly differently from the South staffing collapse despite similar symptoms.

### 5. A positive outcome — what went right (improvement path)
```
What drove the turnaround and improvement in the Northwest zone during 2025?
```
**Expected:** Improvement traced to the **Apr digital lending platform**
(`EVT-2025-0410-NWS`) and **Aug underwriter upskilling** (`EVT-2025-0815-NWS`):
training completion 72% → 95.5%, processing 4.2 → 2.4 days, approvals 67.5% → 76.2%,
NPS 58 → 78, churn 11.5% → 6.5%, NPA 3.8% → 2.5%. Confirms the pipeline narrates a
positive trajectory, not just failures.

---

## Sample report output (abridged)

```
BankIQ Investigation — South Zone Loan Approval Decline
=======================================================
EXECUTIVE SUMMARY
South zone loan approvals fell ~18% in Q3 2025 (Personal Loans −31%), driven by the
Aug 14 resignation of three senior underwriters. Unaddressed, this carries ≈₹6.0 Cr
of 30-day exposure (₹4.2 Cr lost disbursement + ₹1.8 Cr NPA).

WHAT HAPPENED
South overall approval rate 71.7% → 58.4% (Q2 → Q3); Personal-Loan processing time
tripled from 3 to 9 days.

TRIGGERING EVENT
2025-08-14 — 3 senior underwriters resigned from the South Personal-Loan desk
(event EVT-2025-0814-STH, Critical).

WHY IT HAPPENED  (causal chain — overall confidence 0.9)
  1. Underwriter resignations → headcount −22%, open positions spike   (0.95)
  2. Capacity loss → training completion 89% → 31%                      (0.88)
  3. Under-trained, overstretched staff → processing time 3 → 9 days    (0.90)
  4. Processing backlog → Personal-Loan approval −31%, overall −18%     (0.92)
  5. Slow/declined approvals → NPS 72 → 41, complaints tripled, churn ↑ (0.85)
  6. Rushed approvals → NPA rate rising, compliance flags up            (0.78)

FINANCIAL IMPACT (₹ Cr)
  30d: revenue ₹4.20 + NPA ₹1.80 = ₹6.00
  60d: revenue ₹8.40 + NPA ₹3.20 = ₹11.60
  90d: revenue ₹12.60 + NPA ₹4.80 = ₹17.40

RECOMMENDED ACTIONS
  1. [HIGH] Emergency underwriter backfill — Owner: Zonal HR Head — 30 days
  2. [HIGH] Fast-track credit training — Owner: Chief Credit Officer — 60 days
  3. [MEDIUM] Personal-Loan backlog task force — Owner: South Zone Head — 30 days
```

*(Exact figures and wording vary with the model; the causal chain and ~₹6 Cr
headline are designed to be consistently discoverable.)*

---

## Project layout

```
.
├── backend/
│   ├── app/            FastAPI app, agents (triage + 5 investigation + 2 lightweight),
│   │                   pipeline, services, models, prompts
│   └── data/           the seven synthetic CSV datasets (committed with the repo)
└── frontend/
    └── src/            React UI (components, hooks, api, types, styles)
```

---

## License

Provided for demonstration and educational use. All data is synthetic.

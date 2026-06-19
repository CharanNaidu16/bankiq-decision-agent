# BankIQ Backend

FastAPI service that triages each question and runs the five-agent investigation
pipeline (or a cheaper lightweight path) over Groq.

## Setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS/Linux:         source .venv/bin/activate
pip install -r requirements.txt

# Configure credentials (from the project root)
cp ../.env.example ../.env   # then edit GROQ_API_KEY

# Generate the seven synthetic datasets
python scripts/generate_synthetic_data.py

# Run the API (http://127.0.0.1:8000)
uvicorn app.main:app --reload
```

## Endpoints

| Method | Path                | Description                                              |
|--------|---------------------|----------------------------------------------------------|
| GET    | `/api/health`       | Readiness: model, LLM-configured flag, datasets present. |
| POST   | `/api/investigate`  | Runs the pipeline; streams progress + report over SSE.   |

### Example (SSE stream)

```bash
curl -N -X POST http://127.0.0.1:8000/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did our loan approval rate drop 18% in the South zone last quarter?"}'
```

## Layout

```
app/
  main.py          FastAPI app + lifespan
  config.py        env-driven settings        constants.py  domain constants
  models/          Pydantic contracts (the typed agent bus)
  agents/          base_agent + triage router + 5 investigation agents
                   + 2 lightweight agents (simple_query, general_assistant), all stateless
  pipeline/        triage routing + sequential orchestration + SSE generator + degraded fallbacks
  services/        dataset_repository (pandas) + llm_client (Groq)
  prompts/         per-agent system prompts
  api/routes.py    /api/investigate (SSE) + /api/health
  core/            Rich logging + exception hierarchy
scripts/
  generate_synthetic_data.py   standalone CSV generator with the planted story
```

## Quality checks

```bash
ruff check app scripts
mypy app
```

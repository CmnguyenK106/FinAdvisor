# Python Agent Core

This folder contains the LangGraph-based agent core.

## Run locally

```bash
pip install -r requirements.txt
uvicorn agent.service:app --host 0.0.0.0 --port 8000
```

## Environment variables
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL` (default: https://openrouter.ai/api/v1)
- `OPENROUTER_MODEL` (default: google/gemma-4-9b-it)
- `GATEWAY_URL` (default: http://localhost:8081)
- `AGENT_MAX_ITERATIONS` (default: 2)
- `AGENT_MIN_CONFIDENCE` (default: 60)

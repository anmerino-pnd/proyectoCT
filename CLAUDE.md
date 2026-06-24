# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

RAG-based conversational agent (chatbot) for **CT Internacional**, a technology/computing
company. It answers user queries about products, promotions, order status, and support by
combining an LLM with semantic search and live database lookups. Python 3.13, packaged under
`src/ct`, managed with `uv`. Codebase and docs are primarily in Spanish; preserve Spanish terms
that match code (e.g. classification labels, `datos/`).

## Commands

```bash
# Setup (uv is the package manager)
uv venv
source .venv/bin/activate            # Linux/macOS  (Windows: .venv\Scripts\activate)
uv sync --frozen                     # production deps from uv.lock
uv sync --frozen --group test        # add test deps

# Run the backend (development)
uvicorn ct.main:app --host 0.0.0.0 --port 8000 --reload

# Production runs as a systemd service (chatbot-api), NOT nohup. Operate it with:
sudo systemctl restart chatbot-api    # full restart (also used by CD on dependency changes)
sudo systemctl status chatbot-api
journalctl -u chatbot-api -f          # live logs

# Tests (config + markers live in pyproject.toml; HTML coverage -> htmlcov/)
uv run pytest tests/                 # full suite with coverage
uv run pytest tests/ --no-cov        # faster, no coverage
uv run pytest tests/ -m unit         # only the `unit` marker
uv run pytest tests/unit/test_x.py::test_name   # a single test

# Reporting dashboard (Streamlit)
streamlit run run_report.py --server.fileWatcherType none --server.port 3000

# ETL — rebuild the FAISS knowledge base
python -c "from ct.ETL.pipeline import update_products; update_products()"   # products (~every 2-3 months)
python -c "from ct.ETL.pipeline import update_sales; update_sales()"         # promotions (~monthly)
python -c "from ct.ETL.pipeline import update_all; update_all()"             # both

# Container
podman build -t proyecto-ct:latest .
```

## Deployment (CD)

CD is **pull-based (GitOps)**, not push: `deploy.sh` runs on the server via cron every 5 min,
`git fetch`es `origin/main`, validates the commit's CI (`gh api .../check-runs` using `GH_TOKEN`
from `.env`), then classifies changed files — `src/` → graceful reload (`pkill -HUP -f gunicorn`),
`pyproject.toml`/`uv.lock` → `uv sync --frozen` + `sudo systemctl restart chatbot-api`, docs/Quarto/UI
→ pull only, no restart. `datos/vectorstores/`, `static/ssl/`, and `.env` are gitignored so pulls
never touch FAISS data, certs, or secrets. Logs: `logs/deploy.log`. CI itself is
`.github/workflows/ci.yml` (pytest → Buildah image build).

An `.env` file is required before running (DB, OpenAI, MongoDB, and technical-spec service
credentials). See README.md for the full variable list.

## Architecture

The request flow spans several files and is the key thing to understand:

1. **API entry** — `src/ct/main.py` (FastAPI app) and `src/ct/chat.py` (chat endpoints,
   conversation history). Chat responses are streamed and async.
2. **Orchestrator** — `ModeratedToolAgent` (`src/ct/langchain/moderated_tool_agent.py`) is the
   main coordinator. For each query it:
   - calls `QueryModerator` (`src/ct/langchain/moderator_agent.py`), which uses GPT-4.1 to
     classify the query as `relevante`, `irrelevante`, or `inapropiado`;
   - if `relevante`, hands off to `ToolAgent` (`src/ct/langchain/tool_agent.py`), which runs an
     LLM with the tool set to build a RAG answer.
3. **Tools** (`src/ct/tools/`) connect the agent to data sources:
   - `search_information` — semantic search over the FAISS vector store (products/promotions);
   - `inventory` — prices/stock from MySQL;
   - `sales_rules_tool` — promotion and business rules;
   - `status` — order status from MongoDB; plus others (Algolia, image/PDF, currency, etc.).
4. **Data stores** — MongoDB (conversation history, sessions, metrics), MySQL (product/price
   master data), FAISS (similarity vectors, stored under `datos/vectorstores/`).
5. **ETL** (`src/ct/ETL/`) — `extraction.py` → `transform.py` → `load.py`, orchestrated by
   `pipeline.py`, builds the FAISS vector stores that `search_information` reads.

Cross-cutting concerns:

- **Token/cost tracking** — pricing per model in `settings/tokens.py`, callback handler in
  `settings/timing_tools.py`; each response records tokens, cost, duration, and model used.
- **Progressive ban system** — repeated `inapropiado` queries escalate via the
  `inappropriate_tries` / `banned_until` fields in MongoDB.

## Conventions

- Source lives under `src/ct/` (`package-dir` in `pyproject.toml`) — import as `ct.*`, not
  relative to repo root.
- Configuration is centralized: credentials/clients in `settings/clients.py`, runtime paths in
  `settings/config.py`, LLM prompts in `settings/prompt.py`, Pydantic models in `settings/schemas.py`.
- pytest markers: `unit`, `integration`, `slow`; `asyncio_mode = auto`. Coverage targets
  `src/ct` and **omits** `evaluation/`, `reportes/`, and `ETL/` (see `[tool.coverage.run]`).
- The LLM model is configurable (GPT-4.1, GPT-5 variants); pricing must be kept in sync in
  `settings/tokens.py`.

## API endpoints

- `POST /chat` — submit a user query; response is streamed.
- `GET /history/{user_id}` — fetch conversation history.
- `DELETE /history/{user_id}` — delete a user's history.
- `GET /logs/{msg_id}` — cost/timing log for a message.

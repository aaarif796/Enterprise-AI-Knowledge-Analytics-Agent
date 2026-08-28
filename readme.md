# 🧠 Enterprise AI Knowledge & Analytics Agent

A **production-grade, provider-agnostic, deployable** AI agent platform that answers questions across **three knowledge sources** — your documents (RAG / pgvector), your **analytics database** (PostgreSQL), and the **live web** — then scores every answer with an LLM-as-judge evaluator and returns **Confidence + Citations**.

**Cost-first by design:** it routes each task to the best *free* vendor/model (Ollama local, Groq free tier, OpenRouter `:free`), with automatic failover across vendors and Redis caching so repeated work never re-bills.

---

## 🏗️ Architecture

```
                         ┌─────────────────┐
                         │      User       │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │  Agent Router   │
                         │ / Orchestrator  │
                         └────────┬────────┘
                                  ↓
              ┌───────────────────┼───────────────────┐
              ↓                   ↓                   ↓
       ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
       │  RAG Agent  │     │  SQL Agent  │     │  Web Agent  │
       └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
              ↓                   ↓                   ↓
       ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
       │ pgvector    │     │ PostgreSQL  │     │ Web Search  │
       │ (in Postgres)│    └─────────────┘     └─────────────┘
       └──────┬──────┘            │                    │
              └────────────────────┼────────────────────┘
                                   ↓
                         ┌─────────────────┐
                         │   MCP Server    │
                         │  Tool Layer     │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │ Response Agent  │
                         └────────┬────────┘
                                  ↓
                         ┌─────────────────┐
                         │    Evaluator    │
                         └────────┬────────┘
                                  ↓
                  ┌───────────────┼───────────────┐
                  ↓               ↓               ↓
             Faithfulness     Relevance      Correctness
                  │               │               │
                  └───────────────┼───────────────┘
                                  ↓
                         ┌─────────────────┐
                         │ Final Response  │
                         │ + Confidence    │
                         │ + Citations     │
                         └─────────────────┘

### Key design decisions
| Concern | Choice |
|---|---|
| **Model Gateway (all vendors)** | LiteLLM — Ollama, Groq, OpenRouter, OpenAI, Anthropic, Gemini, DeepSeek, any OpenAI-compatible |
| **Task-aware routing** | `Model Router` picks the cheapest/free model per task + failover chain |
| **Vectors** | **pgvector** inside PostgreSQL (one DB for SQL analytics + RAG) |
| **Cache / sessions** | **Redis** (LLM cache, embedding cache, chat memory, rate-limit) |
| **Agents** | LangGraph-style Orchestrator → RAG / SQL / Web agents |
| **MCP tool layer** | Standardized tool registry (`vector_search`, `run_sql`, `web_search`) |
| **Evaluation** | LLM-as-judge: Faithfulness / Relevance / Correctness → Confidence |
| **Frontend** | React + Vite + TypeScript (chat, confidence gauge, citations, model picker) |
| **Deploy** | Docker Compose (backend + frontend + postgres/pgvector + redis + optional ollama) |

---

## 🗂️ Project structure

```
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── core/                   # config, logging, schemas, cache, gateway, router
│   │   ├── agents/                 # orchestrator, rag, sql, web agents
│   │   ├── services/               # vector_store(pgvector), sql_engine, web_search, response_agent, database
│   │   ├── evaluation/             # evaluator + metrics (LLM-as-judge)
│   │   ├── mcp/                    # MCP server + tool registry
│   │   └── api/                    # chat, health, config, ingest endpoints
│   ├── config/models.yaml          # ⭐ PROVIDER + TASK ROUTE TABLE (edit here)
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   └── src/                        # React chat UI (components, services, styles)
├── docker-compose.yml              # one-command deploy
└── .env.example
```


---

## 🚀 Quick start (Docker — recommended)

```bash
# 1. Copy env and add any API keys you want (optional; Ollama works with none)
cp .env.example .env

# 2. Optional: enable the bundled free local Ollama models
docker compose --profile full up --build

# Or without local Ollama (use cloud free tiers like Groq / OpenRouter):
docker compose up --build
```

Then open **http://localhost:8080**.

- Backend API: **http://localhost:8000** · Docs: **http://localhost:8000/docs**
- Redis: `localhost:6379` · PostgreSQL (pgvector): `localhost:5432`

---

## 🧪 Local development

### Backend (Python 3.12+)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows    (source .venv/bin/activate on Linux/mac)
pip install -r requirements.txt
uvicorn app.main:app --reload     # -> http://localhost:8000
```

> **Note:** This workspace runs Python 3.14 (bleeding edge). The requirements use
> minimum pins so pip resolves compatible builds. For a fully pinned/reproducible
> production image, use the provided Dockerfile (Python 3.12).

### Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev                        # -> http://localhost:5173 (proxies /api to :8000)
```

### Tests
```bash
cd backend
.venv\Scripts\python -m pytest tests/
```


---

## 🎯 Adding / switching a model (no code changes)

Everything lives in **`backend/config/models.yaml`**. To connect a new vendor, just
write the model name in the `providers` presets / `model_routes` table and add the key
in `.env`:

```yaml
providers:
  groq:
    llm_prefix: groq
    key_env: GROQ_API_KEY
```

```bash
# .env
GROQ_API_KEY=gsk_xxx
```

The smart **Model Router** then automatically uses the right (cheapest) model per task:

| Task | Route (default = free) | Fallback chain |
|---|---|---|
| `routing` (intent) | `groq/llama-3.1-8b-instant` | ollama → openrouter |
| `embedding` (RAG) | `ollama/nomic-embed-text` | openrouter |
| `sql_generation` | `openrouter/deepseek…:free` | groq → ollama |
| `rag_context` | `ollama/qwen2.5:7b` | groq |
| `web_summary` | `groq/llama-3.3-70b-versatile` | openrouter → ollama |
| `final_synth` | `openrouter/llama-3.3-70b:free` | groq → ollama |
| `evaluator` | `groq/llama-3.1-8b-instant` | openrouter → ollama |

You can also override any task's model at runtime from the **Model Picker** in the UI.

---

## 💰 Cost-saving features
- **Local-first:** default embeddings + RAG run on free local Ollama models.
- **Task-aware routing:** small/cheap models for routing & judging; strong free models only for final synthesis.
- **Redis cache:** identical queries/embeddings never re-bill.
- **Failover:** if a free tier rate-limits, it cascades to another free vendor.
- **All keys optional:** works 100% free with Ollama only.

## 🔌 API endpoints
- `GET  /`                  — health + service status
- `GET  /api/config`        — active providers, routes, available models
- `POST /api/chat`          — full agent pipeline (answer + confidence + citations)
- `POST /api/chat/stream`   — SSE streaming chat
- `POST /api/documents`     — ingest text into the RAG knowledge base (pgvector)
- `GET  /mcp/tools`         — MCP tool registry
- `POST /mcp/tools/call`    — invoke an MCP tool
- `GET  /mcp/tools/{name}`  — invoke a named tool

## 📄 License
MIT — see `LICENSE`.

```

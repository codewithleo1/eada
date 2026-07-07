# EADA — Progress Log

> Update this file at the end of each session. If a conversation with Claude ends unexpectedly, paste this entire file as the first message in a new chat to resume exactly where you left off.

---

## Project

Enterprise Autonomous Data Analyst (EADA) — multi-agent AI platform, built on a CPU-only laptop (i5-1334U, 8GB RAM) using only free tools.

- Repo: https://github.com/codewithleo1/eada
- Stack: FastAPI + LiteLLM (Gemini 2.5 Flash) + PostgreSQL + Redis + Qdrant + Langfuse, all via Docker Compose
- Environment: Windows + VS Code + PowerShell, package manager `uv`
- Python: 3.14
- Learning style: step-by-step, one file at a time, explanation before code, verify before moving on

---

## Status: Phase 0 ✅ Phase 1 ✅ Phase 2 ✅ Phase 3 ✅ Phase 4 ✅ Phase 5 ✅ Phase 6 ✅ Phase 7 ✅ Phase 8 ✅ Phase 9 ✅ — ALL PHASES COMPLETE 🎉

---

## Completed Phases

### Phase 0 — Foundation ✅ COMPLETE
- `uv` project initialized, dependencies installed, folder structure created
- `backend/config.py` — flat Pydantic Settings class reading from `.env`
- `backend/observability/logging.py` — structlog structured JSON logging
- `backend/observability/tracing.py` — Langfuse v2.60.0 tracing wrapper
- `backend/llm/gateway.py` — LiteLLM gateway (Gemini 2.5 Flash primary, Groq fallback, stream=True)
- `backend/api/routes/health.py` — `/health/live` and `/health/ready` endpoints
- `docker-compose.yml` — PostgreSQL, Redis, Qdrant, Langfuse all via Docker Compose
- `infra/postgres/init-multi-db.sh` — creates `eada_app` DB separate from Langfuse's `eada` DB
- `.github/workflows/ci.yml` — GitHub Actions CI (ruff lint + pytest, Python 3.14, green)
- Dependencies: `fastapi`, `uvicorn`, `litellm`, `langfuse==2.60.0`, `structlog`, `pydantic-settings`

### Phase 1 — Simple Chat Interface ✅ COMPLETE
- `backend/db/models.py` — SQLAlchemy async ORM: `User`, `Conversation`, `Message` tables
- `backend/db/session.py` — async engine + session factory pointing to `eada_app` DB
- `backend/db/migrations/` — Alembic async migrations (env.py rewritten for asyncpg)
- `backend/db/repositories.py` — `UserRepository`, `ConversationRepository`, `MessageRepository`
- `backend/api/routes/auth.py` — `POST /auth/register` and `POST /auth/token` (real DB, argon2 hashing)
- `backend/api/routes/chat.py` — persistent multi-turn WebSocket
- `backend/api/routes/conversations.py` — `GET /conversations` and `GET /conversations/{id}`
- `backend/api/deps.py` — FastAPI dependency injection
- `frontend/` — Vite + React + TypeScript + Tailwind CSS
- Dependencies: `sqlalchemy`, `asyncpg`, `alembic`, `python-jose`, `passlib[argon2]`, `argon2-cffi`, `redis`

### Phase 2 — Data File Analysis ✅ COMPLETE
- `backend/tools/file_tool.py` — reads CSV, Excel, JSON, Parquet; extracts schema + sample rows
- `backend/tools/sql_tool.py` — executes DuckDB SQL in-process against uploaded files
- `backend/api/routes/upload.py` — `POST /upload` endpoint
- Dependencies: `duckdb==1.5.4`, `pandas==3.0.3`, `openpyxl`, `python-multipart`

### Phase 3 — RAG Pipeline ✅ COMPLETE
- `backend/rag/chunker.py` — splits PDF/DOCX/TXT/MD into overlapping chunks
- `backend/rag/embedder.py` — embeds text via Google `gemini-embedding-001` (3072 dim)
- `backend/rag/vector_store.py` — Qdrant upsert + `query_points()` search
- `backend/rag/rag_pipeline.py` — orchestrates ingest and retrieve flows
- `backend/api/routes/ingest.py` — `POST /ingest` endpoint
- Dependencies: `qdrant-client==1.18.0`, `pymupdf==1.28.0`, `python-docx==1.2.0`

### Phase 4 — Tool Calling & MCP ✅ COMPLETE
- `backend/tools/registry.py` — tool catalogue; `get_tools_for_context(has_file, has_doc)`
- `backend/tools/executor.py` — tool router; maps LLM tool calls to real Python functions
- `backend/llm/gateway.py` — added `ToolCallRequest`, `ToolCallResponse`, `complete_with_tools()`
- `backend/mcp/server.py` — MCP HTTP server; `/mcp/tools`, `/mcp/tools/call`, `/mcp/health`
- Unit tests: 33 passing

### Phase 5 — Full Agent Architecture ✅ COMPLETE
- `backend/agents/state.py` — `AgentState` TypedDict; all agent fields
- `backend/agents/router.py` — LLM-based routing
- `backend/agents/planner.py` — multi-step planner
- `backend/agents/analyst.py` — data analyst agent with tool loop
- `backend/agents/rag_agent.py` — RAG document agent
- `backend/agents/critic.py` — critic + summarizer agents
- `backend/agents/graph.py` — LangGraph compiled graph
- `backend/api/routes/chat.py` — uses `agent_graph.ainvoke()`
- Dependencies: `langgraph==1.2.2`
- Graph flow: START → router → [analyst|rag_agent|planner|summarizer] → critic → summarizer → END

### Phase 6 — Multi-Agent Collaboration & Self-Correction ✅ COMPLETE
- `backend/agents/state.py` — added `retry_count`, `originating_agent`, `conversation_id` fields
- `backend/agents/graph.py` — added `route_after_critic()` self-correction conditional edge
- `backend/agents/analyst.py` — writes `originating_agent`, `retry_count`; uses critique on retry
- `backend/agents/rag_agent.py` — writes `originating_agent`, `retry_count`; uses critique on retry
- `backend/memory/agent_memory.py` — Redis-backed key-value memory; namespaced by conversation_id
- `backend/evaluation/scorer.py` — LLM-based response scorer (Relevance 40%, Completeness 40%, Clarity 20%)
- `backend/api/routes/chat.py` — passes `conversation_id` into agent graph
- New unit tests: `test_scorer.py` (13), `test_agent_memory.py` (11), `test_graph.py` (11)
- Total unit tests: 68 passing

### Phase 7 — Interactive Dashboard ✅ COMPLETE
- `frontend/src/api.ts` — added `doc_id`, `ingestDocument()`, updated `buildWebSocketUrl()`
- `frontend/src/components/Sidebar.tsx` — conversation history list, new conversation button, active highlight
- `frontend/src/components/AgentStatus.tsx` — animated ping dot showing which agent is running
- `frontend/src/Chat.tsx` — wires sidebar + agent status + both upload types (📊 data, 📄 doc)
- `frontend/src/App.tsx` — simplified props passed to Chat
- `backend/api/routes/chat.py` — switched to `astream_events(version="v2")` to emit `{"type":"agent","value":"..."}` WebSocket messages per node start
- Total unit tests: 68 passing (no new tests needed — frontend only + backend streaming change)

### Phase 8 — Production Deployment ✅ COMPLETE
- `backend/Dockerfile` — two-stage build: uv + python:3.12-slim builder, lean runtime
- `frontend/Dockerfile` — node:20-alpine builds Vite app, nginx:alpine serves dist/
- `infra/nginx/nginx.conf` — reverse proxy: /api/ → backend, /ws/ → WebSocket, / → frontend
- `docker-compose.prod.yml` — full 7-container stack with healthchecks + restart policies
- `backend/config.py` — added ALLOWED_ORIGINS + allowed_origins_list property
- `backend/main.py` — CORS driven by config instead of hardcoded origins
- `.dockerignore` — excludes node_modules, .venv, uploads from build context
- `.github/workflows/ci.yml` — added docker-build job pushing to GHCR on main
- Total unit tests: 68 passing (no new tests — infrastructure phase)

### Phase 9 — Capstone Polish ✅ COMPLETE
- `README.md` — full project documentation with architecture, stack, quick start
- `frontend/src/Auth.tsx` — modern gradient login page (Claude/ChatGPT style)
- `frontend/src/Chat.tsx` — full redesign: welcome screen, suggestion chips, message avatars, thinking dots, auto-resize textarea, Shift+Enter support
- `frontend/src/components/Sidebar.tsx` — grouped by Today/Yesterday, Sign Out at bottom, loads on mount
- `frontend/src/components/AgentStatus.tsx` — colored pills per agent type
- `backend/config.py` — added `qdrant_url` setting
- `backend/rag/vector_store.py` — uses `settings.qdrant_url` instead of hardcoded localhost
- `infra/nginx/nginx.conf` — added `client_max_body_size 50m` for large file uploads
- `test_data/` — sample products.csv, sales.csv, company_report.txt for demos
- `.github/workflows/ci.yml` — updated to Python 3.12 to match Docker
- Total unit tests: 68 passing

---

## Current Folder Structure

EADA/
├── .github/workflows/ci.yml
├── backend/
│   ├── main.py                     ← 7 routers registered
│   ├── config.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── router.py
│   │   ├── planner.py
│   │   ├── analyst.py
│   │   ├── rag_agent.py
│   │   ├── critic.py
│   │   └── graph.py
│   ├── api/routes/
│   │   ├── auth.py
│   │   ├── chat.py                 ← astream_events + agent activity WebSocket events
│   │   ├── conversations.py
│   │   ├── health.py
│   │   ├── ingest.py
│   │   └── upload.py
│   ├── db/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── session.py
│   │   └── migrations/
│   ├── evaluation/
│   │   ├── __init__.py
│   │   └── scorer.py
│   ├── llm/gateway.py
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── server.py
│   ├── memory/
│   │   ├── __init__.py
│   │   └── agent_memory.py
│   ├── observability/
│   │   ├── logging.py
│   │   └── tracing.py
│   ├── rag/
│   │   ├── chunker.py
│   │   ├── embedder.py
│   │   ├── rag_pipeline.py
│   │   └── vector_store.py
│   ├── tools/
│   │   ├── executor.py
│   │   ├── file_tool.py
│   │   ├── registry.py
│   │   └── sql_tool.py
│   └── tests/unit/
│       ├── test_health.py
│       ├── test_registry.py
│       ├── test_executor.py
│       ├── test_gateway.py
│       ├── test_scorer.py
│       ├── test_agent_memory.py
│       └── test_graph.py
├── frontend/src/
│   ├── components/
│   │   ├── AgentStatus.tsx
│   │   └── Sidebar.tsx
│   ├── App.tsx
│   ├── Auth.tsx
│   ├── Chat.tsx
│   ├── api.ts
│   ├── index.css
│   └── main.tsx
├── infra/postgres/init-multi-db.sh
├── uploads/.gitkeep
├── test_data.csv
├── test_e2e_phase4.py
├── .env
├── alembic.ini
├── docker-compose.yml
├── PROGRESS.md
├── pyproject.toml
└── uv.lock

---

## How to resume local dev environment after a break

```powershell
# 1. Reload uv PATH
$env:Path = "C:\Users\suraj\.local\bin;$env:Path"

# 2. Start Docker Desktop manually (GUI), wait for it to be ready

# 3. Start infra
docker compose up -d
docker compose ps

# 4. Start backend
uv run uvicorn backend.main:app --reload

# 5. Start frontend (separate terminal)
cd frontend
npm run dev
```

---

## Service URLs reference

| Service | URL |
|---|---|
| Backend API docs | http://localhost:8000/docs |
| Langfuse UI | http://localhost:3000 |
| Qdrant dashboard | http://localhost:6333/dashboard |
| Frontend | http://localhost:5173 |

---

## Key gotchas (never repeat these)

1. **Langfuse SDK version**: pin to `langfuse==2.60.0` exactly
2. **bcrypt broken on Python 3.14** → use argon2
3. **Pydantic Settings**: single flat `Settings` class only
4. **`.gitignore` pattern**: use `/test_*.py` not `test_*.py`
5. **Shared Postgres DB**: Langfuse uses `eada`, app uses `eada_app`
6. **Docker init script**: must have LF line endings, not CRLF
7. **uv PATH**: run `$env:Path = "C:\Users\suraj\.local\bin;$env:Path"` every new terminal
8. **Docker Desktop**: must be started manually after system restart
9. **frontend npm commands**: must be run from inside `frontend/` folder
10. **DuckDB + CSV encoding**: use pandas bridge via `_execute_on_file`
11. **Excel files**: DuckDB can't read `.xlsx` natively — go through pandas
12. **Google embeddings via LiteLLM**: call Google REST API directly
13. **Gemini embedding model**: use `gemini-embedding-001` (3072 dim)
14. **Qdrant client 1.18.0**: use `.query_points()` not `.search()`
15. **auth/register returns 201** not 200
16. **auth/token expects JSON** not form data
17. **pytest discovery**: requires `[tool.pytest.ini_options]` in pyproject.toml
18. **New files via PowerShell**: use `New-Item` first, then `Set-Content -Encoding UTF8`
19. **PowerShell**: does not support `&&` — run commands separately
20. **LangGraph state**: must be `TypedDict` not Pydantic; use `Annotated[list, operator.add]` for append-only fields
21. **LangGraph compile**: always call `graph.compile()` — validates all edges and node signatures
22. **ruff unused imports**: always fix with `uv run ruff check --fix` before committing
23. **Self-correction loop**: `retry_count` increments in analyst/rag_agent on every run — circuit breaker MAX_RETRIES=2
24. **AgentMemory**: Redis failure is non-fatal — always returns None on error, never raises
25. **astream_events version**: always pass `version="v2"` — v1 is deprecated in LangGraph 1.2+
26. **Agent node names in events**: LangGraph fires `on_chain_start` with `name` = node function name — must match exactly: `router`, `planner`, `analyst`, `rag_agent`, `critic`, `summarizer`
27. **uv.lock pins Python version**: changing `requires-python` in pyproject.toml also requires `uv lock` to regenerate lockfile
28. **PowerShell Set-Content -Encoding UTF8 writes BOM**: Nginx and pytest reject BOM; always use `[System.IO.File]::WriteAllText` with `UTF8Encoding($false)` for config files
29. **qdrant/qdrant image has no curl or wget**: use TCP check: `timeout 1 bash -c 'cat < /dev/null > /dev/tcp/localhost/6333'`
30. **python:3.12-slim has no curl**: use Python one-liner for healthcheck: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"`
31. **prod .env needs extra vars**: POSTGRES_USER, POSTGRES_PASSWORD, LANGFUSE_SALT required by docker-compose.prod.yml — dev compose didn't need them
32. **Frontend API_BASE must be relative in production** — use `window.location.origin + "/api"` not hardcoded `http://localhost:8000`
33. **WebSocket URL must go through Nginx** — use `ws://${window.location.host}/ws/chat/ws` not `ws://localhost:8000/chat/ws`
34. **Nginx proxy_pass path doubling** — `location /ws/chat/ws { proxy_pass http://backend:8000/chat/ws; }` is the correct pattern; avoid trailing slashes that cause path concatenation
35. **Groq llama-3.1-70b-versatile decommissioned** — use `llama-3.3-70b-versatile` instead
36. **docker compose restart does not reload .env** — use `docker compose up -d <service>` to recreate the container with new env vars
37. **Gemini free tier limit is 20 requests/day** — get a paid key or use Groq as primary for heavy testing
38. **Qdrant URL hardcoded**: vector_store.py had localhost:6333 hardcoded — always use settings.qdrant_url so prod uses container name
39. **Nginx default upload limit is 1MB**: add `client_max_body_size 50m` for file upload endpoints
40. **Sidebar useEffect**: must have two hooks — one with [] for initial load, one with [activeConversationId] for refresh

---

## Roadmap reminder (9 phases, 26 weeks total)

Phase 0 — Foundation                    ✅ DONE
Phase 1 — Simple Chat Interface         ✅ DONE
Phase 2 — Data File Analysis            ✅ DONE
Phase 3 — RAG Pipeline                  ✅ DONE
Phase 4 — Tool Calling & MCP            ✅ DONE
Phase 5 — Full Agent Architecture       ✅ DONE
Phase 6 — Multi-Agent Collaboration     ✅ DONE
Phase 7 — Interactive Dashboard         ✅ DONE
Phase 8 — Production Deployment         ✅ DONE
Phase 9 — Capstone Polish               ✅ DONE

---

*Last updated: Phase 9 complete — modern Claude-style UI, full production stack, all features working. 68 unit tests passing. Project complete!*
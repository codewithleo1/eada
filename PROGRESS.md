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

## Status: Phase 0 ✅ Phase 1 ✅ Phase 2 ✅ Phase 3 ✅ — Phase 4 Tool Calling NEXT

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
- `backend/api/routes/chat.py` — persistent multi-turn WebSocket; full history sent to Gemini every turn
- `backend/api/routes/conversations.py` — `GET /conversations` and `GET /conversations/{id}`
- `backend/api/deps.py` — FastAPI dependency injection for DB sessions and repositories
- `frontend/` — Vite + React + TypeScript + Tailwind CSS
- `frontend/src/Auth.tsx` — login/register screen
- `frontend/src/Chat.tsx` — streaming chat UI with WebSocket client
- `frontend/src/App.tsx` — session persistence via localStorage
- `frontend/src/api.ts` — centralized API client (axios + WebSocket URL builder)
- Dependencies: `sqlalchemy`, `asyncpg`, `alembic`, `python-jose`, `passlib[argon2]`, `argon2-cffi`, `redis`

### Phase 2 — Data File Analysis ✅ COMPLETE
- `backend/tools/file_tool.py` — reads CSV, Excel, JSON, Parquet; extracts schema + sample rows
- `backend/tools/sql_tool.py` — executes DuckDB SQL in-process against uploaded files
- `backend/api/routes/upload.py` — `POST /upload` endpoint; saves with UUID filename, returns file_id + schema
- `backend/api/routes/chat.py` — updated WebSocket; detects file_id, injects schema, extracts SQL, executes via DuckDB, streams results + summary
- `frontend/src/Chat.tsx` — file upload button (📎), file badge, file_id passed as WebSocket param
- `frontend/src/api.ts` — `uploadFile()` function, `UploadResponse` interface, updated `buildWebSocketUrl()`
- Dependencies: `duckdb==1.5.4`, `pandas==3.0.3`, `openpyxl`, `python-multipart`

### Phase 3 — RAG Pipeline ✅ COMPLETE
- `backend/rag/chunker.py` — splits PDF/DOCX/TXT/MD into overlapping chunks (1500 chars, 200 overlap)
- `backend/rag/embedder.py` — embeds text via Google `gemini-embedding-001` (3072 dim, direct REST API)
- `backend/rag/vector_store.py` — stores and searches chunks in Qdrant using `query_points()` (v1.18.0+)
- `backend/rag/rag_pipeline.py` — orchestrates ingest and retrieve flows
- `backend/api/routes/ingest.py` — `POST /ingest` endpoint; chunks, embeds, stores in Qdrant; returns `doc_id`
- `backend/api/routes/chat.py` — updated WebSocket; accepts `doc_id` param, retrieves relevant chunks, injects as LLM context
- Dependencies: `qdrant-client==1.18.0`, `pymupdf==1.28.0`, `python-docx==1.2.0`

---

## Current Folder Structure

EADA/
├── .github/
│   └── workflows/
│       └── ci.yml                  ← ruff + pytest, Python 3.14
├── backend/
│   ├── init.py
│   ├── main.py                     ← FastAPI app, 6 routers registered
│   ├── config.py                   ← flat Settings class, reads .env
│   ├── api/
│   │   ├── deps.py                 ← get_current_user, repo dependencies
│   │   ├── middleware/
│   │   │   ├── auth.py             ← JWT verify
│   │   │   └── rate_limit.py       ← Redis rate limiting
│   │   └── routes/
│   │       ├── auth.py             ← POST /auth/register, /auth/token
│   │       ├── chat.py             ← WebSocket /chat/ws (file_id + doc_id support)
│   │       ├── conversations.py    ← GET /conversations, /conversations/{id}
│   │       ├── health.py           ← GET /health
│   │       ├── ingest.py           ← POST /ingest (RAG document ingestion)
│   │       └── upload.py           ← POST /upload (CSV/Excel/JSON/Parquet)
│   ├── agents/
│   │   └── init.py             ← empty, Phase 5
│   ├── db/
│   │   ├── models.py               ← users, conversations, messages
│   │   ├── repositories.py         ← UserRepo, ConversationRepo, MessageRepo
│   │   ├── session.py              ← async SQLAlchemy session
│   │   └── migrations/             ← Alembic async migrations
│   ├── llm/
│   │   ├── gateway.py              ← LiteLLM wrapper, Gemini + Groq fallback
│   │   └── prompts/
│   │       └── init.py
│   ├── observability/
│   │   ├── logging.py              ← structlog setup
│   │   └── tracing.py              ← Langfuse tracing
│   ├── rag/
│   │   ├── chunker.py              ← PDF/DOCX/TXT/MD → overlapping chunks
│   │   ├── embedder.py             ← Google gemini-embedding-001 (3072 dim)
│   │   ├── rag_pipeline.py         ← ingest + retrieve orchestration
│   │   └── vector_store.py         ← Qdrant upsert + query_points search
│   ├── tools/
│   │   ├── file_tool.py            ← parse CSV/Excel/JSON/Parquet, extract schema
│   │   └── sql_tool.py             ← DuckDB query execution
│   ├── memory/
│   │   └── init.py             ← empty, Phase 5
│   ├── evaluation/
│   │   └── init.py             ← empty, Phase 5
│   └── tests/
│       ├── unit/
│       │   └── test_health.py
│       └── integration/
│           └── init.py
├── frontend/
│   └── src/
│       ├── App.tsx                 ← token state, login/chat routing
│       ├── Auth.tsx                ← login + register UI
│       ├── Chat.tsx                ← streaming chat + file upload button (📎)
│       ├── api.ts                  ← axios client, uploadFile(), buildWebSocketUrl()
│       ├── index.css               ← Tailwind import
│       └── main.tsx
├── infra/
│   └── postgres/
│       └── init-multi-db.sh        ← creates eada + eada_app databases
├── uploads/                        ← temp file storage (gitignored)
│   └── .gitkeep
├── .env                            ← secrets (never committed)
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml              ← postgres, redis, qdrant, langfuse
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
docker compose ps   # confirm all 4 services healthy/running

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
| Frontend (once running) | http://localhost:5173 |

---

## Key gotchas (never repeat these)

1. **Langfuse SDK version**: pin to `langfuse==2.60.0` exactly
2. **bcrypt broken on Python 3.14** → use argon2
3. **Pydantic Settings**: single flat `Settings` class only — no nested sub-settings
4. **`.gitignore` pattern**: use `/test_*.py` not `test_*.py`
5. **Shared Postgres DB**: Langfuse uses `eada`, app uses `eada_app` — never share them
6. **Docker init script**: must have LF line endings, not CRLF
7. **uv PATH**: run `$env:Path = "C:\Users\suraj\.local\bin;$env:Path"` every new terminal
8. **Docker Desktop**: must be started manually after system restart
9. **frontend npm commands**: must be run from inside `frontend/` folder
10. **DuckDB + CSV encoding**: PowerShell `Set-Content` writes UTF-8 BOM — use pandas bridge via `_execute_on_file`
11. **Excel files**: DuckDB can't read `.xlsx` natively — always go through pandas → DuckDB view
12. **Google embeddings via LiteLLM**: LiteLLM does NOT support `gemini/text-embedding-*` — call Google REST API directly
13. **Gemini embedding model**: `text-embedding-004` not available on free API keys — use `gemini-embedding-001` (3072 dim)
14. **Qdrant client 1.18.0**: `.search()` removed — use `.query_points()` instead

---

## Roadmap reminder (9 phases, 26 weeks total)

Phase 0 — Foundation                    ✅ DONE
Phase 1 — Simple Chat Interface         ✅ DONE
Phase 2 — Data File Analysis            ✅ DONE
Phase 3 — RAG Pipeline                  ✅ DONE
Phase 4 — Tool Calling & MCP            ⏭️ NEXT
Phase 5 — Full Agent Architecture (LangGraph, 8 specialized agents)
Phase 6 — Multi-Agent Collaboration & Self-Correction
Phase 7 — Interactive Dashboard (proper React frontend, auth, projects)
Phase 8 — Production Deployment
Phase 9 — Capstone Polish

---

*Last updated: Phase 3 complete — RAG pipeline with Qdrant + Google embeddings working end-to-end. Next: Phase 4 Tool Calling & MCP.*
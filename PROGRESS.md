# EADA — Progress Log

> Update this file at the end of each session. If a conversation with Claude ends unexpectedly, paste this entire file as the first message in a new chat to resume exactly where you left off.

---

## Project

Enterprise Autonomous Data Analyst (EADA) — multi-agent AI platform, built on a CPU-only laptop (i5-1334U, 8GB RAM) using only free tools.

- Repo: https://github.com/codewithleo1/eada
- Stack: FastAPI + LangGraph + LiteLLM (Gemini 2.5 Flash) + PostgreSQL + Redis + Qdrant + Langfuse, all via Docker Compose
- Environment: Windows + VS Code + PowerShell, package manager `uv`
- Learning style: step-by-step, one file at a time, explanation before code, verify before moving on

---

## Status: Phase 0 complete, Phase 1 in progress (frontend underway)

### Phase 0 — Foundation (Days 1–5) ✅ COMPLETE
- Day 1: uv scaffold, folder structure, dependencies
- Day 2: LiteLLM gateway, streaming WebSocket chat endpoint
- Day 3: Docker stack (Postgres, Redis, Qdrant, Langfuse) + tracing wired in
- Day 4: JWT auth + Redis rate limiting
- Day 5: GitHub repo live, CI/CD via GitHub Actions (ruff + pytest), all green

### Phase 1 — Simple Chat Interface (Weeks 3–4)
**Backend: COMPLETE**
- PostgreSQL schema: `users`, `conversations`, `messages` (isolated in `eada_app` DB — NOT the same DB as Langfuse, which uses `eada`)
- SQLAlchemy async models (`backend/db/models.py`)
- Alembic migrations configured for async (`backend/db/migrations/env.py` rewritten for async engine)
- Repository layer (`backend/db/repositories.py`) — `UserRepository`, `ConversationRepository`, `MessageRepository`
- Real user registration (`POST /auth/register`) and login (`POST /auth/token`) — replaced old fake in-memory user dict
- `/chat/ws` now persists every message, supports resuming via `?conversation_id=`, sends full history to Gemini every turn (true multi-turn memory) — verified working via direct DB query
- `GET /conversations` and `GET /conversations/{id}` — tested live via Swagger UI, working

**Frontend: IN PROGRESS — left off here**
- Just ran `npm create vite@latest frontend -- --template react-ts` inside project root
- Chose: ESLint (not oxlint), said yes to install + start immediately
- **Next step when resuming:** confirm the Vite dev server started correctly (should show a localhost URL, typically `http://localhost:5173`), then continue with:
  1. Install Tailwind CSS in `frontend/`
  2. Build login/register screen
  3. Build chat interface (message list + input box)
  4. Wire up WebSocket client to `ws://localhost:8000/chat/ws`
  5. End-to-end test: register → login → send message → see streaming response → refresh and confirm history persists

---

## Key gotchas hit and fixed (don't repeat these)

1. **Langfuse SDK version**: must be `langfuse==2.60.0` exactly. v3/v4 break self-hosted (different API, OTLP endpoints that don't exist on self-hosted v2 server).
2. **bcrypt + passlib broken on Python 3.14** → switched to `argon2` (`pwd_context = CryptContext(schemes=["argon2"])`).
3. **Pydantic Settings**: must use a single flat `Settings` class in `config.py` — nested settings classes (e.g. `LLMSettings`, `LangfuseSettings` as sub-objects) don't inherit `env_file` config properly.
4. **`.gitignore` pattern `test_*.py`** was too broad and silently excluded real tests in `backend/tests/`. Fixed by anchoring to root: `/test_*.py`.
5. **Shared Postgres DB with Langfuse**: original docker-compose had both the app and Langfuse pointed at the same `eada` database — caused Alembic to try to delete Langfuse's tables. Fixed via `infra/postgres/init-multi-db.sh` which creates a second `eada_app` database on container init. App's `.env` `DATABASE_URL` now points to `eada_app`, Langfuse keeps `eada`.
6. **Docker init script accidentally created as a directory** (`New-Item -ItemType File` silently failed) — always verify with `Get-Item <path>` after creating shell scripts on Windows; also must save with LF line endings, not CRLF, or Linux containers can't execute them.
7. **uv PATH**: after every fresh terminal/VS Code restart, must run `$env:Path = "C:\Users\suraj\.local\bin;$env:Path"` before `uv` commands work.
8. **Docker Desktop must be manually started** after a system restart before `docker compose up` will work.

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

# 5. (once frontend exists) in a separate terminal:
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

## Roadmap reminder (9 phases, 26 weeks total)

```
Phase 0 — Foundation                    ✅ DONE
Phase 1 — Simple Chat Interface          🔶 IN PROGRESS (backend done, frontend started)
Phase 2 — Data File Analysis (CSV, Excel, PDF, SQL via DuckDB)
Phase 3 — RAG Pipeline (Qdrant, embeddings, hybrid search)
Phase 4 — Tool Calling & MCP
Phase 5 — Full Agent Architecture (LangGraph, 8 specialized agents)
Phase 6 — Multi-Agent Collaboration & Self-Correction
Phase 7 — Interactive Dashboard (proper React frontend, auth, projects)
Phase 8 — Production Deployment
Phase 9 — Capstone Polish
```

---

*Last updated: mid-Phase-1, frontend scaffold just initiated, awaiting Vite dev server confirmation.*

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

## Status: Phase 0 ✅ Phase 1 ✅ Phase 2 backend ✅ — Frontend wiring NEXT

### Phase 0 — Foundation ✅ COMPLETE
### Phase 1 — Simple Chat Interface ✅ COMPLETE
### Phase 2 — Data File Analysis ✅ BACKEND COMPLETE, frontend pending

**Backend complete:**
- `backend/tools/file_tool.py` — reads CSV, Excel, JSON, Parquet; extracts schema + sample rows
- `backend/tools/sql_tool.py` — executes DuckDB SQL in-process against uploaded files
- `backend/api/routes/upload.py` — `POST /upload` endpoint; saves with UUID filename, returns file_id + schema
- `backend/api/routes/chat.py` — updated WebSocket; detects file_id, injects schema into system prompt, extracts SQL from LLM response, executes via DuckDB, streams results + plain-English summary
- Dependencies added: `duckdb==1.5.4`, `pandas==3.0.3`, `openpyxl`, `python-multipart`
- `uploads/` directory created and gitignored

**Verified end-to-end:**
- Upload CSV → get file_id + schema ✅
- WebSocket chat with file_id → LLM writes SQL → DuckDB executes → results streamed → summary generated ✅

**Frontend: NEXT — wire file upload button into React chat UI**
- Add file upload button to `Chat.tsx`
- Call `POST /upload` when user selects a file
- Store `file_id` in component state
- Pass `file_id` as WebSocket query param when connecting
- Show file name + column count as a badge in the chat header

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
10. **DuckDB + CSV encoding**: PowerShell `Set-Content` writes UTF-8 BOM which breaks DuckDB sniffer — use pandas bridge via `_execute_on_file` (loads via pandas, registers as DuckDB view called `data`)
11. **Excel files**: DuckDB can't read `.xlsx` natively — always go through pandas → DuckDB view

---

## Roadmap reminder (9 phases, 26 weeks total)
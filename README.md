# EADA — Enterprise Autonomous Data Analyst

A multi-agent AI platform that autonomously analyses data files and documents using a self-correcting agent graph, built entirely with free tools on a CPU-only laptop.

## Features

- **Multi-agent architecture** — Router, Planner, Analyst, RAG, Critic, and Summarizer agents collaborate via LangGraph
- **Data file analysis** — Upload CSV, Excel, JSON, or Parquet files and query them in natural language
- **Document Q&A** — Ingest PDF, DOCX, TXT files and ask questions via RAG pipeline
- **Self-correction** — Critic agent scores responses and retries up to 2 times if quality is low
- **Conversation memory** — Redis-backed memory persists context across turns
- **Observability** — Full tracing via Langfuse, structured JSON logging via structlog
- **Production-ready** — Dockerized stack with Nginx reverse proxy, healthchecks, and GHCR CI/CD

## Stack

| Layer | Technology |
|---|---|
| LLM | Gemini 2.5 Flash (primary), Groq LLaMA 3.3 70B (fallback) |
| Agent Framework | LangGraph 1.2 |
| Backend | FastAPI + uvicorn |
| Database | PostgreSQL 16 (asyncpg + SQLAlchemy) |
| Vector Store | Qdrant 1.13 |
| Cache / Memory | Redis 7 |
| Observability | Langfuse + structlog |
| Frontend | Vite + React + TypeScript + Tailwind CSS |
| Infra | Docker Compose + Nginx |
| CI/CD | GitHub Actions + GHCR |

## Quick Start

### Prerequisites
- Docker Desktop
- A Gemini API key from https://aistudio.google.com/apikey

### 1. Clone the repo

git clone https://github.com/codewithleo1/eada.git
cd eada

### 2. Configure environment

cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

### 3. Start the full stack

docker compose -f docker-compose.prod.yml up --build -d

### 4. Open the app

Visit http://localhost — register a new account on first run.

## Development Setup (Windows)

`powershell
$env:Path = "C:\Users\<you>\.local\bin;$env:Path"
docker compose up -d
uv run uvicorn backend.main:app --reload
# In a separate terminal:
cd frontend
npm run dev
`powershell

## Running Tests

uv run pytest backend/tests/ -v

68 unit tests covering agent graph routing, tool execution, LLM gateway, Redis memory, and response scoring.

## Project Structure

backend/agents/ — LangGraph agent nodes
backend/api/routes/ — FastAPI endpoints
backend/db/ — SQLAlchemy models and Alembic migrations
backend/llm/ — LiteLLM gateway with fallback
backend/memory/ — Redis-backed agent memory
backend/rag/ — Chunker, embedder, Qdrant vector store
backend/tools/ — DuckDB SQL tool, file schema tool
backend/evaluation/ — LLM-based response scorer
frontend/src/ — Vite + React + TypeScript chat UI
infra/ — Nginx config, Postgres init script

## License

MIT
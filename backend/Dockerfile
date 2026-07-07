# Stage 1: dependency installer
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Force uv to use the system Python 3.12 instead of downloading 3.14
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3

# Stage 2: runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY backend/ ./backend/

ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
# ── Stage 1: dependency installer ──────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only dependency files first — this layer is cached until they change
COPY pyproject.toml uv.lock ./

# Install dependencies into a venv inside /app/.venv
# --frozen: use exact versions from uv.lock
# --no-dev: skip pytest, ruff — not needed at runtime
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime image ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the installed venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY backend/ ./backend/

# Make the venv's Python the default
ENV PATH="/app/.venv/bin:$PATH"

# Create uploads directory (volume will be mounted here in compose)
RUN mkdir -p /app/uploads

# Expose the port uvicorn will listen on
EXPOSE 8000

# Run uvicorn in production mode
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

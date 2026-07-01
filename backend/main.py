from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.observability.logging import setup_logging, get_logger
from backend.observability.tracing import tracer
from backend.api.routes import chat, health, auth, conversations

# Setup logging immediately — before anything else
setup_logging(debug=settings.app_debug)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events.
    
    Everything before 'yield' runs on startup.
    Everything after 'yield' runs on shutdown.
    """
    # Startup
    log.info("app_starting", env=settings.app_env)
    log.info("llm_config", primary=settings.primary_model)

    yield
    # Shutdown
    log.info("app_stopping")
    tracer.flush()  # Flush remaining Langfuse traces


app = FastAPI(
    title="Enterprise Autonomous Data Analyst",
    description="Multi-agent AI platform for autonomous data analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allows the React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)


@app.get("/")
async def root() -> dict:
    return {
        "name": "EADA API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
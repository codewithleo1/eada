from fastapi import APIRouter
from backend.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict:
    """Liveness probe — is the process alive?
    
    If this returns 200, the container is running.
    Docker and load balancers use this to decide whether
    to restart the container.
    """
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> dict:
    """Readiness probe — is the app ready to serve traffic?
    
    In later phases this will check database and Redis
    connectivity before returning healthy.
    """
    return {"status": "ready"}
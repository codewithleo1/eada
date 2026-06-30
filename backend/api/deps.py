from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Tells FastAPI to expect: Authorization: Bearer <token>
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Extract and verify the current user from the JWT token.

    FastAPI calls this automatically on every protected route.
    If token is missing or invalid, returns 401 before
    the route handler even runs.

    Returns:
        The token payload dict containing user_id
    """
    token = credentials.credentials
    payload = verify_token(token)
    return payload


def get_current_user_with_rate_limit(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Verify token AND check rate limit.

    Use this dependency on expensive endpoints like /chat
    that call external LLM APIs.
    """
    user_id = current_user.get("sub", "anonymous")
    check_rate_limit(user_id)
    return current_user
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from backend.api.middleware.auth import create_access_token, verify_password, hash_password
from backend.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ─── Temporary in-memory user store ───────────────────────────────────────────
# In Phase 7 we replace this with a real PostgreSQL users table.
# For now this lets us test auth without a database.
FAKE_USERS = {
    "suraj": {
        "user_id": "user_001",
        "username": "suraj",
        "hashed_password": hash_password("password123"),
    }
}


# ─── Request / Response Models ─────────────────────────────────────────────────
class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Routes ────────────────────────────────────────────────────────────────────
@router.post("/token", response_model=TokenResponse)
async def login(request: TokenRequest) -> TokenResponse:
    """Exchange username + password for a JWT access token.

    Flow:
        1. Look up user by username
        2. Verify password against stored hash
        3. Create signed JWT with user_id as subject
        4. Return token to client

    The client stores this token and sends it on every
    subsequent request as: Authorization: Bearer <token>
    """
    user = FAKE_USERS.get(request.username)

    if not user or not verify_password(request.password, user["hashed_password"]):
        log.warning("login_failed", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(data={"sub": user["user_id"]})
    log.info("login_success", username=request.username, user_id=user["user_id"])

    return TokenResponse(access_token=token)
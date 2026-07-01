from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from backend.api.middleware.auth import create_access_token, verify_password, hash_password
from backend.api.deps import get_user_repo
from backend.db.repositories import UserRepository
from backend.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Request / Response Models ─────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Routes ────────────────────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repo),
) -> TokenResponse:
    """Create a new user account and return an access token immediately.

    Flow:
        1. Check username isn't already taken
        2. Hash the password (never store plaintext)
        3. Persist the user to PostgreSQL
        4. Issue a JWT so the user is logged in right away
    """
    existing = await user_repo.get_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    hashed = hash_password(request.password)
    user = await user_repo.create(username=request.username, hashed_password=hashed)

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/token", response_model=TokenResponse)
async def login(
    request: TokenRequest,
    user_repo: UserRepository = Depends(get_user_repo),
) -> TokenResponse:
    """Exchange username + password for a JWT access token."""
    user = await user_repo.get_by_username(request.username)

    if not user or not verify_password(request.password, user.hashed_password):
        log.warning("login_failed", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(data={"sub": str(user.id)})
    log.info("login_success", username=request.username, user_id=str(user.id))

    return TokenResponse(access_token=token)
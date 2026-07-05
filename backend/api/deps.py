from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit
from backend.db.session import get_db_session
from backend.db.repositories import ConversationRepository, MessageRepository, UserRepository
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Tells FastAPI to expect: Authorization: Bearer <token>
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Extract and verify the current user from the JWT token."""
    token = credentials.credentials
    payload = verify_token(token)
    return payload


def get_current_user_with_rate_limit(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Verify token AND check rate limit."""
    user_id = current_user.get("sub", "anonymous")
    check_rate_limit(user_id)
    return current_user


def get_conversation_repo(
    db: AsyncSession = Depends(get_db_session),
) -> ConversationRepository:
    return ConversationRepository(db)


def get_message_repo(
    db: AsyncSession = Depends(get_db_session),
) -> MessageRepository:
    return MessageRepository(db)


def get_user_repo(
    db: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(db)
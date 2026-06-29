from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from backend.config import settings
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Password hashing context — bcrypt is the industry standard
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt.
    
    Never store plain passwords. Always store the hash.
    bcrypt is slow by design — makes brute force attacks impractical.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if a plain password matches its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token.
    
    Args:
        data: Payload to encode — typically {"sub": user_id}
        expires_delta: How long until the token expires
        
    Returns:
        Signed JWT string
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire

    token = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    log.info("token_created", subject=data.get("sub"), expires=expire.isoformat())
    return token


def verify_token(token: str) -> dict:
    """Verify a JWT token and return its payload.
    
    Raises HTTPException if token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload

    except JWTError as e:
        log.warning("token_verification_failed", error=str(e))
        raise credentials_exception
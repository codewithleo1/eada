import time
import redis
from fastapi import HTTPException, status
from backend.config import settings
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Redis client — synchronous is fine for rate limiting
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# Rate limit config
REQUESTS_PER_MINUTE = 60


def check_rate_limit(user_id: str) -> None:
    """Check if a user has exceeded their rate limit.
    
    Uses a sliding window counter in Redis.
    Key format: rate_limit:{user_id}:{current_minute}
    
    Each key expires after 2 minutes automatically.
    
    Raises HTTPException 429 if limit exceeded.
    """
    current_minute = int(time.time() // 60)
    key = f"rate_limit:{user_id}:{current_minute}"

    try:
        # Increment counter for this user in this minute
        count = redis_client.incr(key)

        # Set expiry on first request of the minute
        if count == 1:
            redis_client.expire(key, 120)  # expire after 2 minutes

        log.info("rate_limit_check", user_id=user_id, count=count, limit=REQUESTS_PER_MINUTE)

        if count > REQUESTS_PER_MINUTE:
            log.warning("rate_limit_exceeded", user_id=user_id, count=count)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {REQUESTS_PER_MINUTE} requests per minute.",
            )

    except HTTPException:
        raise
    except Exception as e:
        # If Redis is down, fail open — don't block the user
        log.error("rate_limit_redis_error", error=str(e))
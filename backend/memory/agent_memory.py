"""
agent_memory.py — Redis-backed key-value memory for EADA agents.

Stores key facts between conversation turns so agents don't repeat
expensive operations like file schema fetching on every message.

Keys are namespaced by conversation_id to isolate conversations.

Usage:
    memory = AgentMemory(conversation_id="uuid")
    await memory.remember("file_schema", schema_dict, ttl=3600)
    schema = await memory.recall("file_schema")
"""

from __future__ import annotations

import json
import redis.asyncio as aioredis

from backend.config import settings
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Default TTL — 1 hour. Schema and results expire after session ends.
DEFAULT_TTL = 3600


class AgentMemory:
    """
    Redis-backed memory for a single conversation session.

    All keys are namespaced as: eada:memory:{conversation_id}:{key}
    This ensures different conversations never share memory.
    """

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        """Lazy Redis connection — created on first use."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _make_key(self, key: str) -> str:
        """Build namespaced Redis key."""
        return f"eada:memory:{self.conversation_id}:{key}"

    async def remember(
        self,
        key: str,
        value: dict | list | str,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """
        Store a value in Redis under the given key.

        Args:
            key:   Short name for this memory (e.g. "file_schema", "sql_result")
            value: Any JSON-serialisable value
            ttl:   Time-to-live in seconds (default 1 hour)
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(key)
            serialised = json.dumps(value, default=str)
            await r.setex(redis_key, ttl, serialised)
            log.info("memory.stored", key=key, conversation=self.conversation_id)
        except Exception as e:
            # Memory failure is non-fatal — agents continue without it
            log.warning("memory.store_failed", key=key, error=str(e))

    async def recall(self, key: str) -> dict | list | str | None:
        """
        Retrieve a stored value from Redis.

        Returns None if key not found or Redis unavailable.
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(key)
            raw = await r.get(redis_key)
            if raw is None:
                log.info("memory.miss", key=key, conversation=self.conversation_id)
                return None
            log.info("memory.hit", key=key, conversation=self.conversation_id)
            return json.loads(raw)
        except Exception as e:
            log.warning("memory.recall_failed", key=key, error=str(e))
            return None

    async def forget(self, key: str) -> None:
        """Delete a specific memory key."""
        try:
            r = await self._get_redis()
            await r.delete(self._make_key(key))
            log.info("memory.deleted", key=key, conversation=self.conversation_id)
        except Exception as e:
            log.warning("memory.delete_failed", key=key, error=str(e))

    async def forget_all(self) -> None:
        """Delete all memory for this conversation."""
        try:
            r = await self._get_redis()
            pattern = self._make_key("*")
            keys = await r.keys(pattern)
            if keys:
                await r.delete(*keys)
            log.info("memory.cleared", conversation=self.conversation_id)
        except Exception as e:
            log.warning("memory.clear_failed", error=str(e))

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

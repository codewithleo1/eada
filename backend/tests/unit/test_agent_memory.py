"""
test_agent_memory.py — unit tests for backend/memory/agent_memory.py

Mocks Redis entirely — no real Redis connection needed.
Tests:
  - remember() stores JSON-serialised value with TTL
  - recall() returns deserialised value on hit
  - recall() returns None on miss
  - recall() returns None when Redis unavailable
  - forget() deletes correct key
  - forget_all() deletes all keys for conversation
  - keys are correctly namespaced by conversation_id
"""

import pytest
from unittest.mock import AsyncMock
from backend.memory.agent_memory import AgentMemory


# ---------------------------------------------------------------------------
# Helpers — build a mock Redis client
# ---------------------------------------------------------------------------

def _make_mock_redis(get_return=None, keys_return=None):
    """Build a mock aioredis client with common methods."""
    mock = AsyncMock()
    mock.setex = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=get_return)
    mock.delete = AsyncMock(return_value=1)
    mock.keys = AsyncMock(return_value=keys_return or [])
    mock.aclose = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# remember()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remember_calls_setex_with_correct_key():
    mock_redis = _make_mock_redis()
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    await memory.remember("file_schema", {"columns": ["a", "b"]}, ttl=3600)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args[0]
    assert call_args[0] == "eada:memory:conv-001:file_schema"
    assert call_args[1] == 3600


@pytest.mark.asyncio
async def test_remember_serialises_dict_to_json():
    import json
    mock_redis = _make_mock_redis()
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    value = {"row_count": 100, "columns": ["a", "b"]}
    await memory.remember("schema", value)

    call_args = mock_redis.setex.call_args[0]
    stored = json.loads(call_args[2])
    assert stored == value


@pytest.mark.asyncio
async def test_remember_does_not_raise_on_redis_failure():
    mock_redis = _make_mock_redis()
    mock_redis.setex = AsyncMock(side_effect=ConnectionError("Redis down"))
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    # Should not raise — memory failure is non-fatal
    await memory.remember("key", {"data": 1})


# ---------------------------------------------------------------------------
# recall()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recall_returns_deserialised_value_on_hit():
    import json
    stored = json.dumps({"row_count": 5})
    mock_redis = _make_mock_redis(get_return=stored)
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    result = await memory.recall("file_schema")
    assert result == {"row_count": 5}


@pytest.mark.asyncio
async def test_recall_returns_none_on_miss():
    mock_redis = _make_mock_redis(get_return=None)
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    result = await memory.recall("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_recall_returns_none_on_redis_failure():
    mock_redis = _make_mock_redis()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    result = await memory.recall("file_schema")
    assert result is None


@pytest.mark.asyncio
async def test_recall_uses_correct_namespaced_key():
    mock_redis = _make_mock_redis(get_return=None)
    memory = AgentMemory(conversation_id="conv-xyz")
    memory._redis = mock_redis

    await memory.recall("sql_result")

    mock_redis.get.assert_called_once_with("eada:memory:conv-xyz:sql_result")


# ---------------------------------------------------------------------------
# forget()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forget_deletes_correct_key():
    mock_redis = _make_mock_redis()
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    await memory.forget("file_schema")

    mock_redis.delete.assert_called_once_with("eada:memory:conv-001:file_schema")


# ---------------------------------------------------------------------------
# forget_all()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forget_all_deletes_all_conversation_keys():
    keys = [
        "eada:memory:conv-001:file_schema",
        "eada:memory:conv-001:sql_result",
    ]
    mock_redis = _make_mock_redis(keys_return=keys)
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    await memory.forget_all()

    mock_redis.delete.assert_called_once_with(*keys)


@pytest.mark.asyncio
async def test_forget_all_does_nothing_when_no_keys():
    mock_redis = _make_mock_redis(keys_return=[])
    memory = AgentMemory(conversation_id="conv-001")
    memory._redis = mock_redis

    await memory.forget_all()

    mock_redis.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Namespace isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_different_conversations_have_different_keys():
    mock_redis_1 = _make_mock_redis(get_return=None)
    mock_redis_2 = _make_mock_redis(get_return=None)

    mem1 = AgentMemory(conversation_id="conv-aaa")
    mem1._redis = mock_redis_1

    mem2 = AgentMemory(conversation_id="conv-bbb")
    mem2._redis = mock_redis_2

    await mem1.recall("schema")
    await mem2.recall("schema")

    key1 = mock_redis_1.get.call_args[0][0]
    key2 = mock_redis_2.get.call_args[0][0]

    assert key1 != key2
    assert "conv-aaa" in key1
    assert "conv-bbb" in key2

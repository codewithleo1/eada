"""
test_gateway.py — unit tests for backend/llm/gateway.py

Mocks litellm.acompletion entirely — no real API calls.
Tests verify:
  - ToolCallRequest and ToolCallResponse dataclasses
  - complete_with_tools() correctly parses tool call responses
  - complete_with_tools() correctly parses text responses
  - Bad JSON in arguments falls back to empty dict
  - LiteLLM exceptions propagate up
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.llm.gateway import ToolCallRequest, ToolCallResponse, LLMGateway


# ---------------------------------------------------------------------------
# ToolCallRequest dataclass
# ---------------------------------------------------------------------------

def test_tool_call_request_stores_fields():
    tc = ToolCallRequest(id="call-1", name="query_data", arguments={"sql": "SELECT 1"})
    assert tc.id == "call-1"
    assert tc.name == "query_data"
    assert tc.arguments == {"sql": "SELECT 1"}


# ---------------------------------------------------------------------------
# ToolCallResponse dataclass
# ---------------------------------------------------------------------------

def test_tool_call_response_wants_tool_true_when_tool_calls_present():
    tc = ToolCallRequest(id="call-1", name="query_data", arguments={})
    response = ToolCallResponse(tool_calls=[tc])
    assert response.wants_tool is True


def test_tool_call_response_wants_tool_false_when_text_only():
    response = ToolCallResponse(text="Here is your answer.")
    assert response.wants_tool is False


def test_tool_call_response_wants_tool_false_when_empty():
    response = ToolCallResponse()
    assert response.wants_tool is False


def test_tool_call_response_default_text_is_none():
    response = ToolCallResponse()
    assert response.text is None


def test_tool_call_response_default_tool_calls_is_empty_list():
    response = ToolCallResponse()
    assert response.tool_calls == []


# ---------------------------------------------------------------------------
# Helpers — build mock LiteLLM responses
# ---------------------------------------------------------------------------

def _make_text_response(text: str):
    """Simulate a LiteLLM response where LLM returns plain text."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None

    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_tool_call_response(tool_name: str, arguments: dict, call_id: str = "call-abc"):
    """Simulate a LiteLLM response where LLM requests a tool call."""
    fn = MagicMock()
    fn.name = tool_name
    fn.arguments = json.dumps(arguments)

    tc = MagicMock()
    tc.id = call_id
    tc.function = fn

    message = MagicMock()
    message.content = None
    message.tool_calls = [tc]

    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_tool_call_response_bad_json(tool_name: str, call_id: str = "call-bad"):
    """Simulate a LiteLLM response with malformed JSON in arguments."""
    fn = MagicMock()
    fn.name = tool_name
    fn.arguments = "this is not valid json {{{"

    tc = MagicMock()
    tc.id = call_id
    tc.function = fn

    message = MagicMock()
    message.content = None
    message.tool_calls = [tc]

    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# complete_with_tools — text response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_with_tools_returns_text_on_stop():
    gateway = LLMGateway()
    mock_response = _make_text_response("Here is your answer.")

    with patch("backend.llm.gateway.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        result = await gateway.complete_with_tools(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
        )

    assert isinstance(result, ToolCallResponse)
    assert result.wants_tool is False
    assert result.text == "Here is your answer."


# ---------------------------------------------------------------------------
# complete_with_tools — tool call response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_with_tools_returns_tool_calls_on_tool_finish():
    gateway = LLMGateway()
    mock_response = _make_tool_call_response(
        tool_name="query_data",
        arguments={"file_id": "abc-123", "sql": "SELECT * FROM data"},
        call_id="call-xyz",
    )

    with patch("backend.llm.gateway.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        result = await gateway.complete_with_tools(
            messages=[{"role": "user", "content": "Show me the data"}],
            tools=[],
        )

    assert isinstance(result, ToolCallResponse)
    assert result.wants_tool is True
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.id == "call-xyz"
    assert tc.name == "query_data"
    assert tc.arguments == {"file_id": "abc-123", "sql": "SELECT * FROM data"}


@pytest.mark.asyncio
async def test_complete_with_tools_bad_json_falls_back_to_empty_dict():
    gateway = LLMGateway()
    mock_response = _make_tool_call_response_bad_json("query_data")

    with patch("backend.llm.gateway.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        result = await gateway.complete_with_tools(
            messages=[{"role": "user", "content": "Show me the data"}],
            tools=[],
        )

    assert result.wants_tool is True
    assert result.tool_calls[0].arguments == {}


@pytest.mark.asyncio
async def test_complete_with_tools_propagates_litellm_exception():
    gateway = LLMGateway()

    with patch(
        "backend.llm.gateway.litellm.acompletion",
        new=AsyncMock(side_effect=RuntimeError("API down")),
    ):
        with pytest.raises(RuntimeError, match="API down"):
            await gateway.complete_with_tools(
                messages=[{"role": "user", "content": "Hello"}],
                tools=[],
            )

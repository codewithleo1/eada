"""
test_registry.py — unit tests for backend/tools/registry.py

No external dependencies — registry is pure data, no mocking needed.
"""

from backend.tools.registry import (
    get_tools_for_context,
    ALL_TOOLS,
    TOOL_MAP,
)


def test_no_file_no_doc_returns_empty():
    tools = get_tools_for_context(has_file=False, has_doc=False)
    assert tools == []


def test_has_file_only_returns_two_tools():
    tools = get_tools_for_context(has_file=True, has_doc=False)
    names = [t["function"]["name"] for t in tools]
    assert len(tools) == 2
    assert "get_file_schema" in names
    assert "query_data" in names
    assert "retrieve_context" not in names


def test_has_doc_only_returns_one_tool():
    tools = get_tools_for_context(has_file=False, has_doc=True)
    names = [t["function"]["name"] for t in tools]
    assert len(tools) == 1
    assert "retrieve_context" in names
    assert "query_data" not in names
    assert "get_file_schema" not in names


def test_has_file_and_doc_returns_all_three():
    tools = get_tools_for_context(has_file=True, has_doc=True)
    names = [t["function"]["name"] for t in tools]
    assert len(tools) == 3
    assert "get_file_schema" in names
    assert "query_data" in names
    assert "retrieve_context" in names


def test_tool_map_keys_match_expected_names():
    expected = {"query_data", "get_file_schema", "retrieve_context"}
    assert set(TOOL_MAP.keys()) == expected


def test_all_tools_in_tool_map():
    for tool in ALL_TOOLS:
        name = tool["function"]["name"]
        assert name in TOOL_MAP


def test_tool_map_values_match_all_tools():
    for tool in ALL_TOOLS:
        name = tool["function"]["name"]
        assert TOOL_MAP[name] is tool


def test_every_tool_has_required_fields():
    for tool in ALL_TOOLS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert len(fn["description"]) > 10
        assert "parameters" in fn
        assert "required" in fn["parameters"]
        assert len(fn["parameters"]["required"]) > 0

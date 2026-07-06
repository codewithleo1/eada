"""
test_executor.py — unit tests for backend/tools/executor.py

All external dependencies are mocked:
  - file system  (pathlib.Path.exists)
  - execute_query (sql_tool)
  - get_file_info (file_tool)
  - retrieve_context + build_rag_context (rag_pipeline)
"""

import json
import pytest
from unittest.mock import patch
from backend.tools.executor import (
    _resolve_file_path,
    execute_tool_call,
)


# ---------------------------------------------------------------------------
# _resolve_file_path
# ---------------------------------------------------------------------------

def test_resolve_file_path_finds_csv(tmp_path):
    """Creates a real CSV file in tmp_path and checks resolution."""
    file_id = "abc-123"
    csv_file = tmp_path / f"{file_id}.csv"
    csv_file.write_text("col1,col2\n1,2")

    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path):
        result = _resolve_file_path(file_id)

    assert result == csv_file


def test_resolve_file_path_finds_xlsx(tmp_path):
    file_id = "def-456"
    xlsx_file = tmp_path / f"{file_id}.xlsx"
    xlsx_file.write_bytes(b"fake xlsx content")

    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path):
        result = _resolve_file_path(file_id)

    assert result == xlsx_file


def test_resolve_file_path_raises_when_missing(tmp_path):
    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path):
        with pytest.raises(FileNotFoundError, match="abc-999"):
            _resolve_file_path("abc-999")


# ---------------------------------------------------------------------------
# execute_tool_call — unknown tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_tool_returns_error_string():
    result = await execute_tool_call("nonexistent_tool", {})
    assert "Unknown tool" in result
    assert "nonexistent_tool" in result


# ---------------------------------------------------------------------------
# execute_tool_call — query_data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_data_returns_json_on_success(tmp_path):
    file_id = "qd-001"
    csv_file = tmp_path / f"{file_id}.csv"
    csv_file.write_text("a,b\n1,2")

    fake_result = {
        "sql": "SELECT * FROM data",
        "columns": ["a", "b"],
        "rows": [{"a": 1, "b": 2}],
        "row_count": 1,
        "truncated": False,
    }

    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path), \
         patch("backend.tools.executor.execute_query", return_value=fake_result):
        result = await execute_tool_call(
            "query_data",
            {"file_id": file_id, "sql": "SELECT * FROM data"},
        )

    parsed = json.loads(result)
    assert parsed["row_count"] == 1
    assert parsed["columns"] == ["a", "b"]


@pytest.mark.asyncio
async def test_query_data_returns_error_string_on_missing_file(tmp_path):
    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path):
        result = await execute_tool_call(
            "query_data",
            {"file_id": "missing-id", "sql": "SELECT * FROM data"},
        )

    assert "File not found" in result


@pytest.mark.asyncio
async def test_query_data_returns_error_string_on_sql_error(tmp_path):
    from backend.tools.sql_tool import SqlToolError

    file_id = "qd-002"
    csv_file = tmp_path / f"{file_id}.csv"
    csv_file.write_text("a,b\n1,2")

    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path), \
         patch("backend.tools.executor.execute_query", side_effect=SqlToolError("bad sql")):
        result = await execute_tool_call(
            "query_data",
            {"file_id": file_id, "sql": "BAD SQL"},
        )

    assert "Query error" in result
    assert "bad sql" in result


@pytest.mark.asyncio
async def test_query_data_returns_no_rows_message(tmp_path):
    file_id = "qd-003"
    csv_file = tmp_path / f"{file_id}.csv"
    csv_file.write_text("a,b\n1,2")

    fake_result = {
        "sql": "SELECT * FROM data WHERE a = 999",
        "columns": ["a", "b"],
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }

    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path), \
         patch("backend.tools.executor.execute_query", return_value=fake_result):
        result = await execute_tool_call(
            "query_data",
            {"file_id": file_id, "sql": "SELECT * FROM data WHERE a = 999"},
        )

    assert result == "Query returned no rows."


# ---------------------------------------------------------------------------
# execute_tool_call — get_file_schema
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_file_schema_returns_json_on_success(tmp_path):
    file_id = "fs-001"
    csv_file = tmp_path / f"{file_id}.csv"
    csv_file.write_text("a,b\n1,2")

    fake_info = {
        "file_path": str(csv_file),
        "extension": ".csv",
        "row_count": 1,
        "columns": [{"name": "a", "dtype": "int64"}],
        "sample": [{"a": 1, "b": 2}],
        "sql_table_ref": "read_csv(...)",
    }

    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path), \
         patch("backend.tools.executor.get_file_info", return_value=fake_info):
        result = await execute_tool_call(
            "get_file_schema",
            {"file_id": file_id},
        )

    parsed = json.loads(result)
    assert parsed["row_count"] == 1
    assert parsed["extension"] == ".csv"


@pytest.mark.asyncio
async def test_get_file_schema_returns_error_on_missing_file(tmp_path):
    with patch("backend.tools.executor.UPLOADS_DIR", tmp_path):
        result = await execute_tool_call(
            "get_file_schema",
            {"file_id": "missing-id"},
        )

    assert "File not found" in result


# ---------------------------------------------------------------------------
# execute_tool_call — retrieve_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_context_returns_formatted_string():
    fake_chunks = [
        {"source": "doc.pdf", "chunk_index": 0, "score": 0.95, "text": "Revenue was $1M"},
        {"source": "doc.pdf", "chunk_index": 1, "score": 0.88, "text": "Costs were $500K"},
    ]

    with patch("backend.tools.executor.retrieve_context", return_value=fake_chunks), \
         patch("backend.tools.executor.build_rag_context", return_value="Formatted context"):
        result = await execute_tool_call(
            "retrieve_context",
            {"doc_id": "doc-001", "query": "what was revenue?"},
        )

    assert result == "Formatted context"


@pytest.mark.asyncio
async def test_retrieve_context_returns_no_context_message():
    with patch("backend.tools.executor.retrieve_context", return_value=[]):
        result = await execute_tool_call(
            "retrieve_context",
            {"doc_id": "doc-001", "query": "what was revenue?"},
        )

    assert "No relevant context" in result


@pytest.mark.asyncio
async def test_retrieve_context_returns_error_on_pipeline_failure():
    from backend.rag.rag_pipeline import RAGPipelineError

    with patch("backend.tools.executor.retrieve_context", side_effect=RAGPipelineError("qdrant down")):
        result = await execute_tool_call(
            "retrieve_context",
            {"doc_id": "doc-001", "query": "what was revenue?"},
        )

    assert "Retrieval error" in result
    assert "qdrant down" in result

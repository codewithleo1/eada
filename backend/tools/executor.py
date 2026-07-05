"""
Tool executor — routes LLM tool calls to real Python functions.

The LLM returns a tool name + arguments dict.
This module maps that to the correct backend function and returns
the result as a string that gets sent back to the LLM.

No tool definitions live here — see registry.py for those.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.tools.file_tool import get_file_info, FileToolError, SUPPORTED_EXTENSIONS
from backend.tools.sql_tool import execute_query, SqlToolError
from backend.rag.rag_pipeline import retrieve_context, build_rag_context, RAGPipelineError

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("uploads")


# ---------------------------------------------------------------------------
# Helper — resolve file_id to an actual path on disk
# ---------------------------------------------------------------------------

def _resolve_file_path(file_id: str) -> Path:
    """
    Scan the uploads directory for a file matching the given UUID.
    Tries every supported extension until a match is found.
    Raises FileNotFoundError if no file exists for that file_id.
    """
    for ext in SUPPORTED_EXTENSIONS:
        candidate = UPLOADS_DIR / f"{file_id}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No uploaded file found for file_id='{file_id}'. "
        f"Searched: {[f'{file_id}{e}' for e in SUPPORTED_EXTENSIONS]}"
    )


# ---------------------------------------------------------------------------
# Individual handlers — one per tool, signatures match real functions exactly
# ---------------------------------------------------------------------------

async def _handle_query_data(args: dict[str, Any]) -> str:
    """
    Execute a DuckDB SQL query against an uploaded file.
    Resolves file_id → file_path, then calls execute_query(sql, file_path).
    """
    file_id: str = args["file_id"]
    sql: str = args["sql"]

    try:
        file_path = _resolve_file_path(file_id)
        result = execute_query(sql, str(file_path))
    except FileNotFoundError as exc:
        return f"File not found: {exc}"
    except SqlToolError as exc:
        logger.error("query_data failed: %s", exc)
        return f"Query error: {exc}"
    except Exception as exc:
        logger.error("query_data unexpected error: %s", exc)
        return f"Unexpected error: {exc}"

    if not result["rows"]:
        return "Query returned no rows."

    # Return the full result dict as JSON — the LLM will interpret it
    return json.dumps(result, default=str)


async def _handle_get_file_schema(args: dict[str, Any]) -> str:
    """
    Return column names, data types, and sample rows for an uploaded file.
    Resolves file_id → file_path, then calls get_file_info(file_path).
    """
    file_id: str = args["file_id"]

    try:
        file_path = _resolve_file_path(file_id)
        info = get_file_info(str(file_path))
    except FileNotFoundError as exc:
        return f"File not found: {exc}"
    except FileToolError as exc:
        logger.error("get_file_schema failed: %s", exc)
        return f"Schema error: {exc}"
    except Exception as exc:
        logger.error("get_file_schema unexpected error: %s", exc)
        return f"Unexpected error: {exc}"

    return json.dumps(info, default=str)


async def _handle_retrieve_context(args: dict[str, Any]) -> str:
    """
    Search Qdrant for document chunks relevant to the query.
    Calls retrieve_context(question, top_k, doc_id) then build_rag_context(chunks).
    Both functions are synchronous — no await needed.
    """
    doc_id: str = args["doc_id"]
    query: str = args["query"]
    top_k: int = args.get("top_k", 5)

    try:
        chunks = retrieve_context(query, top_k=top_k, doc_id=doc_id)
    except RAGPipelineError as exc:
        logger.error("retrieve_context failed: %s", exc)
        return f"Retrieval error: {exc}"
    except Exception as exc:
        logger.error("retrieve_context unexpected error: %s", exc)
        return f"Unexpected error: {exc}"

    if not chunks:
        return "No relevant context found in the document."

    return build_rag_context(chunks)


# ---------------------------------------------------------------------------
# Router — single entry point called by chat.py
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "query_data": _handle_query_data,
    "get_file_schema": _handle_get_file_schema,
    "retrieve_context": _handle_retrieve_context,
}


async def execute_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """
    Route a tool call from the LLM to the correct handler.

    Always returns a string — errors come back as readable strings so
    the LLM can explain what went wrong to the user instead of crashing.

    Args:
        name:       Tool name exactly as returned by the LLM.
        arguments:  Argument dict exactly as returned by the LLM.

    Returns:
        String result to send back to the LLM as a tool result message.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        logger.warning("Unknown tool called: %s", name)
        return (
            f"Unknown tool '{name}'. "
            f"Available tools: {list(_HANDLERS.keys())}"
        )

    logger.info("Executing tool '%s' with args: %s", name, arguments)
    return await handler(arguments)
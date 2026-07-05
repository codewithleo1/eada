"""
Tool registry — catalogue of tools available to the LLM.

Each tool is described as an OpenAI-compatible function-calling schema.
LiteLLM normalises this format for Gemini automatically.

No execution logic lives here — this file is pure definitions.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Individual tool definitions
# ---------------------------------------------------------------------------

QUERY_DATA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "query_data",
        "description": (
            "Execute a SQL SELECT query against an uploaded data file "
            "(CSV, Excel, JSON, or Parquet). Use this whenever the user "
            "asks to filter, aggregate, sort, or analyse tabular data. "
            "Always use DuckDB-compatible SQL syntax. "
            "The table name is always 'df'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The UUID of the uploaded file to query.",
                },
                "sql": {
                    "type": "string",
                    "description": (
                        "A valid DuckDB SELECT statement. "
                        "Example: SELECT region, SUM(sales) FROM df "
                        "GROUP BY region ORDER BY SUM(sales) DESC"
                    ),
                },
            },
            "required": ["file_id", "sql"],
        },
    },
}

GET_FILE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_file_schema",
        "description": (
            "Retrieve the column names, data types, and a small sample of rows "
            "from an uploaded file. Call this before query_data if you are "
            "unsure what columns exist or what the data looks like."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The UUID of the uploaded file to inspect.",
                },
            },
            "required": ["file_id"],
        },
    },
}

RETRIEVE_CONTEXT: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "retrieve_context",
        "description": (
            "Search the vector store for document chunks relevant to a query. "
            "Use this when the user asks questions about an ingested document "
            "(PDF, DOCX, TXT, or Markdown). Returns the most relevant excerpts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "The document ID returned when the document was ingested.",
                },
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant document sections.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to retrieve. Default is 5.",
                },
            },
            "required": ["doc_id", "query"],
        },
    },
}

# ---------------------------------------------------------------------------
# Registry — the complete list sent to the LLM on every chat turn
# ---------------------------------------------------------------------------

ALL_TOOLS: list[dict[str, Any]] = [
    QUERY_DATA,
    GET_FILE_SCHEMA,
    RETRIEVE_CONTEXT,
]

# Lookup by name — used by the executor to route calls
TOOL_MAP: dict[str, dict[str, Any]] = {
    t["function"]["name"]: t for t in ALL_TOOLS
}


def get_tools_for_context(
    *,
    has_file: bool = False,
    has_doc: bool = False,
) -> list[dict[str, Any]]:
    """
    Return only the tools relevant to the current conversation context.

    Sending irrelevant tools wastes tokens and confuses the LLM.
    - No file uploaded  → skip query_data and get_file_schema
    - No doc ingested   → skip retrieve_context
    - Both present      → return all three
    """
    tools = []
    if has_file:
        tools.append(GET_FILE_SCHEMA)
        tools.append(QUERY_DATA)
    if has_doc:
        tools.append(RETRIEVE_CONTEXT)
    return tools
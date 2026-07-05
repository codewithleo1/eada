"""
mcp/server.py — MCP-compliant HTTP server exposing EADA tools.

Endpoints:
  GET  /mcp/health       — health check
  GET  /mcp/tools        — list available tools with schemas
  POST /mcp/tools/call   — execute a tool call

All tool logic lives in executor.py — this file only handles
MCP protocol formatting and HTTP routing.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.tools.registry import ALL_TOOLS
from backend.tools.executor import execute_tool_call
from backend.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ToolCallRequest(BaseModel):
    """Incoming MCP tool call request body."""
    name: str
    arguments: dict


class MCPContent(BaseModel):
    """Single content block in an MCP response."""
    type: str = "text"
    text: str


class MCPResponse(BaseModel):
    """Standard MCP tool call response envelope."""
    content: list[MCPContent]
    isError: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def mcp_health() -> dict:
    """MCP server health check."""
    return {"status": "ok", "server": "eada-mcp"}


@router.get("/tools")
async def list_tools() -> dict:
    """
    Return all available tools with their full schemas.
    MCP clients call this on startup to discover what tools exist.
    """
    log.info("mcp.list_tools", count=len(ALL_TOOLS))
    return {"tools": ALL_TOOLS}


@router.post("/tools/call")
async def call_tool(request: ToolCallRequest) -> MCPResponse:
    """
    Execute a tool call and return the result in MCP format.

    The executor handles all routing and error handling.
    This endpoint only wraps the result in the MCP envelope.
    """
    log.info("mcp.tool_call", name=request.name, args=request.arguments)

    result = await execute_tool_call(request.name, request.arguments)

    # execute_tool_call always returns a string — errors included
    # Detect error strings to set isError flag correctly
    is_error = result.startswith((
        "Unknown tool",
        "File not found",
        "Query error",
        "Schema error",
        "Retrieval error",
        "Unexpected error",
    ))

    log.info("mcp.tool_call_done", name=request.name, is_error=is_error)

    return MCPResponse(
        content=[MCPContent(type="text", text=result)],
        isError=is_error,
    )

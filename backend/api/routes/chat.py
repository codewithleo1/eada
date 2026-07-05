"""
chat.py — WebSocket chat endpoint with agentic tool-calling loop.

Flow per user message:
  1. Build messages list (system prompt + conversation history)
  2. Get tools relevant to this session (file? doc?)
  3. Call LLM with tools → get ToolCallResponse
  4. If LLM wants a tool → execute it, append result, go to 3
  5. Repeat until LLM gives final text answer (max 5 iterations)
  6. Stream final answer to frontend token by token
  7. Persist full exchange to DB
"""

from __future__ import annotations

import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.llm.gateway import llm, ToolCallResponse
from backend.tools.registry import get_tools_for_context
from backend.tools.executor import execute_tool_call
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer
from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit
from backend.db.session import async_session_factory
from backend.db.repositories import ConversationRepository, MessageRepository

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Safety ceiling for the agentic tool-calling loop
MAX_TOOL_ITERATIONS = 5


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _build_system_prompt(
    has_file: bool = False,
    has_doc: bool = False,
) -> str:
    """
    Build the system prompt for the current session.

    No file schema or RAG context is injected here — the LLM pulls
    that information itself by calling get_file_schema or retrieve_context.
    """
    base = (
        "You are EADA, an expert autonomous data analyst. "
        "Answer questions clearly and concisely. "
        "Think step by step before acting. "
    )

    if has_file and has_doc:
        return base + (
            "You have access to an uploaded data file and an ingested document. "
            "Use get_file_schema to inspect the file before querying it. "
            "Use query_data to run SQL against the file. "
            "Use retrieve_context to search the document for relevant information."
        )

    if has_file:
        return base + (
            "You have access to an uploaded data file. "
            "Always call get_file_schema first to understand the columns, "
            "then call query_data to answer questions about the data. "
            "Use DuckDB SQL syntax. The table name is always 'data'."
        )

    if has_doc:
        return base + (
            "You have access to an ingested document. "
            "Use retrieve_context to find relevant sections before answering."
        )

    return base + "Answer questions using your knowledge."


# ---------------------------------------------------------------------------
# Tool-calling agentic loop
# ---------------------------------------------------------------------------

async def _run_tool_loop(
    messages: list[dict],
    tools: list[dict],
) -> tuple[str, list[dict]]:
    """
    Run the agentic tool-calling loop until the LLM gives a final answer.

    Args:
        messages: Full conversation history in OpenAI format.
        tools:    Tool definitions from registry.

    Returns:
        Tuple of:
          - final_text: the LLM's final answer as a plain string
          - messages:   updated messages list including all tool exchanges
                        (caller should persist the assistant's final message)
    """
    for iteration in range(MAX_TOOL_ITERATIONS):
        log.info("tool_loop_iteration", iteration=iteration)

        # Ask the LLM — it returns text OR tool call requests
        response: ToolCallResponse = await llm.complete_with_tools(
            messages=messages,
            tools=tools,
        )

        # LLM gave a final text answer — we are done
        if not response.wants_tool:
            final_text = response.text or ""
            log.info("tool_loop_complete", iterations=iteration + 1)
            return final_text, messages

        # LLM wants to call tools — execute each one and collect results
        # First append the assistant's tool-call message to history
        # so the LLM sees its own request in the next turn
        tool_call_dicts = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in response.tool_calls
        ]
        messages.append({
            "role": "assistant",
            "tool_calls": tool_call_dicts,
            "content": None,
        })

        # Execute each tool call and append results as tool messages
        for tc in response.tool_calls:
            log.info("executing_tool", name=tc.name, args=tc.arguments)
            result_str = await execute_tool_call(tc.name, tc.arguments)
            log.info("tool_result", name=tc.name, result_length=len(result_str))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    # Iteration ceiling hit — ask LLM for best-effort answer with what it has
    log.warning("tool_loop_ceiling_hit", max_iterations=MAX_TOOL_ITERATIONS)
    fallback = await llm.complete(messages=messages)
    return fallback, messages


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    conversation_id: str | None = Query(None, description="Existing conversation UUID"),
    file_id: str | None = Query(None, description="UUID of an uploaded file to analyse"),
    doc_id: str | None = Query(None, description="UUID of an ingested document for RAG Q&A"),
) -> None:
    """
    Protected, persistent WebSocket streaming chat endpoint.

    Connect with:
        ws://localhost:8000/chat/ws?token=<jwt>
        ws://localhost:8000/chat/ws?token=<jwt>&conversation_id=<uuid>
        ws://localhost:8000/chat/ws?token=<jwt>&file_id=<uuid>
        ws://localhost:8000/chat/ws?token=<jwt>&doc_id=<uuid>
        ws://localhost:8000/chat/ws?token=<jwt>&file_id=<uuid>&doc_id=<uuid>
    """
    # --- Auth ---
    try:
        payload = verify_token(token)
        user_id_str = payload.get("sub", "anonymous")
        user_id = uuid.UUID(user_id_str) if user_id_str != "anonymous" else None
    except Exception:
        await websocket.close(code=4001)
        return

    # --- Rate limit ---
    try:
        check_rate_limit(user_id_str)
    except Exception:
        await websocket.close(code=4029)
        return

    await websocket.accept()

    has_file = file_id is not None
    has_doc = doc_id is not None

    log.info(
        "websocket_connected",
        user_id=user_id_str,
        file_id=file_id,
        doc_id=doc_id,
    )

    # Pre-build tools and system prompt once per connection
    tools = get_tools_for_context(has_file=has_file, has_doc=has_doc)
    system_prompt = _build_system_prompt(has_file=has_file, has_doc=has_doc)

    async with async_session_factory() as db:
        conv_repo = ConversationRepository(db)
        msg_repo = MessageRepository(db)

        # Resume or create conversation
        conversation = None
        if conversation_id:
            try:
                conversation = await conv_repo.get_by_id(
                    uuid.UUID(conversation_id), user_id
                )
            except ValueError:
                conversation = None

        if conversation is None:
            conversation = await conv_repo.create(user_id=user_id)
            log.info("new_conversation", id=str(conversation.id))

        await websocket.send_json({
            "type": "conversation_id",
            "value": str(conversation.id),
        })

        # Inject file_id and doc_id into system prompt so LLM knows the IDs
        # to pass when calling tools — it cannot guess them
        enriched_system = system_prompt
        if file_id:
            enriched_system += f"\n\nThe uploaded file ID is: {file_id}"
        if doc_id:
            enriched_system += f"\n\nThe ingested document ID is: {doc_id}"

        try:
            while True:
                data = await websocket.receive_json()
                user_message = data.get("message", "").strip()

                if not user_message:
                    await websocket.send_text("[ERROR] Empty message")
                    continue

                log.info(
                    "message_received",
                    user_id=user_id_str,
                    length=len(user_message),
                )

                # Persist user message
                await msg_repo.add(
                    conversation.id, role="user", content=user_message
                )

                # Auto-title conversation from first message
                history = await msg_repo.list_for_conversation(conversation.id)
                if len(history) == 1:
                    title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                    await conv_repo.update_title(conversation.id, title)

                trace = tracer.create_trace(
                    name="chat",
                    user_id=user_id_str,
                    metadata={"conversation_id": str(conversation.id)},
                )

                # Build full messages list for this turn
                messages: list[dict] = [
                    {"role": "system", "content": enriched_system}
                ]
                for m in history:
                    messages.append({"role": m.role, "content": m.content})

                # --- Agentic tool loop ---
                if tools:
                    final_answer, _ = await _run_tool_loop(
                        messages=messages,
                        tools=tools,
                    )
                else:
                    # No tools available — plain completion
                    final_answer = await llm.complete(messages=messages)

                # Stream final answer to frontend token by token
                # We simulate streaming by chunking the completed text
                # (tool loop uses non-streaming complete_with_tools internally)
                chunk_size = 20
                for i in range(0, len(final_answer), chunk_size):
                    await websocket.send_text(final_answer[i:i + chunk_size])

                # Persist assistant response
                await msg_repo.add(
                    conversation.id, role="assistant", content=final_answer
                )

                tracer.log_generation(
                    trace=trace,
                    name="chat_response",
                    model=llm.primary_model,
                    prompt=user_message,
                    completion=final_answer,
                )

                await websocket.send_text("[DONE]")
                log.info("response_complete", user_id=user_id_str)

        except WebSocketDisconnect:
            log.info("websocket_disconnected", user_id=user_id_str)
        except Exception as e:
            log.error("websocket_error", user_id=user_id_str, error=str(e))
            await websocket.send_text(f"[ERROR] {str(e)}")
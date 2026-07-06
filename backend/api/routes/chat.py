"""
chat.py — WebSocket chat endpoint with multi-agent graph.

Flow per user message:
  1. Build initial AgentState from message + context
  2. Invoke agent_graph — LangGraph runs full pipeline
  3. Extract final_answer from returned state
  4. Stream final answer to frontend token by token
  5. Persist full exchange to DB
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.llm.gateway import llm
from backend.agents.graph import agent_graph
from backend.agents.state import AgentState
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer
from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit
from backend.db.session import async_session_factory
from backend.db.repositories import ConversationRepository, MessageRepository

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Agent graph runner
# ---------------------------------------------------------------------------

async def _run_agent_graph(
    user_message: str,
    file_id: str | None,
    doc_id: str | None,
    history: list[dict],
) -> str:
    """
    Build initial AgentState and invoke the LangGraph agent pipeline.

    Args:
        user_message: current user message
        file_id:      uploaded file UUID or None
        doc_id:       ingested document UUID or None
        history:      conversation history in OpenAI format

    Returns:
        final_answer string from the agent graph
    """
    initial_state: AgentState = {
        "messages": history,
        "user_message": user_message,
        "file_id": file_id,
        "doc_id": doc_id,
        "plan": [],
        "sql_result": {},
        "rag_context": "",
        "code_result": "",
        "critique": "",
        "final_answer": "",
        "next_agent": "router",
        "error": None,
        "iteration": 0,
    }

    log.info(
        "agent_graph.invoke",
        message=user_message[:80],
        file_id=file_id,
        doc_id=doc_id,
    )

    try:
        result_state = await agent_graph.ainvoke(initial_state)
        final_answer = result_state.get("final_answer", "")

        if not final_answer:
            final_answer = "I was unable to generate an answer. Please try again."

        log.info("agent_graph.done", answer_length=len(final_answer))
        return final_answer

    except Exception as e:
        log.error("agent_graph.failed", error=str(e))
        # Fall back to direct LLM call if graph fails
        fallback = await llm.complete(messages=history)
        return fallback


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

    log.info(
        "websocket_connected",
        user_id=user_id_str,
        file_id=file_id,
        doc_id=doc_id,
    )

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

                # Build history in OpenAI format for agent graph
                messages = []
                for m in history:
                    messages.append({"role": m.role, "content": m.content})

                # --- Run multi-agent graph ---
                final_answer = await _run_agent_graph(
                    user_message=user_message,
                    file_id=file_id,
                    doc_id=doc_id,
                    history=messages,
                )

                # Stream final answer to frontend token by token
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

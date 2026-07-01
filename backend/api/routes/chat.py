import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.llm.gateway import llm
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer
from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit
from backend.db.session import async_session_factory
from backend.db.repositories import ConversationRepository, MessageRepository

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    conversation_id: str | None = Query(None, description="Existing conversation UUID, or omit to start a new one"),
) -> None:
    """Protected, persistent WebSocket streaming chat endpoint.

    Connect with:
        ws://localhost:8000/chat/ws?token=<jwt>
        ws://localhost:8000/chat/ws?token=<jwt>&conversation_id=<uuid>  (to resume)

    Every message and response is saved to PostgreSQL. Full conversation
    history is sent to the LLM on every turn so it has context.
    """
    try:
        payload = verify_token(token)
        user_id_str = payload.get("sub", "anonymous")
        user_id = uuid.UUID(user_id_str) if user_id_str != "anonymous" else None
    except Exception:
        await websocket.close(code=4001)
        return

    try:
        check_rate_limit(user_id_str)
    except Exception:
        await websocket.close(code=4029)
        return

    await websocket.accept()
    log.info("websocket_connected", user_id=user_id_str)

    async with async_session_factory() as db:
        conv_repo = ConversationRepository(db)
        msg_repo = MessageRepository(db)

        # Resume existing conversation or start a new one
        conversation = None
        if conversation_id:
            try:
                conversation = await conv_repo.get_by_id(uuid.UUID(conversation_id), user_id)
            except ValueError:
                conversation = None

        if conversation is None:
            conversation = await conv_repo.create(user_id=user_id)
            log.info("new_conversation_started", conversation_id=str(conversation.id))

        # Tell the client which conversation this is, in case it was just created
        await websocket.send_json({"type": "conversation_id", "value": str(conversation.id)})

        try:
            while True:
                data = await websocket.receive_json()
                user_message = data.get("message", "").strip()

                if not user_message:
                    await websocket.send_text("[ERROR] Empty message")
                    continue

                log.info("chat_message_received", user_id=user_id_str, length=len(user_message))

                # Save the user's message
                await msg_repo.add(conversation.id, role="user", content=user_message)

                # Auto-title the conversation from the first message
                history = await msg_repo.list_for_conversation(conversation.id)
                if len(history) == 1:
                    title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                    await conv_repo.update_title(conversation.id, title)

                trace = tracer.create_trace(
                    name="chat",
                    user_id=user_id_str,
                    metadata={"conversation_id": str(conversation.id)},
                )

                # Build full message history for context-aware responses
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert data analyst. "
                            "Answer questions clearly and concisely. "
                            "When writing code, use Python."
                        ),
                    }
                ]
                for m in history:
                    messages.append({"role": m.role, "content": m.content})

                full_response = ""
                async for token_text in llm.stream(messages=messages):
                    full_response += token_text
                    await websocket.send_text(token_text)

                # Save the assistant's response
                await msg_repo.add(conversation.id, role="assistant", content=full_response)

                tracer.log_generation(
                    trace=trace,
                    name="chat_response",
                    model=llm.primary_model,
                    prompt=user_message,
                    completion=full_response,
                )

                await websocket.send_text("[DONE]")
                log.info("chat_response_complete", user_id=user_id_str)

        except WebSocketDisconnect:
            log.info("websocket_disconnected", user_id=user_id_str)
        except Exception as e:
            log.error("websocket_error", user_id=user_id_str, error=str(e))
            await websocket.send_text(f"[ERROR] {str(e)}")
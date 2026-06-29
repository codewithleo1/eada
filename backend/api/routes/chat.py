from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from backend.llm.gateway import llm
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer
from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """Protected WebSocket streaming chat endpoint.

    WebSockets can't send Authorization headers like HTTP requests.
    The standard solution is to pass the token as a query parameter:
        ws://localhost:8000/chat/ws?token=<your_jwt>

    Flow:
        1. Verify JWT token before accepting connection
        2. Check rate limit for this user
        3. Accept connection
        4. Stream responses
    """
    # Verify token BEFORE accepting the connection
    # If invalid, the connection is rejected immediately
    try:
        payload = verify_token(token)
        user_id = payload.get("sub", "anonymous")
    except Exception:
        await websocket.close(code=4001)
        return

    # Check rate limit before accepting
    try:
        check_rate_limit(user_id)
    except Exception:
        await websocket.close(code=4029)
        return

    await websocket.accept()
    log.info("websocket_connected", user_id=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()

            if not user_message:
                await websocket.send_text("[ERROR] Empty message")
                continue

            log.info("chat_message_received", user_id=user_id, length=len(user_message))

            trace = tracer.create_trace(
                name="chat",
                user_id=user_id,
                metadata={"message_length": len(user_message)},
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert data analyst. "
                        "Answer questions clearly and concisely. "
                        "When writing code, use Python."
                    ),
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ]

            async for token_text in llm.stream(messages=messages):
                await websocket.send_text(token_text)

            await websocket.send_text("[DONE]")
            log.info("chat_response_complete", user_id=user_id)

    except WebSocketDisconnect:
        log.info("websocket_disconnected", user_id=user_id)
    except Exception as e:
        log.error("websocket_error", user_id=user_id, error=str(e))
        await websocket.send_text(f"[ERROR] {str(e)}")
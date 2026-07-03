import json
import re
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.llm.gateway import llm
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer
from backend.api.middleware.auth import verify_token
from backend.api.middleware.rate_limit import check_rate_limit
from backend.db.session import async_session_factory
from backend.db.repositories import ConversationRepository, MessageRepository
from backend.tools.file_tool import get_file_info, FileToolError
from backend.tools.sql_tool import execute_query, SqlToolError

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _build_system_prompt(file_info: dict | None) -> str:
    """
    Build the system prompt.
    If a file is attached, include schema + sample so the LLM can write SQL.
    """
    if file_info is None:
        return (
            "You are an expert data analyst. "
            "Answer questions clearly and concisely. "
            "When writing code, use Python."
        )

    columns_desc = ", ".join(
        f"{c['name']} ({c['dtype']})" for c in file_info["columns"]
    )
    sample_json = json.dumps(file_info["sample"][:3], indent=2)

    return f"""You are an expert data analyst with access to a data file.

File: {file_info['file_path']}
Rows: {file_info['row_count']}
Columns: {columns_desc}

Sample data (first 3 rows):
{sample_json}

When the user asks a question about the data:
1. Write a DuckDB SQL query to answer it.
2. Wrap the SQL in a ```sql ... ``` code block.
3. Use 'data' as the table name in your SQL (e.g. SELECT * FROM data LIMIT 5).
4. After the SQL block, write a brief explanation of what the query does.
5. The system will execute your SQL and show the results to the user automatically.

If the question is not about the data, answer normally without SQL."""


def _extract_sql(text: str) -> str | None:
    """
    Extract the first SQL query from a ```sql ... ``` code block.
    Returns None if no SQL block found.
    """
    pattern = r"```sql\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _format_results(sql_result: dict) -> str:
    """
    Format DuckDB query results as a readable markdown table string
    to send back to the LLM for final formatting.
    """
    if not sql_result["rows"]:
        return "The query returned no results."

    cols = sql_result["columns"]
    rows = sql_result["rows"]

    # Build markdown table
    header = " | ".join(cols)
    separator = " | ".join(["---"] * len(cols))
    lines = [header, separator]

    for row in rows[:20]:  # show max 20 rows in LLM context
        line = " | ".join(str(row.get(c, "")) for c in cols)
        lines.append(line)

    table = "\n".join(lines)

    note = ""
    if sql_result["truncated"]:
        note = f"\n\n_(Results truncated to {sql_result['row_count']} rows)_"
    elif len(rows) > 20:
        note = f"\n\n_(Showing 20 of {sql_result['row_count']} rows)_"

    return f"Query results:\n\n{table}{note}"


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    conversation_id: str | None = Query(None, description="Existing conversation UUID"),
    file_id: str | None = Query(None, description="UUID of an uploaded file to analyse"),
) -> None:
    """Protected, persistent WebSocket streaming chat endpoint.

    Connect with:
        ws://localhost:8000/chat/ws?token=<jwt>
        ws://localhost:8000/chat/ws?token=<jwt>&conversation_id=<uuid>
        ws://localhost:8000/chat/ws?token=<jwt>&file_id=<uuid>
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
    log.info("websocket_connected", user_id=user_id_str, file_id=file_id)

    # Load file info once at connection time if file_id provided
    file_info = None
    if file_id:
        try:
            from pathlib import Path
            # Find the file — it could be any supported extension
            from backend.tools.file_tool import SUPPORTED_EXTENSIONS
            uploads_dir = Path("uploads")
            matched = None
            for ext in SUPPORTED_EXTENSIONS:
                candidate = uploads_dir / f"{file_id}{ext}"
                if candidate.exists():
                    matched = candidate
                    break

            if matched is None:
                await websocket.send_text(f"[ERROR] File not found for file_id: {file_id}")
                await websocket.close()
                return

            file_info = get_file_info(str(matched))
            log.info("file_loaded_for_chat", file_id=file_id, rows=file_info["row_count"])

        except FileToolError as e:
            await websocket.send_text(f"[ERROR] Could not load file: {e}")
            await websocket.close()
            return

    async with async_session_factory() as db:
        conv_repo = ConversationRepository(db)
        msg_repo = MessageRepository(db)

        # Resume existing conversation or start a new one
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
            log.info("new_conversation_started", conversation_id=str(conversation.id))

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

                log.info("chat_message_received", user_id=user_id_str, length=len(user_message))

                await msg_repo.add(conversation.id, role="user", content=user_message)

                history = await msg_repo.list_for_conversation(conversation.id)
                if len(history) == 1:
                    title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                    await conv_repo.update_title(conversation.id, title)

                trace = tracer.create_trace(
                    name="chat",
                    user_id=user_id_str,
                    metadata={"conversation_id": str(conversation.id)},
                )

                # Build messages with system prompt (includes schema if file attached)
                messages = [
                    {
                        "role": "system",
                        "content": _build_system_prompt(file_info),
                    }
                ]
                for m in history:
                    messages.append({"role": m.role, "content": m.content})

                # --- First LLM call: get SQL + explanation ---
                full_response = ""
                async for token_text in llm.stream(messages=messages):
                    full_response += token_text
                    await websocket.send_text(token_text)

                # --- If file attached, try to extract and run SQL ---
                if file_info is not None:
                    sql = _extract_sql(full_response)

                    if sql is not None:
                        log.info("sql_extracted", sql=sql[:120])

                        try:
                            # Replace 'data' table name with actual file reference
                            # sql_tool._execute_on_file handles 'data' view internally
                            sql_result = execute_query(sql, file_info["file_path"])
                            results_text = _format_results(sql_result)

                            log.info(
                                "sql_executed",
                                row_count=sql_result["row_count"],
                            )

                            # Stream a separator then the results
                            await websocket.send_text(f"\n\n---\n\n{results_text}")

                            # --- Second LLM call: summarise results in plain English ---
                            summary_messages = messages + [
                                {"role": "assistant", "content": full_response},
                                {
                                    "role": "user",
                                    "content": (
                                        f"The query returned these results:\n\n{results_text}\n\n"
                                        "Please summarise the key insights in 2-3 plain English sentences."
                                    ),
                                },
                            ]

                            await websocket.send_text("\n\n**Summary:** ")
                            summary = ""
                            async for token_text in llm.stream(messages=summary_messages):
                                summary += token_text
                                await websocket.send_text(token_text)

                            full_response += f"\n\n{results_text}\n\n**Summary:** {summary}"

                        except SqlToolError as e:
                            error_msg = f"\n\n⚠️ SQL execution failed: {e}"
                            await websocket.send_text(error_msg)
                            full_response += error_msg
                            log.error("sql_execution_failed", error=str(e))

                # Save full response including results
                await msg_repo.add(
                    conversation.id, role="assistant", content=full_response
                )

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
"""
analyst.py — Data Analyst agent for the EADA multi-agent graph.
Handles all data file questions using the Phase 4 tool calling infrastructure.
Calls get_file_schema then query_data via complete_with_tools().
Reads:  state["user_message"], state["file_id"], state["plan"]
Writes: state["sql_result"], state["final_answer"], state["next_agent"],
        state["originating_agent"], state["retry_count"]
"""

from __future__ import annotations

import json

from backend.agents.state import AgentState, AGENT_ANALYST, AGENT_CRITIC
from backend.llm.gateway import llm
from backend.tools.executor import execute_tool_call
from backend.tools.registry import get_tools_for_context
from backend.observability.logging import get_logger

log = get_logger(__name__)

MAX_TOOL_ITERATIONS = 5


async def analyst_node(state: AgentState) -> AgentState:
    """
    LangGraph node — answers data questions using SQL tool loop.

    Reads:  state["user_message"], state["file_id"], state["plan"], state["retry_count"]
    Writes: state["sql_result"], state["final_answer"], state["next_agent"],
            state["originating_agent"], state["retry_count"]
    """
    user_message = state.get("user_message", "")
    file_id = state.get("file_id")
    plan = state.get("plan", [])
    retry_count = state.get("retry_count", 0)
    critique = state.get("critique", "")

    log.info("analyst.start", message=user_message[:80], file_id=file_id, retry=retry_count)

    if not file_id:
        log.warning("analyst.no_file")
        return {
            "final_answer": "No data file is attached. Please upload a file first.",
            "next_agent": AGENT_CRITIC,
            "originating_agent": AGENT_ANALYST,
            "retry_count": retry_count,
        }

    # On retry, include critique in task so LLM knows what to fix
    task = "\n".join(plan) if plan else user_message
    if retry_count > 0 and critique:
        task = (
            f"Previous answer was rejected with this feedback:\n{critique}\n\n"
            f"Please try again and address the feedback.\n\nOriginal task:\n{task}"
        )

    system_prompt = (
        "You are an expert data analyst. "
        "Use get_file_schema to inspect the file first, "
        "then use query_data to answer the question. "
        f"The uploaded file ID is: {file_id}. "
        "Always use 'data' as the table name in SQL queries."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    tools = get_tools_for_context(has_file=True, has_doc=False)
    sql_result = {}
    final_answer = ""

    # Tool calling loop
    for iteration in range(MAX_TOOL_ITERATIONS):
        log.info("analyst.tool_iteration", iteration=iteration)

        response = await llm.complete_with_tools(
            messages=messages,
            tools=tools,
        )

        if not response.wants_tool:
            final_answer = response.text or ""
            log.info("analyst.done", iterations=iteration + 1)
            break

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

        for tc in response.tool_calls:
            result_str = await execute_tool_call(tc.name, tc.arguments)
            log.info("analyst.tool_result", name=tc.name, length=len(result_str))

            if tc.name == "query_data":
                try:
                    sql_result = json.loads(result_str)
                except json.JSONDecodeError:
                    sql_result = {"raw": result_str}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    if not final_answer:
        final_answer = await llm.complete(messages=messages)

    return {
        "sql_result": sql_result,
        "final_answer": final_answer,
        "next_agent": AGENT_CRITIC,
        "originating_agent": AGENT_ANALYST,
        "retry_count": retry_count + 1,
    }

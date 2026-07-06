"""
planner.py — Planner agent for the EADA multi-agent graph.

Handles complex multi-step requests by breaking them into
an ordered list of steps the Orchestrator executes one by one.

Reads:  state["user_message"], state["file_id"], state["doc_id"]
Writes: state["plan"], state["next_agent"]
"""

from __future__ import annotations

from backend.agents.state import AgentState, AGENT_ANALYST, AGENT_RAG, AGENT_SUMMARIZER
from backend.llm.gateway import llm
from backend.observability.logging import get_logger

log = get_logger(__name__)


def _build_planner_prompt(state: AgentState) -> str:
    has_file = bool(state.get("file_id"))
    has_doc = bool(state.get("doc_id"))
    user_message = state.get("user_message", "")

    tools_available = []
    if has_file:
        tools_available.append("- Data file analysis (SQL queries, aggregations, charts)")
    if has_doc:
        tools_available.append("- Document search (find relevant sections, extract facts)")
    tools_available.append("- General knowledge and summarization")

    tools_str = "\n".join(tools_available)

    return f"""You are a planning agent. Break the user request into a numbered list of clear, ordered steps.

AVAILABLE CAPABILITIES:
{tools_str}

USER REQUEST:
{user_message}

Rules:
- Each step must be a single, actionable instruction
- Maximum 5 steps
- Steps must be executable in order
- Be specific — say exactly what to query or search for
- Output ONLY the numbered list, no preamble or explanation

Example format:
1. Query the data file for total sales by region
2. Search the document for the executive summary
3. Combine results into a final answer

Your plan:"""


async def planner_node(state: AgentState) -> AgentState:
    """
    LangGraph node — breaks complex requests into ordered steps.

    Reads:  state["user_message"], state["file_id"], state["doc_id"]
    Writes: state["plan"], state["next_agent"]
    """
    user_message = state.get("user_message", "")
    log.info("planner.start", message=user_message[:80])

    prompt = _build_planner_prompt(state)

    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse numbered list into individual steps
        lines = response.strip().split("\n")
        steps = []
        for line in lines:
            line = line.strip()
            if line and line[0].isdigit():
                # Strip leading number and punctuation e.g. "1. " or "1) "
                step = line.lstrip("0123456789").lstrip(".").lstrip(")").strip()
                if step:
                    steps.append(step)

        if not steps:
            steps = [user_message]

        log.info("planner.done", num_steps=len(steps), steps=steps)

        # Decide first agent based on available context
        has_file = bool(state.get("file_id"))
        has_doc = bool(state.get("doc_id"))

        if has_file:
            first_agent = AGENT_ANALYST
        elif has_doc:
            first_agent = AGENT_RAG
        else:
            first_agent = AGENT_SUMMARIZER

        return {
            "plan": steps,
            "next_agent": first_agent,
        }

    except Exception as e:
        log.error("planner.failed", error=str(e))
        return {
            "plan": [user_message],
            "next_agent": AGENT_SUMMARIZER,
            "error": str(e),
        }

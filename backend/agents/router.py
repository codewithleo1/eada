"""
router.py — Router agent for the EADA multi-agent graph.

The Router is the first node every user message hits.
It reads the message + context and decides which specialist handles it.

It does NOT answer the question — it only routes.
Output: sets state["next_agent"] to one of the VALID_AGENTS names.
"""

from __future__ import annotations

from backend.agents.state import (
    AgentState,
    VALID_AGENTS,
    AGENT_SUMMARIZER,
)
from backend.llm.gateway import llm
from backend.observability.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Router prompt
# ---------------------------------------------------------------------------

def _build_router_prompt(state: AgentState) -> str:
    """
    Build the routing decision prompt.
    Gives the LLM exactly the context it needs to route correctly.
    """
    has_file = bool(state.get("file_id"))
    has_doc = bool(state.get("doc_id"))
    user_message = state.get("user_message", "")

    context_lines = []
    if has_file:
        context_lines.append("- An uploaded data file is available (CSV/Excel/JSON/Parquet)")
    if has_doc:
        context_lines.append("- An ingested document is available for Q&A")
    if not has_file and not has_doc:
        context_lines.append("- No file or document attached")

    context = "\n".join(context_lines)

    return f"""You are a routing agent. Read the user message and context, then output EXACTLY ONE word — the name of the agent that should handle this request.

CONTEXT:
{context}

USER MESSAGE:
{user_message}

AGENT OPTIONS:
- analyst    → user is asking a question about data in the uploaded file (counts, sums, filters, comparisons, charts)
- rag_agent  → user is asking a question about content in the ingested document
- planner    → user is asking a complex multi-step question that needs both data analysis AND document search, or requires multiple operations
- summarizer → simple conversational question, general knowledge, or no tools needed

Rules:
- If a file is available and the question is about data → analyst
- If a document is available and the question is about its content → rag_agent
- If both are needed or the request has multiple steps → planner
- If neither file nor document is relevant → summarizer
- Output ONLY the agent name, nothing else. No punctuation, no explanation.

Your answer:"""


# ---------------------------------------------------------------------------
# Router node function
# ---------------------------------------------------------------------------

async def router_node(state: AgentState) -> AgentState:
    """
    LangGraph node — routes the user message to the correct specialist agent.

    Reads:  state["user_message"], state["file_id"], state["doc_id"]
    Writes: state["next_agent"]
    """
    user_message = state.get("user_message", "")
    log.info("router.start", message=user_message[:80])

    prompt = _build_router_prompt(state)

    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}]
        )
        # Clean up response — LLM sometimes adds punctuation or whitespace
        decision = response.strip().lower().rstrip(".")

        # Validate — fall back to summarizer if LLM returns unexpected value
        if decision not in VALID_AGENTS:
            log.warning(
                "router.invalid_decision",
                decision=decision,
                fallback=AGENT_SUMMARIZER,
            )
            decision = AGENT_SUMMARIZER

        log.info("router.decision", next_agent=decision)
        return {"next_agent": decision}

    except Exception as e:
        log.error("router.failed", error=str(e))
        # On failure, route to summarizer as safe fallback
        return {"next_agent": AGENT_SUMMARIZER, "error": str(e)}

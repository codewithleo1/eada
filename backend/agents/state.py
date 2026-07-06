"""
state.py — shared state schema for the EADA multi-agent graph.

Every agent in the LangGraph graph reads from and writes to this state.
It flows through every node like a shared whiteboard.

Design decisions:
- TypedDict required by LangGraph (not Pydantic)
- Annotated[list, operator.add] for list fields — appends instead of replaces
- All fields optional except messages — agents only populate what they touch
"""

from __future__ import annotations

import operator
from typing import Annotated, Any
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """
    Shared state that flows through every node in the agent graph.

    Fields:
        messages:     Full conversation history in OpenAI format.
                      Uses operator.add so each agent appends, not replaces.
        user_message: The current user message being processed.
        file_id:      UUID of uploaded data file (CSV/Excel/JSON/Parquet).
        doc_id:       UUID of ingested document for RAG Q&A.
        plan:         Ordered list of steps from the Planner agent.
        sql_result:   Query result dict from the Data Analyst agent.
        rag_context:  Retrieved document chunks from the RAG agent.
        code_result:  Output string from the Code Executor agent.
        critique:     Feedback string from the Critic agent.
        final_answer: The answer ready to send to the user.
        next_agent:   Which agent should run next (set by Router).
        error:        Error message if any agent fails.
        iteration:    How many agent iterations have run (circuit breaker).
    """

    # Core conversation — append-only
    messages: Annotated[list[dict], operator.add]

    # Current request context
    user_message: str
    file_id: str | None
    doc_id: str | None

    # Agent outputs — each agent writes to its own field
    plan: list[str]
    sql_result: dict[str, Any]
    rag_context: str
    code_result: str
    critique: str
    final_answer: str

    # Routing and control
    next_agent: str
    error: str | None
    iteration: int


# ---------------------------------------------------------------------------
# Valid agent names — used by Router to validate routing decisions
# ---------------------------------------------------------------------------

AGENT_ROUTER = "router"
AGENT_PLANNER = "planner"
AGENT_ANALYST = "analyst"
AGENT_RAG = "rag_agent"
AGENT_CRITIC = "critic"
AGENT_SUMMARIZER = "summarizer"
AGENT_END = "end"

VALID_AGENTS = {
    AGENT_ROUTER,
    AGENT_PLANNER,
    AGENT_ANALYST,
    AGENT_RAG,
    AGENT_CRITIC,
    AGENT_SUMMARIZER,
    AGENT_END,
}

# Maximum agent iterations before forcing a response (circuit breaker)
MAX_ITERATIONS = 10

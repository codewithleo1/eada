"""
graph.py — LangGraph orchestrator for the EADA multi-agent system.

Wires all agents into a stateful graph:

START → router → [analyst | rag_agent | planner | summarizer] → critic → summarizer → END

The conditional edge reads state["next_agent"] to decide routing.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from backend.agents.state import (
    AgentState,
    AGENT_ROUTER,
    AGENT_PLANNER,
    AGENT_ANALYST,
    AGENT_RAG,
    AGENT_CRITIC,
    AGENT_SUMMARIZER,
    MAX_ITERATIONS,
)
from backend.agents.router import router_node
from backend.agents.planner import planner_node
from backend.agents.analyst import analyst_node
from backend.agents.rag_agent import rag_agent_node
from backend.agents.critic import critic_node, summarizer_node
from backend.observability.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Conditional edge — reads next_agent from state
# ---------------------------------------------------------------------------

def route_after_router(state: AgentState) -> str:
    """
    Called after the router node.
    Returns the name of the next node to execute.
    """
    next_agent = state.get("next_agent", AGENT_SUMMARIZER)
    iteration = state.get("iteration", 0)

    # Circuit breaker — force end if too many iterations
    if iteration >= MAX_ITERATIONS:
        log.warning("graph.circuit_breaker", iteration=iteration)
        return AGENT_SUMMARIZER

    log.info("graph.routing", next_agent=next_agent)

    # Map agent names to node names
    valid_routes = {
        AGENT_ANALYST: AGENT_ANALYST,
        AGENT_RAG: AGENT_RAG,
        AGENT_PLANNER: AGENT_PLANNER,
        AGENT_SUMMARIZER: AGENT_SUMMARIZER,
    }

    return valid_routes.get(next_agent, AGENT_SUMMARIZER)


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Build the EADA multi-agent graph.

    Returns a compiled LangGraph StateGraph ready to invoke.
    """
    graph = StateGraph(AgentState)

    # --- Register all nodes ---
    graph.add_node(AGENT_ROUTER, router_node)
    graph.add_node(AGENT_PLANNER, planner_node)
    graph.add_node(AGENT_ANALYST, analyst_node)
    graph.add_node(AGENT_RAG, rag_agent_node)
    graph.add_node(AGENT_CRITIC, critic_node)
    graph.add_node(AGENT_SUMMARIZER, summarizer_node)

    # --- Entry point ---
    graph.set_entry_point(AGENT_ROUTER)

    # --- Conditional routing after router ---
    graph.add_conditional_edges(
        AGENT_ROUTER,
        route_after_router,
        {
            AGENT_ANALYST: AGENT_ANALYST,
            AGENT_RAG: AGENT_RAG,
            AGENT_PLANNER: AGENT_PLANNER,
            AGENT_SUMMARIZER: AGENT_SUMMARIZER,
        },
    )

    # --- Planner always goes to analyst first ---
    graph.add_edge(AGENT_PLANNER, AGENT_ANALYST)

    # --- Analyst and RAG always go to critic ---
    graph.add_edge(AGENT_ANALYST, AGENT_CRITIC)
    graph.add_edge(AGENT_RAG, AGENT_CRITIC)

    # --- Critic always goes to summarizer ---
    graph.add_edge(AGENT_CRITIC, AGENT_SUMMARIZER)

    # --- Summarizer ends the graph ---
    graph.add_edge(AGENT_SUMMARIZER, END)

    compiled = graph.compile()
    log.info("graph.compiled")
    return compiled


# ---------------------------------------------------------------------------
# Singleton — compile once at import time
# ---------------------------------------------------------------------------

agent_graph = build_graph()

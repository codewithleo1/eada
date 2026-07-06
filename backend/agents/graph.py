"""
graph.py — LangGraph orchestrator for the EADA multi-agent system.

Phase 6 update: self-correction loop added after Critic.

Graph flow:
START → router → [analyst|rag_agent|planner|summarizer]
               → critic → PASS       → summarizer → END
                        → NEEDS_IMPROVEMENT + retry < 2 → analyst or rag_agent
                        → NEEDS_IMPROVEMENT + retry >= 2 → summarizer → END
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

MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Conditional edge — after Router
# ---------------------------------------------------------------------------

def route_after_router(state: AgentState) -> str:
    """Route to correct specialist after Router decides."""
    next_agent = state.get("next_agent", AGENT_SUMMARIZER)
    iteration = state.get("iteration", 0)

    if iteration >= MAX_ITERATIONS:
        log.warning("graph.circuit_breaker", iteration=iteration)
        return AGENT_SUMMARIZER

    log.info("graph.routing_after_router", next_agent=next_agent)

    valid_routes = {
        AGENT_ANALYST: AGENT_ANALYST,
        AGENT_RAG: AGENT_RAG,
        AGENT_PLANNER: AGENT_PLANNER,
        AGENT_SUMMARIZER: AGENT_SUMMARIZER,
    }
    return valid_routes.get(next_agent, AGENT_SUMMARIZER)


# ---------------------------------------------------------------------------
# Conditional edge — after Critic (self-correction)
# ---------------------------------------------------------------------------

def route_after_critic(state: AgentState) -> str:
    """
    Self-correction routing after Critic reviews the answer.

    - PASS or retry limit hit → Summarizer
    - NEEDS_IMPROVEMENT + retry < MAX_RETRIES → back to originating agent
    """
    critique = state.get("critique", "")
    retry_count = state.get("retry_count", 0)
    originating_agent = state.get("originating_agent", AGENT_SUMMARIZER)

    needs_improvement = "NEEDS_IMPROVEMENT" in critique.upper()

    if not needs_improvement:
        log.info("graph.critic_pass", retry_count=retry_count)
        return AGENT_SUMMARIZER

    if retry_count >= MAX_RETRIES:
        log.warning(
            "graph.retry_limit_hit",
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
        )
        return AGENT_SUMMARIZER

    # Route back to originating agent for a retry
    log.info(
        "graph.self_correction",
        retry_count=retry_count,
        returning_to=originating_agent,
    )

    valid_retry_targets = {AGENT_ANALYST, AGENT_RAG}
    if originating_agent in valid_retry_targets:
        return originating_agent

    return AGENT_SUMMARIZER


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Build the EADA multi-agent graph with self-correction loop.
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

    # --- Conditional routing after Router ---
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

    # --- Conditional routing after Critic (self-correction) ---
    graph.add_conditional_edges(
        AGENT_CRITIC,
        route_after_critic,
        {
            AGENT_ANALYST: AGENT_ANALYST,
            AGENT_RAG: AGENT_RAG,
            AGENT_SUMMARIZER: AGENT_SUMMARIZER,
        },
    )

    # --- Summarizer ends the graph ---
    graph.add_edge(AGENT_SUMMARIZER, END)

    compiled = graph.compile()
    log.info("graph.compiled_with_self_correction")
    return compiled


# ---------------------------------------------------------------------------
# Singleton — compile once at import time
# ---------------------------------------------------------------------------

agent_graph = build_graph()

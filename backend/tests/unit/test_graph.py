"""
test_graph.py — unit tests for route_after_critic in backend/agents/graph.py

Tests the self-correction routing logic:
  - PASS verdict → summarizer
  - NEEDS_IMPROVEMENT + retry < MAX_RETRIES → originating agent
  - NEEDS_IMPROVEMENT + retry >= MAX_RETRIES → summarizer
  - Missing critique → summarizer
  - Invalid originating_agent → summarizer
"""

from backend.agents.graph import route_after_critic
from backend.agents.state import AGENT_ANALYST, AGENT_RAG, AGENT_SUMMARIZER


# ---------------------------------------------------------------------------
# PASS verdict
# ---------------------------------------------------------------------------

def test_pass_verdict_routes_to_summarizer():
    state = {
        "critique": "VERDICT: PASS\nFEEDBACK: Answer is correct.",
        "retry_count": 0,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


def test_pass_verdict_routes_to_summarizer_regardless_of_retry():
    state = {
        "critique": "VERDICT: PASS\nFEEDBACK: Good.",
        "retry_count": 1,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


# ---------------------------------------------------------------------------
# NEEDS_IMPROVEMENT verdict — retry available
# ---------------------------------------------------------------------------

def test_needs_improvement_routes_back_to_analyst():
    state = {
        "critique": "VERDICT: NEEDS_IMPROVEMENT\nFEEDBACK: Missing totals.",
        "retry_count": 0,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_ANALYST


def test_needs_improvement_routes_back_to_rag_agent():
    state = {
        "critique": "VERDICT: NEEDS_IMPROVEMENT\nFEEDBACK: Incomplete answer.",
        "retry_count": 0,
        "originating_agent": AGENT_RAG,
    }
    result = route_after_critic(state)
    assert result == AGENT_RAG


def test_needs_improvement_retry_count_1_still_retries():
    state = {
        "critique": "VERDICT: NEEDS_IMPROVEMENT\nFEEDBACK: Still wrong.",
        "retry_count": 1,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_ANALYST


# ---------------------------------------------------------------------------
# NEEDS_IMPROVEMENT verdict — retry limit hit
# ---------------------------------------------------------------------------

def test_needs_improvement_at_max_retries_routes_to_summarizer():
    state = {
        "critique": "VERDICT: NEEDS_IMPROVEMENT\nFEEDBACK: Still wrong.",
        "retry_count": 2,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


def test_needs_improvement_above_max_retries_routes_to_summarizer():
    state = {
        "critique": "VERDICT: NEEDS_IMPROVEMENT\nFEEDBACK: Still wrong.",
        "retry_count": 10,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_critique_routes_to_summarizer():
    state = {
        "critique": "",
        "retry_count": 0,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


def test_missing_critique_routes_to_summarizer():
    state = {
        "retry_count": 0,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


def test_invalid_originating_agent_routes_to_summarizer():
    state = {
        "critique": "VERDICT: NEEDS_IMPROVEMENT\nFEEDBACK: Wrong.",
        "retry_count": 0,
        "originating_agent": "unknown_agent",
    }
    result = route_after_critic(state)
    assert result == AGENT_SUMMARIZER


def test_needs_improvement_case_insensitive():
    state = {
        "critique": "verdict: needs_improvement\nfeedback: wrong.",
        "retry_count": 0,
        "originating_agent": AGENT_ANALYST,
    }
    result = route_after_critic(state)
    assert result == AGENT_ANALYST

"""
critic.py — Critic and Summarizer agents for the EADA multi-agent graph.

Critic:     Reviews final_answer for quality and completeness.
Summarizer: Produces a clean, concise response ready for the user.

These two agents always run in sequence at the end of every agent pipeline.
"""

from __future__ import annotations

from backend.agents.state import AgentState, AGENT_SUMMARIZER, AGENT_END
from backend.llm.gateway import llm
from backend.observability.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Critic node
# ---------------------------------------------------------------------------

async def critic_node(state: AgentState) -> AgentState:
    """
    LangGraph node — reviews final_answer for quality.

    Reads:  state["final_answer"], state["user_message"]
    Writes: state["critique"], state["next_agent"]
    """
    final_answer = state.get("final_answer", "")
    user_message = state.get("user_message", "")

    log.info("critic.start", answer_length=len(final_answer))

    if not final_answer:
        return {
            "critique": "No answer was generated.",
            "next_agent": AGENT_SUMMARIZER,
        }

    prompt = f"""You are a quality reviewer. Evaluate this answer to the user's question.

USER QUESTION:
{user_message}

ANSWER TO REVIEW:
{final_answer}

Review criteria:
1. Does the answer actually address the question?
2. Is it clear and easy to understand?
3. Are there any obvious errors or missing information?

Output format — respond with EXACTLY this structure:
VERDICT: PASS or NEEDS_IMPROVEMENT
FEEDBACK: One sentence explaining your verdict.

Your review:"""

    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}]
        )
        critique = response.strip()
        log.info("critic.done", critique=critique[:80])
    except Exception as e:
        log.error("critic.failed", error=str(e))
        critique = "VERDICT: PASS\nFEEDBACK: Could not review answer."

    return {
        "critique": critique,
        "next_agent": AGENT_SUMMARIZER,
    }


# ---------------------------------------------------------------------------
# Summarizer node
# ---------------------------------------------------------------------------

async def summarizer_node(state: AgentState) -> AgentState:
    """
    LangGraph node — produces clean final response for the user.

    Reads:  state["final_answer"], state["critique"], state["user_message"]
    Writes: state["final_answer"], state["next_agent"]
    """
    final_answer = state.get("final_answer", "")
    critique = state.get("critique", "")
    user_message = state.get("user_message", "")

    log.info("summarizer.start", answer_length=len(final_answer))

    # If critic passed, just clean up formatting
    # If needs improvement, ask LLM to improve it
    needs_improvement = "NEEDS_IMPROVEMENT" in critique.upper()

    if needs_improvement:
        prompt = f"""You are a professional analyst. Improve this answer based on the feedback.

USER QUESTION:
{user_message}

CURRENT ANSWER:
{final_answer}

FEEDBACK:
{critique}

Write an improved, clear, concise answer. Do not mention the review process."""
    else:
        prompt = f"""You are a professional analyst. Polish this answer for the user.

USER QUESTION:
{user_message}

ANSWER:
{final_answer}

Make it clear and well-formatted. Keep all facts and numbers exactly as they are.
Do not add new information. Do not mention the review process."""

    try:
        polished = await llm.complete(
            messages=[{"role": "user", "content": prompt}]
        )
        log.info("summarizer.done", length=len(polished))
    except Exception as e:
        log.error("summarizer.failed", error=str(e))
        polished = final_answer  # Fall back to unpolished answer

    return {
        "final_answer": polished,
        "next_agent": AGENT_END,
    }

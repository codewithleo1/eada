"""
scorer.py — Evaluation scorer for EADA agent responses.

Scores every agent response on three dimensions:
  - Relevance:     Does the answer address the question? (40%)
  - Completeness:  Are all parts of the question answered? (40%)
  - Clarity:       Is the answer clear and well-formatted? (20%)

Each dimension scored 1-5 by LLM. Final score normalised to 0.0-1.0.

Usage:
    scorer = ResponseScorer()
    result = await scorer.score(question, answer)
    print(result)
    # {"relevance": 4, "completeness": 3, "clarity": 5, "final_score": 0.76}
"""

from __future__ import annotations

from backend.llm.gateway import llm
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Weights must sum to 1.0
WEIGHTS = {
    "relevance": 0.40,
    "completeness": 0.40,
    "clarity": 0.20,
}


class ResponseScorer:
    """
    LLM-based scorer for agent responses.
    Each instance is stateless — safe to share across requests.
    """

    async def score(
        self,
        question: str,
        answer: str,
    ) -> dict:
        """
        Score an answer against the question.

        Args:
            question: the user's original question
            answer:   the agent's response to evaluate

        Returns:
            {
                "relevance":     int (1-5),
                "completeness":  int (1-5),
                "clarity":       int (1-5),
                "final_score":   float (0.0-1.0),
                "passed":        bool (True if final_score >= 0.6)
            }
        """
        prompt = f"""You are an evaluation assistant. Score this answer on three dimensions.

QUESTION:
{question}

ANSWER:
{answer}

Score each dimension from 1 to 5:
- 1: Very poor
- 3: Acceptable
- 5: Excellent

RELEVANCE (does the answer address the question?):
COMPLETENESS (are all parts of the question answered?):
CLARITY (is the answer clear and well-formatted?):

Output ONLY these three lines with integer scores, exactly in this format:
RELEVANCE: <1-5>
COMPLETENESS: <1-5>
CLARITY: <1-5>"""

        try:
            response = await llm.complete(
                messages=[{"role": "user", "content": prompt}]
            )
            scores = _parse_scores(response)
        except Exception as e:
            log.warning("scorer.llm_failed", error=str(e))
            # Return neutral scores on failure
            scores = {"relevance": 3, "completeness": 3, "clarity": 3}

        final_score = _compute_final_score(scores)
        passed = final_score >= 0.6

        result = {
            "relevance": scores.get("relevance", 3),
            "completeness": scores.get("completeness", 3),
            "clarity": scores.get("clarity", 3),
            "final_score": round(final_score, 3),
            "passed": passed,
        }

        log.info(
            "scorer.done",
            final_score=result["final_score"],
            passed=passed,
        )

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_scores(response: str) -> dict:
    """
    Parse LLM score response into a dict.

    Expected format:
        RELEVANCE: 4
        COMPLETENESS: 3
        CLARITY: 5

    Falls back to 3 for any unparseable line.
    """
    scores = {}
    dimension_map = {
        "RELEVANCE": "relevance",
        "COMPLETENESS": "completeness",
        "CLARITY": "clarity",
    }

    for line in response.strip().split("\n"):
        line = line.strip()
        for label, key in dimension_map.items():
            if line.startswith(label + ":"):
                raw = line.split(":", 1)[1].strip()
                try:
                    val = int(raw)
                    scores[key] = max(1, min(5, val))  # clamp to 1-5
                except ValueError:
                    scores[key] = 3
                break

    # Fill any missing dimensions with neutral score
    for key in dimension_map.values():
        if key not in scores:
            scores[key] = 3

    return scores


def _compute_final_score(scores: dict) -> float:
    """
    Compute weighted average score normalised to 0.0-1.0.
    Input scores are 1-5, output is 0.0-1.0.
    """
    raw = sum(scores.get(dim, 3) * weight for dim, weight in WEIGHTS.items())
    # Normalise: min=1.0, max=5.0 → 0.0-1.0
    return (raw - 1.0) / 4.0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

scorer = ResponseScorer()

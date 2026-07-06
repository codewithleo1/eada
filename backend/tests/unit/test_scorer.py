"""
test_scorer.py — unit tests for backend/evaluation/scorer.py

Mocks LLM calls entirely — no real API calls.
Tests:
  - _parse_scores correctly extracts dimension scores
  - _compute_final_score produces correct weighted average
  - score() returns correct structure on success
  - score() returns neutral scores when LLM fails
  - passed=True when final_score >= 0.6
  - passed=False when final_score < 0.6
"""

import pytest
from unittest.mock import AsyncMock, patch
from backend.evaluation.scorer import (
    ResponseScorer,
    _parse_scores,
    _compute_final_score,
)


# ---------------------------------------------------------------------------
# _parse_scores
# ---------------------------------------------------------------------------

def test_parse_scores_valid_response():
    response = "RELEVANCE: 4\nCOMPLETENESS: 3\nCLARITY: 5"
    scores = _parse_scores(response)
    assert scores["relevance"] == 4
    assert scores["completeness"] == 3
    assert scores["clarity"] == 5


def test_parse_scores_clamps_above_5():
    response = "RELEVANCE: 9\nCOMPLETENESS: 3\nCLARITY: 5"
    scores = _parse_scores(response)
    assert scores["relevance"] == 5


def test_parse_scores_clamps_below_1():
    response = "RELEVANCE: 0\nCOMPLETENESS: 3\nCLARITY: 5"
    scores = _parse_scores(response)
    assert scores["relevance"] == 1


def test_parse_scores_falls_back_on_invalid():
    response = "RELEVANCE: abc\nCOMPLETENESS: 3\nCLARITY: 5"
    scores = _parse_scores(response)
    assert scores["relevance"] == 3


def test_parse_scores_fills_missing_dimensions():
    response = "RELEVANCE: 4"
    scores = _parse_scores(response)
    assert "completeness" in scores
    assert "clarity" in scores
    assert scores["completeness"] == 3
    assert scores["clarity"] == 3


# ---------------------------------------------------------------------------
# _compute_final_score
# ---------------------------------------------------------------------------

def test_compute_final_score_all_fives():
    scores = {"relevance": 5, "completeness": 5, "clarity": 5}
    result = _compute_final_score(scores)
    assert result == 1.0


def test_compute_final_score_all_ones():
    scores = {"relevance": 1, "completeness": 1, "clarity": 1}
    result = _compute_final_score(scores)
    assert result == 0.0


def test_compute_final_score_all_threes():
    scores = {"relevance": 3, "completeness": 3, "clarity": 3}
    result = _compute_final_score(scores)
    assert abs(result - 0.5) < 0.01


def test_compute_final_score_weighted_correctly():
    # relevance=5 (40%), completeness=1 (40%), clarity=5 (20%)
    # raw = 5*0.4 + 1*0.4 + 5*0.2 = 2.0 + 0.4 + 1.0 = 3.4
    # normalised = (3.4 - 1) / 4 = 0.6
    scores = {"relevance": 5, "completeness": 1, "clarity": 5}
    result = _compute_final_score(scores)
    assert abs(result - 0.6) < 0.01


# ---------------------------------------------------------------------------
# ResponseScorer.score()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_returns_correct_structure():
    mock_response = "RELEVANCE: 4\nCOMPLETENESS: 4\nCLARITY: 4"

    with patch(
        "backend.evaluation.scorer.llm.complete",
        new=AsyncMock(return_value=mock_response),
    ):
        s = ResponseScorer()
        result = await s.score("What is total sales?", "Total sales is $350,000.")

    assert "relevance" in result
    assert "completeness" in result
    assert "clarity" in result
    assert "final_score" in result
    assert "passed" in result
    assert isinstance(result["final_score"], float)
    assert isinstance(result["passed"], bool)


@pytest.mark.asyncio
async def test_score_passed_true_when_high_scores():
    mock_response = "RELEVANCE: 5\nCOMPLETENESS: 5\nCLARITY: 5"

    with patch(
        "backend.evaluation.scorer.llm.complete",
        new=AsyncMock(return_value=mock_response),
    ):
        s = ResponseScorer()
        result = await s.score("question", "answer")

    assert result["passed"] is True
    assert result["final_score"] == 1.0


@pytest.mark.asyncio
async def test_score_passed_false_when_low_scores():
    mock_response = "RELEVANCE: 1\nCOMPLETENESS: 1\nCLARITY: 1"

    with patch(
        "backend.evaluation.scorer.llm.complete",
        new=AsyncMock(return_value=mock_response),
    ):
        s = ResponseScorer()
        result = await s.score("question", "answer")

    assert result["passed"] is False
    assert result["final_score"] == 0.0


@pytest.mark.asyncio
async def test_score_returns_neutral_on_llm_failure():
    with patch(
        "backend.evaluation.scorer.llm.complete",
        new=AsyncMock(side_effect=RuntimeError("API down")),
    ):
        s = ResponseScorer()
        result = await s.score("question", "answer")

    assert result["relevance"] == 3
    assert result["completeness"] == 3
    assert result["clarity"] == 3
    assert result["passed"] is False  # neutral score 0.5 < 0.6 threshold


"""Typed state definition for the LangGraph evaluation workflow."""

from typing import TypedDict


class EvaluationState(TypedDict):
    """State object passed through the evaluation LangGraph nodes.

    Each field tracks data flowing between analysis steps:
    technical, communication, cultural, and scoring.
    """

    session_id: str
    transcript: list[dict[str, str]]
    assessment_details: dict[str, object]

    technical_analysis: str | None
    communication_analysis: str | None
    cultural_analysis: str | None

    skill_scores: dict[str, dict[str, object]]

    # Per-skill scores on 0-100 scale: {"React": 65, "SQL": 40, "Python": 80}
    per_skill_scores: dict[str, float]

    scores: dict[str, float]
    summary: str | None
    explanation: str | None
    recommendation: str | None
    tie_breaker_subscore: float

    error: str | None

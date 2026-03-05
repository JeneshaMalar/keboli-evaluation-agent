from typing import TypedDict, List, Dict, Any, Optional

class EvaluationState(TypedDict):
    session_id: str
    transcript: List[Dict[str, Any]]
    assessment_details: Dict[str, Any]
    
    technical_analysis: Optional[str]
    communication_analysis: Optional[str]
    cultural_analysis: Optional[str]
    
    skill_scores: Dict[str, Dict[str, Any]]
    
    # Per-skill scores on 0-100 scale: {"React": 65, "SQL": 40, "Python": 80}
    per_skill_scores: Dict[str, float]
    
    scores: Dict[str, float]
    summary: Optional[str]
    explanation: Optional[str]
    recommendation: Optional[str]
    tie_breaker_subscore: float
    
    error: Optional[str]

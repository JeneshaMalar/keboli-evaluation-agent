"""Utilities for processing and normalizing technical skill graphs."""
from typing import Any


def _parse_skills_list(skills_list: list[Any]) -> dict[str, float]:
    result = {}
    for s in skills_list:
        if isinstance(s, dict):
            name = s.get("name", "")
            weight = s.get("weightage", s.get("weight", 0.0))
            if name:
                try:
                    result[name] = float(weight)
                except (ValueError, TypeError):
                    result[name] = 0.0
    return result

def _parse_flat_dict(raw_dict: dict[str, Any]) -> dict[str, float]:
    result = {}
    for key, val in raw_dict.items():
        try:
            w = float(str(val).replace('%', ''))
            if w > 1.0:
                w = w / 100.0
            result[key] = w
        except (ValueError, TypeError):
            continue
    return result

def parse_skill_graph(raw_skill_graph: Any) -> dict[str, float]:
    """
    Normalize the skill_graph from the assessment into a flat {skill_name: weight} dict.
    The interview agent stores it as: {"skills": [{"name": "Java", "weightage": 0.3, ...}]}
    But sometimes it can be a flat dict like {"Java": 0.3, "Python": 0.2}
    """
    if not raw_skill_graph:
        return {}
    
    if isinstance(raw_skill_graph, dict):
        if "skills" in raw_skill_graph and isinstance(raw_skill_graph["skills"], list):
            return _parse_skills_list(raw_skill_graph["skills"])
        return _parse_flat_dict(raw_skill_graph)
    
    return {}


def find_skill_score(skill_evaluations: dict[str, Any], skill_name: str) -> dict[str, Any] | None:
    """
    Fuzzy match a skill name from the graph against the LLM's skill evaluation keys.
    The LLM might use slightly different casing or naming.
    """
    if not skill_evaluations:
        return None

    if skill_name in skill_evaluations:
        val1 = skill_evaluations[skill_name]
        return val1 if isinstance(val1, dict) else None

    lower_name = skill_name.lower()
    for key, val in skill_evaluations.items():
        if key.lower() == lower_name:
            return val if isinstance(val, dict) else None

    for key, val in skill_evaluations.items():
        if lower_name in key.lower() or key.lower() in lower_name:
            return val if isinstance(val, dict) else None

    return None

from typing import Dict, Any, Optional


def parse_skill_graph(raw_skill_graph: Any) -> Dict[str, float]:
    """
    Normalize the skill_graph from the assessment into a flat {skill_name: weight} dict.
    The interview agent stores it as: {"skills": [{"name": "Java", "weightage": 0.3, ...}]}
    But sometimes it can be a flat dict like {"Java": 0.3, "Python": 0.2}
    """
    if not raw_skill_graph:
        return {}

    if isinstance(raw_skill_graph, dict) and "skills" in raw_skill_graph:
        skills_list = raw_skill_graph["skills"]
        if isinstance(skills_list, list):
            result = {}
            for s in skills_list:
                name = s.get("name", "")
                weight = s.get("weightage", s.get("weight", 0.0))
                if name:
                    try:
                        result[name] = float(weight)
                    except (ValueError, TypeError):
                        result[name] = 0.0
            return result

    if isinstance(raw_skill_graph, dict):
        result = {}
        for key, val in raw_skill_graph.items():
            try:
                w = float(str(val).replace('%', '')) 
                if w > 1.0:
                    w = w / 100.0  
                result[key] = w
            except (ValueError, TypeError):
                continue
        return result

    return {}


def find_skill_score(skill_evaluations: Dict, skill_name: str) -> Optional[Dict]:
    """
    Fuzzy match a skill name from the graph against the LLM's skill evaluation keys.
    The LLM might use slightly different casing or naming.
    """
    if not skill_evaluations:
        return None
    
    if skill_name in skill_evaluations:
        return skill_evaluations[skill_name]
    
    lower_name = skill_name.lower()
    for key, val in skill_evaluations.items():
        if key.lower() == lower_name:
            return val
    
    for key, val in skill_evaluations.items():
        if lower_name in key.lower() or key.lower() in lower_name:
            return val
    
    return None
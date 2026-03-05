import json
import re
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from .state import EvaluationState
from .llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from .prompt_manager import PromptManager


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _parse_skill_graph(raw_skill_graph: Any) -> Dict[str, float]:
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


def _find_skill_score(skill_evaluations: Dict, skill_name: str) -> Optional[Dict]:
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


async def analyze_technical_node(state: EvaluationState):
    llm = get_llm(temperature=0)
    transcript_text = "\n".join([f"{t['role']}: {t['text']}" for t in state['transcript']])
    
    raw_skill_graph = state['assessment_details'].get('skill_graph', {})
    
    prompt = PromptManager.get_technical_prompt(transcript_text, str(raw_skill_graph))
    
    resp = await llm.ainvoke([
        SystemMessage(content="You are a rigorous technical evaluator. You MUST output valid JSON. Score strictly using the provided multi-layer rubric. Do not inflate scores. Apply all three evaluation layers for each skill."),
        HumanMessage(content=prompt)
    ])
    
    data = extract_json(resp.content)
    if data and "skill_evaluations" in data:
        # Log multi-layer scores for debugging
        for skill_name, skill_data in data["skill_evaluations"].items():
            relevance = skill_data.get('relevance_score', 'N/A')
            depth = skill_data.get('depth_score', 'N/A')
            composite = skill_data.get('score', 'N/A')
            print(f"[EVAL TECH] {skill_name}: Relevance={relevance}, Depth={depth}, Composite={composite}")
        
        return {
            "technical_analysis": json.dumps(data) if isinstance(data, dict) else str(data),
            "skill_scores": data["skill_evaluations"]
        }
    return {"technical_analysis": resp.content, "skill_scores": {}}

async def analyze_communication_node(state: EvaluationState):
    llm = get_llm(temperature=0)
    transcript_text = "\n".join([f"{t['role']}: {t['text']}" for t in state['transcript']])
    
    prompt = PromptManager.get_communication_prompt(transcript_text)
    
    resp = await llm.ainvoke([
        SystemMessage(content="You are a rigorous communication and confidence assessor. Output valid JSON. Score strictly using the provided rubric. You MUST count filler words, hedging phrases, and assertive phrases explicitly."),
        HumanMessage(content=prompt)
    ])
    
    data = extract_json(resp.content)
    
    if data:
        # Log enhanced communication metrics
        filler_count = data.get('filler_word_count', 0)
        hedging_ratio = data.get('hedging_ratio', 'N/A')
        hedging_count = data.get('hedging_count', 0)
        assertive_count = data.get('assertive_count', 0)
        print(f"[EVAL COMM] Fillers: {filler_count}, Hedging: {hedging_count}, Assertive: {assertive_count}, Ratio: {hedging_ratio}")
        print(f"[EVAL COMM] Sub-scores → Clarity: {data.get('clarity_subscore', 'N/A')}, "
              f"Articulation: {data.get('articulation_subscore', 'N/A')}, "
              f"Structure: {data.get('structure_subscore', 'N/A')}")
    
    return {"communication_analysis": json.dumps(data) if data else resp.content}

async def analyze_cultural_fit_node(state: EvaluationState):
    llm = get_llm(temperature=0)
    transcript_text = "\n".join([f"{t['role']}: {t['text']}" for t in state['transcript']])
    
    job_description = state['assessment_details'].get('job_description', '')
    
    prompt = PromptManager.get_cultural_fit_prompt(transcript_text, job_description)
    
    resp = await llm.ainvoke([
        SystemMessage(content="You are a rigorous culture and behavioral assessor. Output valid JSON. Score conservatively using the behavioral rubric dimensions. Evaluate each of the 5 dimensions separately."),
        HumanMessage(content=prompt)
    ])
    
    data = extract_json(resp.content)
    
    if data:
        # Log behavioral rubric scores
        rubric = data.get('behavioral_rubric', {})
        for dimension, dim_data in rubric.items():
            if isinstance(dim_data, dict):
                print(f"[EVAL CULTURE] {dimension}: {dim_data.get('score', 'N/A')}/5")
        print(f"[EVAL CULTURE] Overall: {data.get('cultural_fit_score', 'N/A')}/5, "
              f"STAR stories: {data.get('star_stories_detected', 0)}")
    
    return {"cultural_analysis": json.dumps(data) if data else resp.content}


async def final_scoring_node(state: EvaluationState):
    raw_skill_graph = state['assessment_details'].get('skill_graph', {})
    passing_score = float(state['assessment_details'].get('passing_score', 60))

    parsed_skills = _parse_skill_graph(raw_skill_graph)
    skill_evaluations = state.get('skill_scores', {})

    print(f"[EVAL DEBUG] Parsed skills: {list(parsed_skills.keys())}")
    print(f"[EVAL DEBUG] LLM evaluated skills: {list(skill_evaluations.keys())}")

    # ── Multi-layer weighted technical scoring ──
    weighted_tech_score = 0.0
    evaluated_weight_sum = 0.0
    total_weight_sum = 0.0
    matched_skills = []
    unmatched_skills = []
    
    # Per-skill scores on 0-100 scale for admin display
    per_skill_scores = {}

    for skill_name, weight in parsed_skills.items():
        total_weight_sum += weight

        eval_data = _find_skill_score(skill_evaluations, skill_name)
        if eval_data and eval_data.get('score') is not None:
            try:
                # Use the composite score (Layer 3) which already factors in relevance & depth
                composite_score = float(eval_data['score'])
                composite_score = min(5.0, max(0.0, composite_score))
                
                # Also extract layer scores for detailed logging
                relevance = float(eval_data.get('relevance_score', composite_score))
                depth = float(eval_data.get('depth_score', composite_score))
                
                weighted_tech_score += composite_score * weight
                evaluated_weight_sum += weight
                
                # Convert to 0-100 scale for per-skill admin display
                skill_score_100 = round(composite_score * 20.0, 1)
                per_skill_scores[skill_name] = skill_score_100
                
                matched_skills.append(
                    f"{skill_name}: {composite_score}/5 "
                    f"(R={relevance:.1f}, D={depth:.1f}, w={weight})"
                )
            except (ValueError, TypeError):
                unmatched_skills.append(skill_name)
                per_skill_scores[skill_name] = 0.0
        else:
            unmatched_skills.append(skill_name)
            per_skill_scores[skill_name] = 0.0

    print(f"[EVAL DEBUG] Matched (multi-layer): {matched_skills}")
    print(f"[EVAL DEBUG] Unmatched/unevaluated: {unmatched_skills}")
    print(f"[EVAL DEBUG] Per-skill scores (0-100): {per_skill_scores}")

    if evaluated_weight_sum > 0:
        normalized_tech_score = weighted_tech_score / evaluated_weight_sum
    else:
        normalized_tech_score = 0.0

    coverage_ratio = evaluated_weight_sum / total_weight_sum if total_weight_sum > 0 else 0.0

    coverage_factor = 0.85 + (0.15 * coverage_ratio)
    final_technical_score = normalized_tech_score * coverage_factor
    final_technical_score = min(5.0, max(0.0, final_technical_score))

    print(f"[EVAL DEBUG] Normalized tech: {normalized_tech_score:.2f}, Coverage: {coverage_ratio:.2f}, Final tech: {final_technical_score:.2f}")

    # ── Enhanced Communication scoring with sub-scores ──
    comm_data = extract_json(state.get('communication_analysis') or "{}") or {}
    cult_data = extract_json(state.get('cultural_analysis') or "{}") or {}

    # Communication: use sub-scores for more accurate scoring
    try:
        # Try to use the enhanced sub-scores first
        clarity = float(comm_data.get('clarity_subscore', 0))
        articulation = float(comm_data.get('articulation_subscore', 0))
        structure = float(comm_data.get('structure_subscore', 0))
        
        # If sub-scores are available, calculate weighted communication score
        if clarity > 0 or articulation > 0 or structure > 0:
            comm_score = (clarity * 0.35) + (articulation * 0.35) + (structure * 0.30)
        else:
            comm_score = float(comm_data.get('communication_score', 0))
        
        comm_score = min(5.0, max(0.0, comm_score))
    except (ValueError, TypeError):
        comm_score = 0.0

    # Confidence: factor in hedging ratio for more accurate scoring
    try:
        conf_score = float(comm_data.get('confidence_score', 0))
        
        # Apply hedging ratio adjustment if available
        hedging_ratio = comm_data.get('hedging_ratio')
        if hedging_ratio is not None:
            try:
                hr = float(hedging_ratio)
                # If hedging ratio is very high but confidence score is also high, moderate it
                if hr > 0.6 and conf_score > 3.0:
                    conf_score = min(conf_score, 3.0)
                    print(f"[EVAL DEBUG] Confidence capped at 3.0 due to high hedging ratio: {hr:.2f}")
                elif hr < 0.2 and conf_score < 3.5:
                    # If very assertive but scored low, give a small boost
                    conf_score = max(conf_score, conf_score + 0.5)
                    print(f"[EVAL DEBUG] Confidence boosted by 0.5 due to low hedging ratio: {hr:.2f}")
            except (ValueError, TypeError):
                pass
        
        # Apply filler word penalty
        filler_count = comm_data.get('filler_word_count', 0)
        if isinstance(filler_count, (int, float)) and filler_count > 10:
            penalty = min(1.0, (filler_count - 10) * 0.1)
            comm_score = max(0.0, comm_score - penalty)
            print(f"[EVAL DEBUG] Communication penalized by {penalty:.1f} for {filler_count} filler words")
        
        conf_score = min(5.0, max(0.0, conf_score))
    except (ValueError, TypeError):
        conf_score = 0.0

    # ── Enhanced Cultural Fit scoring with behavioral rubric ──
    try:
        # Try to use behavioral rubric dimension scores
        rubric = cult_data.get('behavioral_rubric', {})
        if rubric and isinstance(rubric, dict):
            dimension_scores = []
            dimension_weights = {
                'ownership': 0.25,
                'collaboration': 0.25,
                'growth_mindset': 0.20,
                'innovation': 0.15,
                'integrity': 0.15
            }
            
            weighted_cult = 0.0
            total_cult_weight = 0.0
            
            for dim_name, dim_weight in dimension_weights.items():
                dim_data = rubric.get(dim_name, {})
                if isinstance(dim_data, dict) and dim_data.get('score') is not None:
                    try:
                        dim_score = float(dim_data['score'])
                        dim_score = min(5.0, max(0.0, dim_score))
                        weighted_cult += dim_score * dim_weight
                        total_cult_weight += dim_weight
                        dimension_scores.append(f"{dim_name}: {dim_score}/5")
                    except (ValueError, TypeError):
                        continue
            
            if total_cult_weight > 0:
                cult_score = weighted_cult / total_cult_weight
                print(f"[EVAL DEBUG] Cultural dimensions: {', '.join(dimension_scores)}")
            else:
                cult_score = float(cult_data.get('cultural_fit_score', 0))
        else:
            cult_score = float(cult_data.get('cultural_fit_score', 0))
        
        cult_score = min(5.0, max(0.0, cult_score))
    except (ValueError, TypeError):
        cult_score = 0.0

    # ── Final weighted total ──
    final_total_score = (
        (final_technical_score * 0.60) +
        (comm_score * 0.15) +
        (conf_score * 0.15) +
        (cult_score * 0.10)
    )
    final_total_score = min(5.0, max(0.0, final_total_score))
    
    total_score_100 = final_total_score * 20.0

    print(f"[EVAL DEBUG] Scores → Tech: {final_technical_score:.2f}, Comm: {comm_score:.2f}, Conf: {conf_score:.2f}, Cult: {cult_score:.2f}")
    print(f"[EVAL DEBUG] Total (0-5): {final_total_score:.2f}, Total (0-100): {total_score_100:.2f}")

    transcript_text = "\n".join(
        [f"{t.get('role','unknown')}: {t.get('text','')}" for t in state.get("transcript", [])]
    )

    llm = get_llm(temperature=0)

    prompt = PromptManager.get_final_synthesis_prompt(
        state.get('technical_analysis') or "None",
        state.get('communication_analysis') or "None",
        state.get('cultural_analysis') or "None",
        transcript_text,
        round(total_score_100, 1),
        round(coverage_ratio, 2),
        passing_score
    )

    resp = await llm.ainvoke([
        SystemMessage(content="You are a strict hiring decision maker. Your recommendation MUST align with the numeric score ranges provided. Output valid JSON only."),
        HumanMessage(content=prompt)
    ])

    data = extract_json(resp.content) or {}
    llm_recommendation = data.get("recommendation", "REJECT").upper()

    if total_score_100 < passing_score:
        final_recommendation = "REJECT"
        print(f"[EVAL DEBUG] REJECT: Score {total_score_100:.1f} < passing {passing_score}")
    elif coverage_ratio < 0.5:
        final_recommendation = "REJECT"
        print(f"[EVAL DEBUG] REJECT: Coverage {coverage_ratio:.2f} < 0.5")
    else:
        if total_score_100 < 55 and llm_recommendation != "REJECT":
            final_recommendation = "REJECT"
            print(f"[EVAL DEBUG] Overriding LLM {llm_recommendation} → REJECT (score {total_score_100:.1f} < 55)")
        elif total_score_100 < 80 and llm_recommendation == "STRONG_HIRE":
            final_recommendation = "HIRE"
            print(f"[EVAL DEBUG] Downgrading STRONG_HIRE → HIRE (score {total_score_100:.1f} < 80)")
        else:
            final_recommendation = llm_recommendation

    print(f"[EVAL DEBUG] Final recommendation: {final_recommendation}")

    # Build enhanced communication sub-scores for the response
    comm_sub_scores = {}
    if comm_data:
        comm_sub_scores = {
            "clarity": round(float(comm_data.get('clarity_subscore', comm_score)), 2),
            "articulation": round(float(comm_data.get('articulation_subscore', comm_score)), 2),
            "structure": round(float(comm_data.get('structure_subscore', comm_score)), 2),
            "filler_word_count": comm_data.get('filler_word_count', 0),
            "hedging_ratio": comm_data.get('hedging_ratio', None),
            "hedging_count": comm_data.get('hedging_count', 0),
            "assertive_count": comm_data.get('assertive_count', 0),
        }

    # Build behavioral rubric summary for the response
    behavioral_summary = {}
    if cult_data and 'behavioral_rubric' in cult_data:
        rubric = cult_data['behavioral_rubric']
        for dim_name in ['ownership', 'collaboration', 'growth_mindset', 'innovation', 'integrity']:
            dim_data = rubric.get(dim_name, {})
            if isinstance(dim_data, dict):
                behavioral_summary[dim_name] = round(float(dim_data.get('score', 0)), 2)

    return {
        "scores": {
            "technical": round(final_technical_score, 2),
            "communication": round(comm_score, 2),
            "confidence": round(conf_score, 2),
            "cultural_fit": round(cult_score, 2),
            "total": round(final_total_score, 2),
            "coverage_ratio": round(coverage_ratio, 2),
            "total_score_100": round(total_score_100, 2),
            "communication_sub_scores": comm_sub_scores,
            "behavioral_rubric": behavioral_summary,
        },
        "per_skill_scores": per_skill_scores,
        "summary": data.get("summary", ""),
        "explanation": data.get("explanation", ""),
        "recommendation": final_recommendation,
        "tie_breaker_subscore": round(total_score_100 / 10, 2)
    }

workflow = StateGraph(EvaluationState)

workflow.add_node("analyze_technical", analyze_technical_node)
workflow.add_node("analyze_communication", analyze_communication_node)
workflow.add_node("analyze_cultural", analyze_cultural_fit_node)
workflow.add_node("final_scoring", final_scoring_node)

workflow.set_entry_point("analyze_technical")
workflow.add_edge("analyze_technical", "analyze_communication")
workflow.add_edge("analyze_communication", "analyze_cultural")
workflow.add_edge("analyze_cultural", "final_scoring")
workflow.add_edge("final_scoring", END)

evaluation_app = workflow.compile()

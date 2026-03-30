"""Node for calculating the final numeric scores and hiring recommendation."""

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..state import EvaluationState
from ..utils.json_utils import extract_json
from ..utils.skill_utils import find_skill_score, parse_skill_graph


def _calculate_technical_scores(parsed_skills: dict[str, float], skill_evaluations: dict[str, Any]) -> tuple[float, float, list[str], list[str], dict[str, float]]:
    weighted_tech_score = 0.0
    evaluated_weight_sum = 0.0
    total_weight_sum = 0.0
    matched_skills = []
    unmatched_skills = []
    per_skill_scores = {}

    for skill_name, weight in parsed_skills.items():
        total_weight_sum += weight

        eval_data = find_skill_score(skill_evaluations, skill_name)
        if eval_data and eval_data.get('score') is not None:
            try:
                composite_score = float(eval_data['score'])
                composite_score = min(5.0, max(0.0, composite_score))

                relevance = float(eval_data.get('relevance_score', composite_score))
                depth = float(eval_data.get('depth_score', composite_score))

                weighted_tech_score += composite_score * weight
                evaluated_weight_sum += weight

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

    normalized_tech_score = weighted_tech_score / evaluated_weight_sum if evaluated_weight_sum > 0 else 0.0
    coverage_ratio = evaluated_weight_sum / total_weight_sum if total_weight_sum > 0 else 0.0

    coverage_factor = 0.85 + (0.15 * coverage_ratio)
    final_technical_score = normalized_tech_score * coverage_factor
    final_technical_score = min(5.0, max(0.0, final_technical_score))
    
    return final_technical_score, coverage_ratio, matched_skills, unmatched_skills, per_skill_scores


def _calculate_communication_scores(comm_data: dict[str, Any]) -> tuple[float, float]:
    try:
        clarity = float(comm_data.get('clarity_subscore', 0))
        articulation = float(comm_data.get('articulation_subscore', 0))
        structure = float(comm_data.get('structure_subscore', 0))

        if clarity > 0 or articulation > 0 or structure > 0:
            comm_score = (clarity * 0.35) + (articulation * 0.35) + (structure * 0.30)
        else:
            comm_score = float(comm_data.get('communication_score', 0))
        comm_score = min(5.0, max(0.0, comm_score))
    except (ValueError, TypeError):
        comm_score = 0.0

    try:
        conf_score = float(comm_data.get('confidence_score', 0))
        hedging_ratio = comm_data.get('hedging_ratio')
        if hedging_ratio is not None:
            try:
                hr = float(hedging_ratio)
                if hr > 0.6 and conf_score > 3.0:
                    conf_score = min(conf_score, 3.0)
                elif hr < 0.2 and conf_score < 3.5:
                    conf_score = max(conf_score, conf_score + 0.5)
            except (ValueError, TypeError):
                pass

        filler_count = comm_data.get('filler_word_count', 0)
        if isinstance(filler_count, (int, float)) and filler_count > 10:
            penalty = min(1.0, (filler_count - 10) * 0.1)
            comm_score = max(0.0, comm_score - penalty)

        conf_score = min(5.0, max(0.0, conf_score))
    except (ValueError, TypeError):
        conf_score = 0.0
        
    return comm_score, conf_score


def _calculate_cultural_score(cult_data: dict[str, Any]) -> float:
    try:
        rubric = cult_data.get('behavioral_rubric', {})
        if rubric and isinstance(rubric, dict):
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
                        dim_score = min(5.0, max(0.0, float(dim_data['score'])))
                        weighted_cult += dim_score * dim_weight
                        total_cult_weight += dim_weight
                    except (ValueError, TypeError):
                        continue

            if total_cult_weight > 0:
                cult_score = weighted_cult / total_cult_weight
            else:
                cult_score = float(cult_data.get('cultural_fit_score', 0))
        else:
            cult_score = float(cult_data.get('cultural_fit_score', 0))

        return min(5.0, max(0.0, cult_score))
    except (ValueError, TypeError):
        return 0.0


async def final_scoring_node(state: EvaluationState) -> dict[str, Any]:
    """Calculate the final scores and recommendation for the candidate."""
    raw_skill_graph = state['assessment_details'].get('skill_graph', {})
    passing_val = state['assessment_details'].get('passing_score', 60)
    passing_score = float(passing_val) if isinstance(passing_val, (int, float, str)) else 60.0

    parsed_skills = parse_skill_graph(raw_skill_graph)
    skill_evaluations = state.get('skill_scores', {})

    tech_data = extract_json(state.get('technical_analysis') or '{}') or {}
    interview_validity = tech_data.get('interview_validity', 'VALID')
    is_invalid_interview = (interview_validity == 'INVALID_INTERVIEW')

    final_technical_score, coverage_ratio, _, _, per_skill_scores = _calculate_technical_scores(parsed_skills, skill_evaluations)

    comm_data = extract_json(state.get('communication_analysis') or "{}") or {}
    cult_data = extract_json(state.get('cultural_analysis') or "{}") or {}

    comm_score, conf_score = _calculate_communication_scores(comm_data)
    cult_score = _calculate_cultural_score(cult_data)

    final_total_score = min(5.0, max(0.0, (final_technical_score * 0.60) + (comm_score * 0.15) + (conf_score * 0.15) + (cult_score * 0.10)))
    total_score_100 = final_total_score * 20.0

    transcript_text = "\n".join([f"{t.get('role','unknown')}: {t.get('text','')}" for t in state.get("transcript", [])])
    llm = get_llm(temperature=0)

    synthesis_total = 0.0 if is_invalid_interview else round(total_score_100, 1)
    synthesis_coverage = 0.0 if is_invalid_interview else round(coverage_ratio, 2)

    prompt = PromptManager.get_final_synthesis_prompt(
        str(state.get('technical_analysis') or "None"),
        str(state.get('communication_analysis') or "None"),
        str(state.get('cultural_analysis') or "None"),
        str(transcript_text),
        float(synthesis_total),
        float(synthesis_coverage),
        float(passing_score)
    )

    resp = await llm.ainvoke([
        SystemMessage(content="You are a strict hiring decision maker. Your recommendation MUST align with the numeric score ranges provided. Output valid JSON only."),
        HumanMessage(content=str(prompt))
    ])

    data = extract_json(str(resp.content)) or {}
    llm_recommendation = data.get("recommendation", "REJECT").upper()

    if is_invalid_interview:
        final_recommendation, final_technical_score, comm_score, conf_score, cult_score = "REJECT", 0.0, 0.0, 0.0, 0.0
        final_total_score, total_score_100, coverage_ratio = 0.0, 0.0, 0.0
        per_skill_scores = dict.fromkeys(per_skill_scores, 0.0)
    elif total_score_100 < passing_score or coverage_ratio < 0.5:
        final_recommendation = "REJECT"
    else:
        if total_score_100 < 55 and llm_recommendation != "REJECT":
            final_recommendation = "REJECT"
        elif total_score_100 < 80 and llm_recommendation == "STRONG_HIRE":
            final_recommendation = "HIRE"
        else:
            final_recommendation = llm_recommendation

    comm_sub_scores = {"clarity": round(float(comm_data.get('clarity_subscore', comm_score)), 2), "articulation": round(float(comm_data.get('articulation_subscore', comm_score)), 2), "structure": round(float(comm_data.get('structure_subscore', comm_score)), 2), "filler_word_count": comm_data.get('filler_word_count', 0), "hedging_ratio": comm_data.get('hedging_ratio', None), "hedging_count": comm_data.get('hedging_count', 0), "assertive_count": comm_data.get('assertive_count', 0)} if comm_data else {}
    behavioral_summary = {dim: round(float(cult_data.get('behavioral_rubric', {}).get(dim, {}).get('score', 0)), 2) for dim in ['ownership', 'collaboration', 'growth_mindset', 'innovation', 'integrity'] if isinstance(cult_data.get('behavioral_rubric', {}).get(dim), dict)} if cult_data and 'behavioral_rubric' in cult_data else {}

    return {
        "scores": {
            "technical": round(final_technical_score, 2), "communication": round(comm_score, 2), "confidence": round(conf_score, 2), "cultural_fit": round(cult_score, 2),
            "total": round(final_total_score, 2), "coverage_ratio": round(coverage_ratio, 2), "total_score_100": round(total_score_100, 2),
            "communication_sub_scores": comm_sub_scores, "behavioral_rubric": behavioral_summary
        },
        "per_skill_scores": per_skill_scores,
        "summary": data.get("summary", ""),
        "explanation": data.get("explanation", ""),
        "recommendation": final_recommendation,
        "tie_breaker_subscore": round(total_score_100 / 10, 2)
    }

import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..state import EvaluationState
from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..utils.json_utils import extract_json
from ..utils.skill_utils import parse_skill_graph, find_skill_score


async def final_scoring_node(state: EvaluationState):
    raw_skill_graph = state['assessment_details'].get('skill_graph', {})
    passing_score = float(state['assessment_details'].get('passing_score', 60))

    parsed_skills = parse_skill_graph(raw_skill_graph)
    skill_evaluations = state.get('skill_scores', {})

    tech_data = extract_json(state.get('technical_analysis') or '{}') or {}
    interview_validity = tech_data.get('interview_validity', 'VALID')
    is_invalid_interview = (interview_validity == 'INVALID_INTERVIEW')

    
    if is_invalid_interview:
        print(f"[EVAL DEBUG] INVALID INTERVIEW — zeroing all scores")

    print(f"[EVAL DEBUG] Parsed skills: {list(parsed_skills.keys())}")
    print(f"[EVAL DEBUG] LLM evaluated skills: {list(skill_evaluations.keys())}")

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

    comm_data = extract_json(state.get('communication_analysis') or "{}") or {}
    cult_data = extract_json(state.get('cultural_analysis') or "{}") or {}

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
                    print(f"[EVAL DEBUG] Confidence capped at 3.0 due to high hedging ratio: {hr:.2f}")
                elif hr < 0.2 and conf_score < 3.5:
                    conf_score = max(conf_score, conf_score + 0.5)
                    print(f"[EVAL DEBUG] Confidence boosted by 0.5 due to low hedging ratio: {hr:.2f}")
            except (ValueError, TypeError):
                pass
        
        filler_count = comm_data.get('filler_word_count', 0)
        if isinstance(filler_count, (int, float)) and filler_count > 10:
            penalty = min(1.0, (filler_count - 10) * 0.1)
            comm_score = max(0.0, comm_score - penalty)
            print(f"[EVAL DEBUG] Communication penalized by {penalty:.1f} for {filler_count} filler words")
        
        conf_score = min(5.0, max(0.0, conf_score))
    except (ValueError, TypeError):
        conf_score = 0.0

    try:
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

    synthesis_total = 0.0 if is_invalid_interview else round(total_score_100, 1)
    synthesis_coverage = 0.0 if is_invalid_interview else round(coverage_ratio, 2)

    prompt = PromptManager.get_final_synthesis_prompt(
        state.get('technical_analysis') or "None",
        state.get('communication_analysis') or "None",
        state.get('cultural_analysis') or "None",
        transcript_text,
        synthesis_total,
        synthesis_coverage,
        passing_score
    )

    resp = await llm.ainvoke([
        SystemMessage(content="You are a strict hiring decision maker. Your recommendation MUST align with the numeric score ranges provided. Output valid JSON only."),
        HumanMessage(content=prompt)
    ])

    data = extract_json(resp.content) or {}
    llm_recommendation = data.get("recommendation", "REJECT").upper()

    if is_invalid_interview:
        final_recommendation = "REJECT"
        print(f"[EVAL DEBUG] REJECT: Invalid interview — candidate did not participate")
        final_technical_score = 0.0
        comm_score = 0.0
        conf_score = 0.0
        cult_score = 0.0
        final_total_score = 0.0
        total_score_100 = 0.0
        coverage_ratio = 0.0
        per_skill_scores = {skill: 0.0 for skill in per_skill_scores}
    elif total_score_100 < passing_score:
        final_recommendation = "REJECT"
        print(f"[EVAL DEBUG] REJECT: Score {total_score_100:.1f} < passing {passing_score}")
    elif coverage_ratio < 0.5:
        final_recommendation = "REJECT"
        print(f"[EVAL DEBUG] REJECT: Coverage {coverage_ratio:.2f} < 0.5 — keeping real scores for transparency")
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
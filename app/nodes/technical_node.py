import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..state import EvaluationState
from ..utils.json_utils import extract_json


async def analyze_technical_node(state: EvaluationState) -> dict[str, Any]:  
    """Node responsible for analyzing the technical performance of the candidate based on the interview transcript and the skill graph extracted from the job description."""
    llm = get_llm(temperature=0)
    transcript_text = "\n".join([f"{t['role']}: {t['text']}" for t in state['transcript']])

    raw_skill_graph = state['assessment_details'].get('skill_graph', {})

    prompt = PromptManager.get_technical_prompt(transcript_text, str(raw_skill_graph))

    resp = await llm.ainvoke([
        SystemMessage(content="You are a rigorous technical evaluator. You MUST output valid JSON. Score strictly using the provided multi-layer rubric. Do not inflate scores. Apply all three evaluation layers for each skill."),
        HumanMessage(content=prompt)
    ])

    data = extract_json(str(resp.content))
    if data and "skill_evaluations" in data:
        data.get('interview_validity', 'VALID')


        for _skill_name, skill_data in data["skill_evaluations"].items():
            skill_data.get('relevance_score', 'N/A')
            skill_data.get('depth_score', 'N/A')
            skill_data.get('score', 'N/A')

        return {
            "technical_analysis": json.dumps(data) if isinstance(data, dict) else str(data),
            "skill_scores": data["skill_evaluations"]
        }
    return {"technical_analysis": str(resp.content), "skill_scores": {}}

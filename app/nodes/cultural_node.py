"""Node for evaluating candidate cultural and behavioral fit."""
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..state import EvaluationState
from ..utils.json_utils import extract_json


async def analyze_cultural_fit_node(state: EvaluationState) -> dict[str, Any]:  
    """Node responsible for analyzing the cultural fit and behavioral aspects of the candidate based on the interview transcript and job description."""
    llm = get_llm(temperature=0)
    transcript_text = "\n".join([f"{t['role']}: {t['text']}" for t in state['transcript']])

    job_description = state['assessment_details'].get('job_description', '')

    prompt = PromptManager.get_cultural_fit_prompt(transcript_text, str(job_description))

    resp = await llm.ainvoke([
        SystemMessage(content="You are a rigorous culture and behavioral assessor. Output valid JSON. Score conservatively using the behavioral rubric dimensions. Evaluate each of the 5 dimensions separately."),
        HumanMessage(content=prompt)
    ])

    data = extract_json(str(resp.content))
    if data:
        rubric = data.get('behavioral_rubric', {})
        for _dimension, dim_data in rubric.items():
            if isinstance(dim_data, dict):
                pass

    return {"cultural_analysis": json.dumps(data) if data else str(resp.content)}

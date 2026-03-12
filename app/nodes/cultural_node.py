import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..state import EvaluationState
from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..utils.json_utils import extract_json


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
        rubric = data.get('behavioral_rubric', {})
        for dimension, dim_data in rubric.items():
            if isinstance(dim_data, dict):
                print(f"[EVAL CULTURE] {dimension}: {dim_data.get('score', 'N/A')}/5")
        print(f"[EVAL CULTURE] Overall: {data.get('cultural_fit_score', 'N/A')}/5, "
              f"STAR stories: {data.get('star_stories_detected', 0)}")
    
    return {"cultural_analysis": json.dumps(data) if data else resp.content}
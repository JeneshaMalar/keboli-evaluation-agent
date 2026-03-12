import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..state import EvaluationState
from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..utils.json_utils import extract_json


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
        interview_validity = data.get('interview_validity', 'VALID')
        if interview_validity == 'INVALID_INTERVIEW':
            print(f"[EVAL TECH] INVALID INTERVIEW DETECTED — valid_response_count: {data.get('valid_response_count', 0)}")
        
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
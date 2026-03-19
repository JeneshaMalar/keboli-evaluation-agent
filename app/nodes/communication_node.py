import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..state import EvaluationState
from ..llm import get_llm
from ..prompt_manager import PromptManager
from ..utils.json_utils import extract_json


async def analyze_communication_node(state: EvaluationState):
    """Node responsible for analyzing the communication and confidence of the candidate based on the interview transcript."""
    llm = get_llm(temperature=0)
    transcript_text = "\n".join([f"{t['role']}: {t['text']}" for t in state['transcript']])
    
    prompt = PromptManager.get_communication_prompt(transcript_text)
    
    resp = await llm.ainvoke([
        SystemMessage(content="You are a rigorous communication and confidence assessor. Output valid JSON. Score strictly using the provided rubric. You MUST count filler words, hedging phrases, and assertive phrases explicitly."),
        HumanMessage(content=prompt)
    ])
    
    data = extract_json(resp.content)
    
    if data:
        filler_count = data.get('filler_word_count', 0)
        hedging_ratio = data.get('hedging_ratio', 'N/A')
        hedging_count = data.get('hedging_count', 0)
        assertive_count = data.get('assertive_count', 0)
    
    return {"communication_analysis": json.dumps(data) if data else resp.content}
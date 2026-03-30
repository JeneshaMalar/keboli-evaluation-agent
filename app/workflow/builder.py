"""LangGraph workflow builder for the evaluation agent."""
from langgraph.graph import END, StateGraph

from ..nodes import (
    analyze_communication_node,
    analyze_cultural_fit_node,
    analyze_technical_node,
    final_scoring_node,
)
from ..state import EvaluationState


def build_evaluation_workflow() -> StateGraph:  
    """Build and compile the evaluation workflow."""
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

    return workflow.compile() 

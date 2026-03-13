from fastapi import FastAPI, HTTPException
from .keboli_client import keboli_client
from .graph import evaluation_app
from .state import EvaluationState
from .observability import langfuse_handler

app = FastAPI(title="Keboli Evaluation Agent", version="1.0.0")

@app.post("/api/v1/evaluate/{session_id}")
async def evaluate_candidate(session_id: str):
    try:
        await keboli_client.post_log({
            "level": "INFO",
            "service": "evaluation_agent",
            "component": "evaluation",
            "event_type": "evaluation_started",
            "session_id": session_id,
            "message": f"Starting evaluation for session {session_id}"
        })
        
        transcript_data = await keboli_client.get_transcript(session_id)
        session_details = await keboli_client.get_session_details(session_id)
        
        initial_state: EvaluationState = {
            "session_id": session_id,
            "transcript": transcript_data,
            "assessment_details": session_details,
            "technical_analysis": None,
            "communication_analysis": None,
            "cultural_analysis": None,
            "skill_scores": {},
            "per_skill_scores": {},
            "scores": {},
            "summary": None,
            "explanation": None,
            "recommendation": None,
            "tie_breaker_subscore": 0.0,
            "error": None
        }
        
        config = {"run_name": f"evaluation-{session_id}"}
        if langfuse_handler:
            config["callbacks"] = [langfuse_handler]

        result = await evaluation_app.ainvoke(initial_state, config=config)
        
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
            
       
        recommendation = result.get("recommendation", "REJECT").lower()
        
        scale = 20.0
        
        per_skill_scores = result.get("per_skill_scores", {})
        
        scores = result.get("scores", {})
        comm_sub_scores = scores.get("communication_sub_scores", {})
        behavioral_rubric = scores.get("behavioral_rubric", {})
        
        evaluation_payload = {
            "technical_score": float(scores.get("technical", 0)) * scale,
            "communication_score": float(scores.get("communication", 0)) * scale,
            "confidence_score": float(scores.get("confidence", 0)) * scale,
            "cultural_alignment_score": float(scores.get("cultural_fit", 0)) * scale,
            "total_score": float(scores.get("total", 0)) * scale,
            "score_breakdown": {
                "technical": scores.get("technical", 0),
                "communication": scores.get("communication", 0),
                "confidence": scores.get("confidence", 0),
                "cultural_fit": scores.get("cultural_fit", 0),
                "tie_breaker": float(result.get("tie_breaker_subscore", 0.0)),
                "skill_evaluations": result.get("skill_scores", {}),
                "per_skill_scores": per_skill_scores,
                "communication_details": comm_sub_scores,
                "behavioral_rubric": behavioral_rubric,
            },
            "ai_summary": result["summary"],
            "ai_explanation": result["explanation"],
            "hiring_recommendation": recommendation,
            "admin_recommendation": None,
            "admin_notes": None,
            "is_tie_winner": False,
            "detailed_analysis": {
                "skill_scores": result.get("skill_scores", {}),
                "per_skill_scores": per_skill_scores,
                "technical_analysis": result.get("technical_analysis"),
                "communication_analysis": result.get("communication_analysis"),
                "cultural_analysis": result.get("cultural_analysis")
            }
        }
        
        print(f"Pushing evaluation for session {session_id}: {recommendation}")
        print(f"Per-skill scores: {per_skill_scores}")
        
        await keboli_client.post_log({
            "level": "INFO",
            "service": "evaluation_agent",
            "component": "evaluation",
            "event_type": "evaluation_completed",
            "session_id": session_id,
            "message": f"Completed evaluation for session {session_id}",
            "details": {
                "recommendation": recommendation, 
                "total_score": float(scores.get("total", 0)) * scale
            }
        })
        try:
            resp = await keboli_client.post_evaluation(session_id, evaluation_payload)
            print("Successfully posted evaluation to backend.")
            return {"status": "success", "session_id": session_id, "recommendation": recommendation}
        except Exception as api_err:
            print(f"Failed to post evaluation: {api_err}")
            if hasattr(api_err, 'response') and api_err.response:
                print(f"Backend response: {api_err.response.text}")
            raise api_err
        
    except Exception as e:
        await keboli_client.post_log({
            "level": "ERROR",
            "service": "evaluation_agent",
            "component": "evaluation",
            "event_type": "evaluation_failed",
            "session_id": session_id,
            "message": f"Evaluation failed for session {session_id}: {str(e)}",
            "error_stack": str(e)
        })
        print(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

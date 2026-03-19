from fastapi import FastAPI, HTTPException
from .keboli_client import keboli_client
from .graph import evaluation_app
from .state import EvaluationState
from .observability import langfuse_handler
from datetime import datetime, timezone   
from fastapi.responses import JSONResponse  
from fastapi import status                
from sqlalchemy import text     
import httpx          
app = FastAPI(title="Keboli Evaluation Agent", version="1.0.0")
@app.get("/health")
async def health_check():
    """
    Check application health status by verifying connectivity to the 
    Keboli Main Backend and the readiness of the Evaluation Graph.
    """
    services_health = {
        "keboli_backend_connectivity": "down",
        "evaluation_graph": "down"
    }
    
    try:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{keboli_client.base_url}/health", 
                    timeout=2.0
                )
                if response.status_code == 200:
                    services_health["keboli_backend_connectivity"] = "ok"
                else:
                    services_health["keboli_backend_connectivity"] = f"unhealthy_status_{response.status_code}"
        except Exception as e:
            services_health["keboli_backend_connectivity"] = f"connection_failed: {str(e)}"

        if evaluation_app is not None:
            services_health["evaluation_graph"] = "ok"

        is_healthy = all(v == "ok" for v in services_health.values())
        
        health_payload = {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": services_health
        }

        return JSONResponse(
            status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_payload
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error", 
                "error": str(e), 
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@app.post("/api/v1/evaluate/{session_id}")
async def evaluate_candidate(session_id: str):
    """
    Start an automated evaluation of a candidate based on their interview session.
  
    This endpoint fetches the interview transcript, runs it through a 
    multi-step LangGraph analysis (technical, communication, and cultural), 
    calculates normalized scores, and persists the results to the backend.

    Args:
        session_id: The unique identifier for the interview session to be evaluated.
  
    Raises:
        HTTPException (500): If the LangGraph analysis fails or if there is an 
                             error communicating with the Keboli backend.
  
    Returns:
        A dictionary containing the status, session_id, and final hiring recommendation.
    """

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
            return {"status": "success", "session_id": session_id, "recommendation": recommendation}
        except Exception as api_err:
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
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

"""Keboli Evaluation Agent — Application entrypoint.

Provides the FastAPI server for triggering automated candidate
evaluations via the LangGraph workflow.
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

from .exceptions import AppError, EvaluationError, ExternalServiceError
from .graph import evaluation_app
from .keboli_client import keboli_client
from .observability import langfuse_handler
from .state import EvaluationState

logger = logging.getLogger("keboli-eval")

app = FastAPI(
    title="Keboli Evaluation Agent",
    description="Automated interview evaluation service using LangGraph.",
    version="1.0.0",
)




@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError exceptions into structured JSON error responses.

    Args:
        request: The incoming HTTP request.
        exc: The AppError instance containing error details.

    Returns:
        A JSONResponse with the appropriate status code and error body.
    """
    logger.error(
        "app_error: %s (code=%s, status=%d)",
        exc.message,
        exc.error_code,
        exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )




class ServiceStatus(BaseModel):
    """Status of individual backing services."""

    keboli_backend_connectivity: str = "unknown"
    evaluation_graph: str = "unknown"


class HealthResponse(BaseModel):
    """Structured health-check response."""

    status: str = "ok"
    timestamp: str = ""
    services: ServiceStatus = ServiceStatus()
    error: str | None = None


class EvaluationResponse(BaseModel):
    """Response returned after a successful evaluation."""

    status: str
    session_id: str
    recommendation: str




@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check",
    description="Verify connectivity to the Keboli backend and readiness of the evaluation graph.",
)
async def health_check() -> JSONResponse:
    """Check application health by verifying backend connectivity and graph readiness.

    Returns:
        JSONResponse with service statuses and overall health.
    """
    services = ServiceStatus()

    try:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{keboli_client.base_url}/health",
                    timeout=2.0,
                )
                if response.status_code == 200:
                    services.keboli_backend_connectivity = "ok"
                else:
                    services.keboli_backend_connectivity = (
                        f"unhealthy_status_{response.status_code}"
                    )
        except Exception as e:
            services.keboli_backend_connectivity = f"connection_failed: {e!s}"

        if evaluation_app is not None:
            services.evaluation_graph = "ok"

        is_healthy = (
            services.keboli_backend_connectivity == "ok"
            and services.evaluation_graph == "ok"
        )

        payload = HealthResponse(
            status="healthy" if is_healthy else "unhealthy",
            timestamp=datetime.now(timezone.utc).isoformat(),
            services=services,
        )

        return JSONResponse(
            status_code=200 if is_healthy else 503,
            content=payload.model_dump(),
        )

    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@app.post(
    "/api/v1/evaluate/{session_id}",
    response_model=EvaluationResponse,
    summary="Evaluate a candidate interview",
    description="Fetch the interview transcript, run multi-step LangGraph analysis, and persist results.",
)
async def evaluate_candidate(session_id: str) -> EvaluationResponse:
    """Start an automated evaluation of a candidate based on their interview session.

    This endpoint fetches the interview transcript, runs it through a
    multi-step LangGraph analysis (technical, communication, and cultural),
    calculates normalized scores, and persists the results to the backend.

    Args:
        session_id: The unique identifier for the interview session to be evaluated.

    Returns:
        EvaluationResponse with status, session_id, and hiring recommendation.

    Raises:
        EvaluationError: If the LangGraph analysis fails.
        ExternalServiceError: If there is an error communicating with the backend.
    """
    try:
        await keboli_client.post_log(
            {
                "level": "INFO",
                "service": "evaluation_agent",
                "component": "evaluation",
                "event_type": "evaluation_started",
                "session_id": session_id,
                "message": f"Starting evaluation for session {session_id}",
            }
        )

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
            "error": None,
        }

        config: dict[str, object] = {"run_name": f"evaluation-{session_id}"}
        if langfuse_handler:
            config["callbacks"] = [langfuse_handler]

        result: dict[str, Any] = await evaluation_app.ainvoke(initial_state, config=config)  

        if result.get("error"):
            raise EvaluationError(
                session_id=session_id,
                message=str(result["error"]),
            )

        recommendation = result.get("recommendation", "REJECT").lower()

        scale = 20.0

        per_skill_scores: dict[str, float] = result.get("per_skill_scores", {})

        scores: dict[str, float] = result.get("scores", {})
        comm_sub_scores: dict[str, Any] = scores.get("communication_sub_scores", {})  
        behavioral_rubric: dict[str, Any] = scores.get("behavioral_rubric", {})  

        evaluation_payload: dict[str, object] = {
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
                "cultural_analysis": result.get("cultural_analysis"),
            },
        }

        await keboli_client.post_log(
            {
                "level": "INFO",
                "service": "evaluation_agent",
                "component": "evaluation",
                "event_type": "evaluation_completed",
                "session_id": session_id,
                "message": f"Completed evaluation for session {session_id}",
                "details": {
                    "recommendation": recommendation,
                    "total_score": float(scores.get("total", 0)) * scale,
                },
            }
        )

        try:
            await keboli_client.post_evaluation(session_id, evaluation_payload)
            return EvaluationResponse(
                status="success",
                session_id=session_id,
                recommendation=recommendation,
            )
        except Exception as api_err:
            if hasattr(api_err, "response") and api_err.response:
                logger.error("Backend response: %s", api_err.response.text)
            raise ExternalServiceError(
                service_name="keboli-backend",
                message=f"Failed to post evaluation: {api_err!s}",
            ) from api_err

    except AppError:
        raise
    except Exception as e:
        await keboli_client.post_log(
            {
                "level": "ERROR",
                "service": "evaluation_agent",
                "component": "evaluation",
                "event_type": "evaluation_failed",
                "session_id": session_id,
                "message": f"Evaluation failed for session {session_id}: {e!s}",
                "error_stack": str(e),
            }
        )
        raise EvaluationError(
            session_id=session_id, message=str(e)
        ) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)

"""HTTP client for communicating with the Keboli Main Backend API."""

import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("keboli-eval-client")


class KeboliClient:
    """Client for interacting with the Keboli backend API.

    Provides methods to fetch transcripts, session details, post evaluations,
    and send structured logs. All methods are asynchronous.
    """

    def __init__(self) -> None:
        self.base_url = settings.MAIN_BACKEND_URL

    async def get_transcript(self, session_id: str) -> list[dict[str, str]]:
        """Fetch the interview transcript for a given session ID from the backend.

        Args:
            session_id: The unique identifier for the interview session.

        Returns:
            A list of transcript entries (role + content dicts).

        Raises:
            httpx.HTTPStatusError: If the backend returns a non-2xx response.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/livekit/transcript/{session_id}"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("full_transcript", [])

    async def get_session_details(self, session_id: str) -> dict[str, Any]:
        """Fetch the session details for a given session ID from the backend.

        Args:
            session_id: The unique identifier for the interview session.

        Returns:
            A dictionary containing session and assessment metadata.

        Raises:
            httpx.HTTPStatusError: If the backend returns a non-2xx response.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/livekit/session/{session_id}"
            )
            response.raise_for_status()
            return response.json()  

    async def post_evaluation(
        self, session_id: str, evaluation_data: dict[str, object]
    ) -> dict[str, Any]:
        """Post the evaluation results for a given session ID to the backend.

        Args:
            session_id: The unique identifier for the interview session.
            evaluation_data: Structured evaluation scores and analysis.

        Returns:
            The backend's response confirming the evaluation was stored.

        Raises:
            httpx.HTTPStatusError: If the backend returns a non-2xx response.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/evaluation/{session_id}",
                json=evaluation_data,
            )
            response.raise_for_status()
            return response.json()  

    async def post_log(self, log_data: dict[str, object]) -> dict[str, Any] | None:
        """Post a log entry to the backend logging endpoint.

        This method is fire-and-forget; exceptions are caught and logged
        without propagating to the caller.

        Args:
            log_data: Structured log entry matching the backend's LogCreate schema.

        Returns:
            The backend's response on success, or None on failure.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/logs/",
                    json=log_data,
                )
                response.raise_for_status()
                return response.json()  
            except httpx.HTTPStatusError as e:
                response_text = ""
                try:
                    response_text = e.response.text
                except Exception:
                    pass
                logger.error("Failed to post log to backend (Status %d): %s", e.response.status_code, response_text)
                return None
            except httpx.HTTPError as e:
                logger.exception("Failed to post log to backend: %s", e)
                return None


keboli_client = KeboliClient()

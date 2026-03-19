import httpx
from .config import settings

class KeboliClient:
    """Client for interacting with the Keboli backend API. 
    Provides methods to fetch assessment details, update skill graphs, append interview transcripts, and post logs. 
    All methods are asynchronous and handle HTTP errors gracefully."""
    def __init__(self):
        self.base_url = settings.MAIN_BACKEND_URL

    async def get_transcript(self, session_id: str):
        """Fetch the interview transcript for a given session ID from the backend."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/evaluation/transcript/{session_id}")
            response.raise_for_status()
            return response.json()

    async def get_session_details(self, session_id: str):
        """Fetch the session details for a given session ID from the backend."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/evaluation/session/{session_id}")
            response.raise_for_status()
            return response.json()

    async def post_evaluation(self, session_id: str, evaluation_data: dict):
        """Post the evaluation results for a given session ID to the backend."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/evaluation/report/{session_id}",
                json=evaluation_data
            )
            response.raise_for_status()
            return response.json()

    async def post_log(self, log_data: dict):
        """Post a log entry to the backend logging endpoint. 
        This method is designed to be fire-and-forget, and any exceptions are caught and logged without raising to the caller."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/logs/",
                    json=log_data
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return None

keboli_client = KeboliClient()

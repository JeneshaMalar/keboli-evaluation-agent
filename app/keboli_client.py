import httpx
from .config import settings

class KeboliClient:
    def __init__(self):
        self.base_url = settings.MAIN_BACKEND_URL

    async def get_transcript(self, session_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/evaluation/transcript/{session_id}")
            response.raise_for_status()
            return response.json()

    async def get_session_details(self, session_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/evaluation/session/{session_id}")
            response.raise_for_status()
            return response.json()

    async def post_evaluation(self, session_id: str, evaluation_data: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/evaluation/report/{session_id}",
                json=evaluation_data
            )
            response.raise_for_status()
            return response.json()

keboli_client = KeboliClient()

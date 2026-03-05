from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    MAIN_BACKEND_URL: str = "http://localhost:8000/api"
    
    GROQ_API_KEY: Optional[str] = None
    MODEL_NAME: str = "llama-3.3-70b-versatile"
    
    EVALUATION_AGENT_SECRET: Optional[str] = "REPLACE_THIS_SECRET_IN_PROD"

    model_config = SettingsConfigDict(env_file="app/.env", extra="ignore")

settings = Settings()

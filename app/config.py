"""Application settings loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Keboli Evaluation Agent.

    All values are loaded from environment variables or a `.env` file.
    """

    MAIN_BACKEND_URL: str

    GROQ_API_KEY: str | None = None
    MODEL_NAME: str = "llama-3.3-70b-versatile"

    EVALUATION_AGENT_SECRET: str | None = None

    model_config = SettingsConfigDict(env_file="app/.env", extra="forbid")


settings = Settings()

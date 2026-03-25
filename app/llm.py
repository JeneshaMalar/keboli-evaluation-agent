"""LLM factory for the evaluation agent."""

from langchain_groq import ChatGroq

from .config import settings


def get_llm(temperature: float = 0) -> ChatGroq:
    """Create a ChatGroq LLM instance using the configured API key and model.

    Args:
        temperature: Sampling temperature for the LLM (0 = deterministic).

    Returns:
        A configured ChatGroq instance.

    Raises:
        ValueError: If GROQ_API_KEY is not set.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY must be set in .env or environment")

    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY, 
        model_name=settings.MODEL_NAME,
        temperature=temperature,
    )

from langchain_groq import ChatGroq
from .config import settings

def get_llm(temperature: float = 0):
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY must be set in .env or environment")
        
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=settings.MODEL_NAME,
        temperature=temperature
    )

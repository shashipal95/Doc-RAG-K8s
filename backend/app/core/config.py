"""
Application Configuration
Centralized settings management using Pydantic
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # ═══════════════════════════════════════════════════════════════
    # API Keys
    # ═══════════════════════════════════════════════════════════════
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    RESEND_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════
    # Qdrant DB
    # ═══════════════════════════════════════════════════════════════
    QDRANT_URL: str = "http://localhost:6380"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "doc-rag"
    QDRANT_DIMENSION: int = 3072
    QDRANT_METRIC: str = "dotproduct"

    # ═══════════════════════════════════════════════════════════════
    # Neon Database & JWT Authentication
    # ═══════════════════════════════════════════════════════════════
    DATABASE_URL: str  # Neon PostgreSQL connection string
    JWT_SECRET: str    # Secret for signing/verifying JWT tokens
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 1 week

    # ═══════════════════════════════════════════════════════════════
    # LangSmith (Optional Tracing)
    # ═══════════════════════════════════════════════════════════════
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════
    # Ollama (Optional)
    # ═══════════════════════════════════════════════════════════════
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_API_KEY: Optional[str] = ""
    OLLAMA_MODEL: Optional[str] = "llama3.2:3b"

    GOOGLE_API_KEY: str = ""
    GOOGLE_CX: str = ""

    # ═══════════════════════════════════════════════════════════════
    # Pexels (Image Search)
    # ═══════════════════════════════════════════════════════════════
    PEXELS_API_KEY: str = ""

    # ═══════════════════════════════════════════════════════════════
    # Tavily (Web Search — fallback when no docs uploaded)
    # ═══════════════════════════════════════════════════════════════
    TAVILY_API_KEY: str = ""

    # ═══════════════════════════════════════════════════════════════
    # MLflow (Experiment Tracking & Monitoring)
    # ═══════════════════════════════════════════════════════════════
    MLFLOW_TRACKING_URI: str = "http://mlflow:5000/mlflow"
    MLFLOW_EXPERIMENT_NAME: str = "doc-rag-chat"

    # ═══════════════════════════════════════════════════════════════
    # Application Settings
    # ═══════════════════════════════════════════════════════════════
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    DEFAULT_TOP_K: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (singleton pattern)"""
    return Settings()
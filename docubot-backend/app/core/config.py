"""
DocuBot — Configuración central de la aplicación.
Carga variables de entorno con Pydantic Settings.
Stack: OpenAI directo + almacenamiento local (Railway/Render compatible).
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Entorno
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Base de datos
    DATABASE_URL: str

    # OpenAI (directo, sin Azure)
    OPENAI_API_KEY: str
    OPENAI_MODEL_GPT4O: str = "gpt-4o"
    OPENAI_MODEL_EMBEDDINGS: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # Almacenamiento de archivos (directorio local; en Railway usar volumen persistente)
    STORAGE_LOCAL_PATH: str = "/data/documents"

    # JWT / Auth simple (reemplaza Azure AD B2C en esta versión)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 horas

    # Límites operacionales
    MAX_FILE_SIZE_MB: int = 50
    MAX_PAGES_PER_DOCUMENT: int = 1000
    RAG_DEFAULT_TOP_K: int = 8
    RAG_MAX_TOP_K: int = 20
    OCR_TIMEOUT_SECONDS: int = 60
    GPT_TIMEOUT_SECONDS: int = 60

    # CORS
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://aurenza-group.netlify.app",
        "https://docubot.aurenzagroup.cl",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

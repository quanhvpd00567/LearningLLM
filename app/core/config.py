from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Learning LLM API"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_timeout_seconds: float = Field(default=180, gt=0)

    # Postgres (asyncpg DSN – dùng postgresql+asyncpg:// hoặc postgresql://)
    database_url: str = "postgresql://app:changeme@localhost:5432/semantic_search"

    # Embedding service
    embedding_url: str = "http://localhost:8001"
    embedding_timeout_seconds: float = Field(default=60, gt=0)

    # Search defaults
    search_default_top_k: int = Field(default=5, ge=1, le=100)


@lru_cache
def get_settings() -> Settings:
    return Settings()

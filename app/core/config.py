from functools import lru_cache
from pydantic import Field, SecretStr
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

    # Embeddings use the same Ollama runtime as chat.
    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_dimensions: int = Field(default=1024, ge=1024, le=1024)
    embedding_timeout_seconds: float = Field(default=120, gt=0)

    embedding_batch_size: int = Field(default=8, ge=1, le=64)
    embedding_job_poll_seconds: float = Field(default=5, gt=0)
    embedding_job_lease_seconds: float = Field(default=600, ge=3)
    embedding_job_retry_seconds: float = Field(default=5, gt=0)

    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("")
    admin_cookie_secure: bool = False
    admin_tenant_id: str = "demo"

    store_cookie_secure: bool = False
    shipping_fee_vnd: int = Field(default=30000, ge=0, le=10000000)

    # Search defaults
    search_default_top_k: int = Field(default=5, ge=1, le=100)


@lru_cache
def get_settings() -> Settings:
    return Settings()

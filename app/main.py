from contextlib import asynccontextmanager
import httpx
import asyncpg
from fastapi import FastAPI

from app.api.routes import chat, health, search
from app.core.config import get_settings
from app.services.ollama import OllamaService
from app.services.search import SearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # asyncpg yêu cầu DSN dạng postgresql:// (không có +asyncpg)
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url,
        timeout=settings.ollama_timeout_seconds,
    ) as ollama_client, httpx.AsyncClient(
        base_url=settings.embedding_url,
        timeout=settings.embedding_timeout_seconds,
    ) as embed_client:

        pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
        try:
            app.state.ollama = OllamaService(ollama_client, settings.ollama_model)
            app.state.search = SearchService(pool, embed_client)
            yield
        finally:
            await pool.close()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")

from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from app.api.routes import chat, health
from app.core.config import get_settings
from app.services.ollama import OllamaService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url,
        timeout=settings.ollama_timeout_seconds,
    ) as client:
        app.state.ollama = OllamaService(client, settings.ollama_model)
        yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from app.core.observability import configure_logging, ObservabilityMiddleware
from app.api.routes import monitoring

configure_logging()

from app.api.routes import admin, ai_health, chat, customer_auth, health, search, store
from app.core.config import get_settings
from app.db.session import create_database
from app.services.embedding import EmbeddingService
from app.services.gemini import GeminiService
from app.services.search import SearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine, sessions = create_database(settings.database_url)
    try:
        async with httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com", timeout=settings.gemini_timeout_seconds,
        ) as gemini_client, httpx.AsyncClient(
            base_url=settings.ollama_base_url, timeout=settings.embedding_timeout_seconds,
        ) as embed_client:
            app.state.db_engine = engine
            app.state.db_sessions = sessions
            app.state.chat = GeminiService(gemini_client, settings.gemini_model, settings.gemini_api_key.get_secret_value(), settings.gemini_max_output_tokens)
            app.state.embedding = EmbeddingService(embed_client, settings.embedding_model, settings.embedding_dimensions)
            app.state.search = SearchService(sessions, app.state.embedding)
            yield
    finally:
        await engine.dispose()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.add_middleware(ObservabilityMiddleware)
app.include_router(monitoring.router, prefix="/api/v1")

@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})

app.include_router(store.router, prefix="/api/v1")
app.include_router(customer_auth.router, prefix="/api/v1")
app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")

app.include_router(admin.auth_router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(ai_health.router, prefix="/api/v1")
# One React build serves both storefront and /admin, with APIs registered first.
ui_dist = Path(__file__).resolve().parent / "static" / "admin"
if not ui_dist.exists():
    ui_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if ui_dist.exists():
    @app.get("/login", include_in_schema=False)
    @app.get("/register", include_in_schema=False)
    @app.get("/account", include_in_schema=False)
    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/", include_in_schema=False)
    async def admin_page():
        from fastapi.responses import FileResponse
        return FileResponse(ui_dist / "index.html")

    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="web-ui")

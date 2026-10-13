from fastapi import Request
from app.services.ollama import OllamaService
from app.services.search import SearchService


def get_ollama_service(request: Request) -> OllamaService:
    return request.app.state.ollama


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search

from fastapi import Request
from app.services.gemini import GeminiService
from app.services.search import SearchService


def get_chat_service(request: Request) -> GeminiService:
    return request.app.state.chat


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search

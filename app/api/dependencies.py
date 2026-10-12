from fastapi import Request
from app.services.ollama import OllamaService


def get_ollama_service(request: Request) -> OllamaService:
    return request.app.state.ollama

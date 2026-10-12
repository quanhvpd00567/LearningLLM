from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.dependencies import get_ollama_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ollama import OllamaService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, service: Annotated[OllamaService, Depends(get_ollama_service)]):
    return await service.chat(body)

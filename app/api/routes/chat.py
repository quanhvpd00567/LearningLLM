from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.gemini import GeminiService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, service: Annotated[GeminiService, Depends(get_chat_service)]):
    if any(message.role == "system" for message in body.messages):
        raise HTTPException(422, "Client không được đặt system prompt.")
    return await service.chat(body)

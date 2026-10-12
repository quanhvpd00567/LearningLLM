from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0, le=2)


class ChatResponse(BaseModel):
    model: str
    message: Message
    done: bool

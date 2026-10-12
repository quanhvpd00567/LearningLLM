import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.chat import ChatRequest, ChatResponse


class OllamaService:
    def __init__(self, client: httpx.AsyncClient, model: str):
        self.client = client
        self.model = model

    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            response = await self.client.post("/api/chat", json={
                "model": self.model,
                "messages": [message.model_dump() for message in request.messages],
                "stream": False,
                "options": {"temperature": request.temperature},
            })
            response.raise_for_status()
            return ChatResponse.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Ollama xử lý quá thời gian chờ.") from exc
        except httpx.HTTPStatusError as exc:
            detail = "Chưa tải model. Kiểm tra OLLAMA_MODEL và chạy ollama pull." if exc.response.status_code == 404 else "Ollama trả về lỗi. Kiểm tra log của Ollama."
            raise HTTPException(502, detail) from exc
        except httpx.RequestError as exc:
            raise HTTPException(503, "Không kết nối được Ollama.") from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(502, "Phản hồi Ollama không hợp lệ.") from exc

"""Explicit admin probes use the same model clients and guardrails as production."""
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.core.admin_auth import admin_db, require_admin
from app.core.config import get_settings
from app.db.models import AdminSettings
from app.schemas.chat import ChatRequest, Message

router = APIRouter(prefix="/admin/ai-health", tags=["AI health"], dependencies=[Depends(require_admin, scope="function")])


@router.get("")
async def configuration(request: Request, session=Depends(admin_db, scope="function")):
    s = get_settings()
    return {"models": [
        {"id": "gemini", "name": "Gemini · Chat", "model": request.app.state.chat.model,
         "configured": bool(request.app.state.chat.api_key.strip())},
        {"id": "embedding", "name": "Ollama · Embedding", "model": request.app.state.embedding.model,
         "configured": True, "dimensions": s.embedding_dimensions},
    ], "embedding_paused": bool(await session.scalar(select(AdminSettings.embedding_paused).where(AdminSettings.id == 1)))}


@router.post("/{provider}")
async def probe(provider: Literal["gemini", "embedding"], request: Request):
    started = perf_counter()
    service = request.app.state.chat if provider == "gemini" else request.app.state.embedding
    result = {"provider": provider, "model": service.model, "status": "ok", "detail": "Model phản hồi hợp lệ."}
    try:
        if provider == "gemini":
            await service.chat(ChatRequest(messages=[Message(role="user", content="Trả lời ngắn bằng tiếng Việt: Xin chào.")], temperature=0))
        else:
            vector = await service.embed_query("Kiểm tra kết nối embedding")
            result["dimensions"] = len(vector)
    except HTTPException as exc:
        result.update(status="error", detail=str(exc.detail), http_status=exc.status_code)
        cause = exc.__cause__
        if isinstance(cause, httpx.HTTPStatusError):
            status = cause.response.status_code
            result["upstream_status"] = status
            # Fixed actionable messages; never expose provider payloads, credentials or URLs.
            result["detail"] = {
                400: "Upstream từ chối yêu cầu. Kiểm tra API key, model và cấu hình request.",
                401: "API key không hợp lệ. Kiểm tra GEMINI_API_KEY và tạo lại container API.",
                403: "API key không có quyền gọi model hoặc bị giới hạn truy cập.",
                404: "Model không tồn tại hoặc không còn khả dụng cho tài khoản. Kiểm tra model đang cấu hình.",
                429: "Đã vượt hạn mức hoặc tần suất gọi model. Kiểm tra quota trong Google AI Studio.",
            }.get(status, "Dịch vụ model trả lỗi. Kiểm tra trạng thái upstream và thử lại sau.")
    result["latency_ms"] = round((perf_counter() - started) * 1000)
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    return result

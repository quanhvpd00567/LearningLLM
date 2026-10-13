from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.dependencies import get_search_service
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("", response_model=SearchResponse, summary="Tìm kiếm ngữ nghĩa")
async def search(
    body: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    """
    Nhận query text, tạo embedding, tìm kiếm bằng cosine distance trong pgvector
    và lọc theo metadata.

    - **query**: câu truy vấn tiếng Việt hoặc tiếng Anh
    - **top_k**: số kết quả trả về (mặc định 5)
    - **filter.tenant_id**: bắt buộc – cô lập dữ liệu theo tenant
    - **filter.metadata**: lọc thêm trên cột JSONB, vd `{"category": "llm"}`
    """
    return await service.search(body)

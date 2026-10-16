from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class MetadataFilter(BaseModel):
    """Lọc theo các trường trong cột metadata (JSONB) hoặc cột trực tiếp.

    Ví dụ:
        {"tenant_id": "tenant_acme", "language": "vi", "status": "current"}
    """
    tenant_id: str = Field(description="Bắt buộc – isolate dữ liệu theo tenant")
    language: str | None = Field(default=None, description="Lọc theo ngôn ngữ, vd 'vi'")
    status: str | None = Field(default="current", description="Lọc theo trạng thái chunk")
    # Lọc động trên metadata JSONB: {"category": "llm", ...}
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Lọc thêm trên cột metadata JSONB, vd {\"category\": \"llm\"}",
    )


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000, description="Câu truy vấn")
    top_k: int = Field(default=5, ge=1, le=50, description="Số kết quả trả về")
    filter: MetadataFilter = Field(description="Bộ lọc bắt buộc")


class SearchResult(BaseModel):
    id: UUID
    document_id: UUID
    content: str
    score: float = Field(description="Normalized score = 1 - cosine_distance / 2, trong [0, 1]")
    tenant_id: str
    language: str
    status: str
    metadata: dict[str, Any] | None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]

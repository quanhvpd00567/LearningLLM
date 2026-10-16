"""Semantic search using SQLAlchemy and pgvector."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.chatbot.rag.chunking import PIPELINE_VERSION
from app.db.models import DocumentChunk
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.embedding import EmbeddingService


class SearchService:
    def __init__(self, sessions: async_sessionmaker, embedding: EmbeddingService):
        self.sessions = sessions
        self.embedding = embedding

    async def search(self, req: SearchRequest) -> SearchResponse:
        vector = await self.embedding.embed_query(req.query)
        distance = DocumentChunk.embedding.cosine_distance(vector)
        stmt = select(DocumentChunk, distance.label("distance")).where(
            DocumentChunk.tenant_id == req.filter.tenant_id,
            DocumentChunk.status == (req.filter.status or "current"),
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_model == self.embedding.model,
            DocumentChunk.pipeline_version == PIPELINE_VERSION,
        )
        if req.filter.language:
            stmt = stmt.where(DocumentChunk.language == req.filter.language)
        if req.filter.metadata:
            stmt = stmt.where(DocumentChunk.metadata_json.contains(req.filter.metadata))
        stmt = stmt.order_by(distance).limit(req.top_k)
        try:
            async with self.sessions() as session:
                rows = (await session.execute(stmt)).all()
        except SQLAlchemyError as exc:
            raise HTTPException(503, "Không truy vấn được dữ liệu tìm kiếm.") from exc
        results = [SearchResult(
            id=chunk.id, document_id=chunk.document_id, content=chunk.content,
            score=round(max(0.0, min(1.0, 1 - float(value) / 2)), 6),
            tenant_id=chunk.tenant_id, language=chunk.language, status=chunk.status,
            metadata=chunk.metadata_json,
        ) for chunk, value in rows]
        return SearchResponse(query=req.query, total=len(results), results=results)

"""SearchService: embed query → pgvector cosine search → metadata filter."""
import json
import httpx
import asyncpg
from fastapi import HTTPException

from app.schemas.search import SearchRequest, SearchResponse, SearchResult


class SearchService:
    def __init__(
        self,
        pool: asyncpg.Pool,
        embed_client: httpx.AsyncClient,
    ) -> None:
        self._pool = pool
        self._embed_client = embed_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, req: SearchRequest) -> SearchResponse:
        embedding = await self._embed(req.query)
        rows = await self._query(embedding, req)
        results = [
            SearchResult(
                id=row["id"],
                document_id=row["document_id"],
                content=row["content"],
                # pgvector cosine *distance* ∈ [0, 2]; similarity = 1 - distance/2
                score=round(1 - row["distance"] / 2, 6),
                tenant_id=row["tenant_id"],
                language=row["language"],
                status=row["status"],
                # asyncpg trả JSONB về dạng str – parse thủ công
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"],
            )
            for row in rows
        ]
        return SearchResponse(query=req.query, total=len(results), results=results)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _embed(self, text: str) -> list[float]:
        """Gọi embedding service, trả về vector float[]."""
        try:
            resp = await self._embed_client.post("/embed", json={"texts": [text]})
            resp.raise_for_status()
            return resp.json()["embeddings"][0]
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Embedding service xử lý quá thời gian chờ.") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(502, f"Embedding service lỗi: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise HTTPException(503, "Không kết nối được embedding service.") from exc

    async def _query(
        self, embedding: list[float], req: SearchRequest
    ) -> list[asyncpg.Record]:
        """Xây dynamic SQL với cosine distance (<=>), trả về top_k rows."""
        f = req.filter

        # Params list – thứ tự khớp với $1, $2, ...
        params: list = []

        def add(value) -> str:
            """Thêm param, trả về placeholder $n."""
            params.append(value)
            return f"${len(params)}"

        # Các điều kiện WHERE
        conditions: list[str] = []

        conditions.append(f"tenant_id = {add(f.tenant_id)}")
        conditions.append(f"status = {add(f.status or 'current')}")

        if f.language:
            conditions.append(f"language = {add(f.language)}")

        # Lọc động trên cột metadata JSONB
        # metadata @> '{"category": "llm"}'::jsonb
        if f.metadata:
            for key, value in f.metadata.items():
                conditions.append(
                    f"metadata @> {add(json.dumps({key: value}))}::jsonb"
                )

        # Vector embedding dạng chuỗi "[0.1, 0.2, ...]"
        vec_str = "[" + ",".join(map(str, embedding)) + "]"
        vec_ph = add(vec_str)
        limit_ph = add(req.top_k)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                id,
                document_id,
                content,
                tenant_id,
                language,
                status,
                metadata,
                (embedding <=> {vec_ph}::vector) AS distance
            FROM document_chunks
            WHERE {where}
            ORDER BY distance
            LIMIT {limit_ph}
        """

        try:
            async with self._pool.acquire() as conn:
                return await conn.fetch(sql, *params)
        except asyncpg.PostgresError as exc:
            raise HTTPException(502, f"Database lỗi: {exc}") from exc

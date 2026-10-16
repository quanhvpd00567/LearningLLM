import math

import httpx
from fastapi import HTTPException


class EmbeddingService:
    def __init__(self, client: httpx.AsyncClient, model: str, dimensions: int = 1024):
        self.client = client
        self.model = model
        self.dimensions = dimensions

    async def embed_query(self, query: str) -> list[float]:
        instruction = "Given a Vietnamese ecommerce query, retrieve relevant product descriptions or knowledge passages."
        return (await self.embed_documents([f"Instruct: {instruction}\nQuery: {query}"]))[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not value.strip() for value in texts):
            raise ValueError("Embedding inputs must not be empty")
        try:
            response = await self.client.post("/api/embed", json={
                "model": self.model, "input": texts, "truncate": False,
            })
            response.raise_for_status()
            vectors = response.json()["embeddings"]
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise ValueError("Unexpected embedding count")
            for vector in vectors:
                if not isinstance(vector, list) or len(vector) != self.dimensions:
                    raise ValueError("Unexpected embedding dimensions")
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
                    raise ValueError("Invalid embedding values")
                if not any(vector):
                    raise ValueError("Zero vector cannot be used for cosine search")
            return vectors
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Embedding xử lý quá thời gian chờ.") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(502, "Ollama embedding trả lỗi. Kiểm tra model và input.") from exc
        except httpx.RequestError as exc:
            raise HTTPException(503, "Không kết nối được Ollama embedding.") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(502, "Phản hồi embedding không hợp lệ.") from exc

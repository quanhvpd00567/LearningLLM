import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from app.services.embedding import EmbeddingService


def run_embedding(handler, texts=None, query=None):
    async def run():
        async with httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler)) as client:
            service = EmbeddingService(client, "qwen3-embedding:0.6b")
            if query is not None:
                return await service.embed_query(query)
            return await service.embed_documents(texts or ["Chính sách đổi trả"])
    return asyncio.run(run())


def test_documents_are_not_prefixed_and_batch_order_is_preserved():
    def handler(request):
        assert request.url.path == "/api/embed"
        assert json.loads(request.content) == {
            "model": "qwen3-embedding:0.6b", "input": ["Giày", "Đổi trả"], "truncate": False,
        }
        return httpx.Response(200, json={"embeddings": [[1.0] * 1024, [0.5] * 1024]})
    result = run_embedding(handler, ["Giày", "Đổi trả"])
    assert result[0][0] == 1.0
    assert result[1][0] == 0.5


def test_query_uses_retrieval_instruction():
    def handler(request):
        text = json.loads(request.content)["input"][0]
        assert text.startswith("Instruct: ")
        assert text.endswith("\nQuery: Giày dưới một triệu")
        return httpx.Response(200, json={"embeddings": [[0.1] * 1024]})
    assert len(run_embedding(handler, query="Giày dưới một triệu")) == 1024


@pytest.mark.parametrize("payload", [
    {}, {"embeddings": []}, {"embeddings": [[1.0] * 768]},
    {"embeddings": [[0.0] * 1024]}, {"embeddings": [["bad"] * 1024]},
    {"embeddings": [[True] * 1024]}, {"embeddings": None},
])
def test_rejects_invalid_upstream_embeddings(payload):
    with pytest.raises(HTTPException) as error:
        run_embedding(lambda request: httpx.Response(200, json=payload))
    assert error.value.status_code == 502


@pytest.mark.parametrize("failure,status", [
    (httpx.ConnectError, 503), (httpx.ReadTimeout, 504),
])
def test_embedding_transport_errors(failure, status):
    def handler(request):
        raise failure("upstream failure", request=request)
    with pytest.raises(HTTPException) as error:
        run_embedding(handler)
    assert error.value.status_code == status


def test_embedding_http_failure():
    with pytest.raises(HTTPException) as error:
        run_embedding(lambda request: httpx.Response(404))
    assert error.value.status_code == 502

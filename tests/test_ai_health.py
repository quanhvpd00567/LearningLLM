import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routes.ai_health import router
from app.core.admin_auth import admin_db, require_admin
from app.services.embedding import EmbeddingService
from app.services.gemini import GeminiService


def setup_client(handler, key="secret-key"):
    upstream = httpx.AsyncClient(base_url="https://example.com", transport=httpx.MockTransport(handler))
    app = FastAPI()
    app.state.chat = GeminiService(upstream, "test-model", key)
    app.state.embedding = EmbeddingService(upstream, "test-embedding")
    app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: "admin"
    return app, TestClient(app)


def test_probe_runs_real_clients_and_validates_vectors():
    def handler(request):
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[1.0] * 1024]})
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "Xin chào"}]}}]})
    _, client = setup_client(handler)
    for provider in ("gemini", "embedding"):
        result = client.post("/admin/ai-health/" + provider).json()
        assert result["status"] == "ok"
        assert result["latency_ms"] >= 0
        assert result["checked_at"]
    assert client.post("/admin/ai-health/embedding").json()["dimensions"] == 1024


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_errors_are_actionable_without_provider_payload_or_key(status):
    _, client = setup_client(lambda request: httpx.Response(status, json={"error": "secret-key sensitive-provider-payload"}))
    response = client.post("/admin/ai-health/gemini")
    assert response.json()["status"] == "error"
    assert response.json()["upstream_status"] == status
    assert "secret-key" not in response.text
    assert "sensitive-provider-payload" not in response.text


def test_missing_key_does_not_call_provider():
    def unexpected(request):
        pytest.fail("must not call upstream without key")
    _, client = setup_client(unexpected, key="")
    result = client.post("/admin/ai-health/gemini").json()
    assert result["http_status"] == 503
    assert "GEMINI_API_KEY" in result["detail"]


def test_invalid_vectors_and_timeout_are_not_healthy():
    _, client = setup_client(lambda request: httpx.Response(200, json={"embeddings": [[1.0]]}))
    assert client.post("/admin/ai-health/embedding").json()["status"] == "error"
    def timeout(request):
        raise httpx.ReadTimeout("secret-key", request=request)
    _, client = setup_client(timeout)
    assert client.post("/admin/ai-health/gemini").json()["http_status"] == 504


def test_config_does_not_probe_or_expose_key_and_reports_pause():
    def unexpected(request):
        pytest.fail("configuration must not use quota")
    app, client = setup_client(unexpected)
    class Session:
        async def scalar(self, statement):
            return True
    app.dependency_overrides[admin_db] = lambda: Session()
    response = client.get("/admin/ai-health")
    assert response.json()["embedding_paused"] is True
    assert response.json()["models"][0]["configured"] is True
    assert "secret-key" not in response.text


def test_probes_require_admin_and_only_known_providers():
    app, client = setup_client(lambda request: pytest.fail("no probe expected"))
    assert client.post("/admin/ai-health/arbitrary").status_code == 422
    def reject():
        raise HTTPException(401, "Login required")
    app.dependency_overrides[require_admin] = reject
    assert client.get("/admin/ai-health").status_code == 401
    assert client.post("/admin/ai-health/gemini").status_code == 401

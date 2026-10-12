import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.dependencies import get_ollama_service
from app.main import app
from app.services.ollama import OllamaService


@pytest.fixture
def api():
    clients = []

    def configure(handler):
        client = httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler))
        clients.append(client)
        app.dependency_overrides[get_ollama_service] = lambda: OllamaService(client, "test-model")

    with TestClient(app) as client:
        yield client, configure
    app.dependency_overrides.clear()


def test_chat_payload_and_response(api):
    client, configure = api

    def handler(request):
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "Xin chào"}]
        return httpx.Response(200, json={"model": "test-model", "message": {"role": "assistant", "content": "Chào bạn"}, "done": True})

    configure(handler)
    response = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Xin chào"}]})
    assert response.status_code == 200
    assert response.json()["message"]["content"] == "Chào bạn"


@pytest.mark.parametrize("status,expected", [(404, 502), (500, 502)])
def test_upstream_errors(api, status, expected):
    client, configure = api
    configure(lambda request: httpx.Response(status, json={"error": "upstream error"}))
    assert client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]}).status_code == expected


@pytest.mark.parametrize("error,expected", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_connection_errors(api, error, expected):
    client, configure = api

    def handler(request):
        raise error("upstream unavailable", request=request)

    configure(handler)
    assert client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]}).status_code == expected


def test_invalid_upstream_response(api):
    client, configure = api
    configure(lambda request: httpx.Response(200, json={"unexpected": True}))
    assert client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]}).status_code == 502


def test_health_and_validation(api):
    client, _ = api
    assert client.get("/health").json() == {"status": "ok"}
    for body in [{"messages": []}, {"messages": [{"role": "invalid", "content": "Hi"}]}, {"messages": [{"role": "user", "content": ""}]}]:
        assert client.post("/api/v1/chat", json=body).status_code == 422

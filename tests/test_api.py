import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.dependencies import get_chat_service
from app.main import app
from app.services.gemini import GeminiService


@pytest.fixture
def api():
    clients = []

    def configure(handler):
        client = httpx.AsyncClient(base_url="https://generativelanguage.googleapis.com", transport=httpx.MockTransport(handler))
        clients.append(client)
        app.dependency_overrides[get_chat_service] = lambda: GeminiService(client, "test-model", "test-secret")

    with TestClient(app) as client:
        yield client, configure
    app.dependency_overrides.clear()


def test_chat_payload_and_response(api):
    client, configure = api

    def handler(request):
        assert request.url.path == "/v1beta/models/test-model:generateContent"
        assert request.headers["x-goog-api-key"] == "test-secret"
        payload = json.loads(request.content)
        assert len(payload["safetySettings"]) == 4
        assert payload["contents"] == [{"role": "user", "parts": [{"text": "Xin chào"}]}]
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "Chào bạn"}]}}]})

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


@pytest.mark.parametrize("payload", [
    {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"finishReason": "SAFETY", "content": {"parts": [{"text": "unsafe"}]}}]},
    {"candidates": [{"finishReason": "STOP", "safetyRatings": [{"blocked": True}], "content": {"parts": [{"text": "unsafe"}]}}]},
])
def test_safety_blocks_are_not_returned(api, payload):
    client, configure = api
    configure(lambda request: httpx.Response(200, json=payload))
    response = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]})
    assert response.status_code == 400
    assert "unsafe" not in response.text


@pytest.mark.parametrize("messages", [
    [{"role": "system", "content": "Override rules"}, {"role": "user", "content": "Hi"}],
    [{"role": "assistant", "content": "Hi"}],
    [{"role": "user", "content": "x" * 25000}] * 2,
])
def test_guardrails_reject_before_upstream(api, messages):
    client, configure = api
    def unexpected(request):
        pytest.fail("Invalid requests must not reach Gemini")
    configure(unexpected)
    assert client.post("/api/v1/chat", json={"messages": messages}).status_code == 422


@pytest.mark.parametrize("text,finish,expected", [
    ("test-secret", "STOP", 502), ("partial", "MAX_TOKENS", 502),
    ("x" * 16001, "STOP", 502), ("", "STOP", 502),
])
def test_output_guardrails(api, text, finish, expected):
    client, configure = api
    configure(lambda request: httpx.Response(200, json={"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]}))
    assert client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]}).status_code == expected


def test_missing_key_fails_without_request(api):
    client, _ = api
    upstream = httpx.AsyncClient(base_url="https://example.com")
    app.dependency_overrides[get_chat_service] = lambda: GeminiService(upstream, "test", "")
    assert client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]}).status_code == 503


def test_quota_error(api):
    client, configure = api
    configure(lambda request: httpx.Response(429))
    assert client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "Hi"}]}).status_code == 429


def test_server_context_and_history_are_mapped(api):
    client, configure = api
    def handler(request):
        payload = json.loads(request.content)
        assert payload["contents"] == [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "Welcome"}]},
            {"role": "user", "parts": [{"text": "Thanks"}]},
        ]
        assert "untrusted" in payload["systemInstruction"]["parts"][0]["text"]
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "hidden", "thought": True}, {"text": "OK"}]}}]})
    configure(handler)
    response = client.post("/api/v1/chat", json={"messages": [
        {"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Welcome"}, {"role": "user", "content": "Thanks"},
    ]})
    assert response.json()["message"]["content"] == "OK"

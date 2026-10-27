import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.monitoring import router
from app.core.admin_auth import require_admin


def client_with_backend(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr("app.api.routes.monitoring.httpx.AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: "admin"
    return TestClient(app)


def test_monitoring_partial_outage_and_nonfinite_metrics(monkeypatch):
    def handler(request):
        if request.url.host == "loki":
            return httpx.Response(503)
        expression = request.url.params["query"]
        if expression == "docker_stats_up":
            result = [{"metric": {}, "value": [1, "0"]}]
        elif "histogram_quantile" in expression:
            result = [{"metric": {}, "value": [1, "NaN"]}]
        else:
            result = []
        return httpx.Response(200, json={"status": "success", "data": {"result": result}})
    client = client_with_backend(monkeypatch, handler)
    response = client.get("/admin/monitoring")
    assert response.status_code == 200
    data = response.json()
    assert data["latency_p95_seconds"] is None
    assert data["logs"] == []
    assert len(data["errors"]) == 2


def test_service_filter_is_validated_and_applied_upstream(monkeypatch):
    queries = []
    def handler(request):
        if request.url.host == "loki":
            queries.append(request.url.params["query"])
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})
    client = client_with_backend(monkeypatch, handler)
    assert client.get("/admin/monitoring?service=worker").status_code == 200
    assert queries == ['{service_name="worker"}']
    assert client.get('/admin/monitoring?service=other').status_code == 422

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from app.core.observability import JsonFormatter, ObservabilityMiddleware, REQUESTS
from monitoring.exporter.exporter import stats_values


def test_docker_cpu_and_working_set():
    values = stats_values({
        "cpu_stats": {"cpu_usage": {"total_usage": 400}, "system_cpu_usage": 1000, "online_cpus": 4},
        "precpu_stats": {"cpu_usage": {"total_usage": 300}, "system_cpu_usage": 200},
        "memory_stats": {"usage": 900, "limit": 2000, "stats": {"inactive_file": 200}},
        "networks": {"eth0": {"rx_bytes": 50, "tx_bytes": 60}, "eth1": {"rx_bytes": 10}},
    })
    assert values == {"cpu_percent": 50, "memory_bytes": 700, "memory_limit_bytes": 2000, "network_receive_bytes": 60, "network_transmit_bytes": 60}
    assert stats_values({})["cpu_percent"] == 0


def test_request_id_streaming_and_logs_do_not_include_secrets(caplog):
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/stream/{identifier}")
    async def stream(identifier: str):
        async def chunks():
            yield b"one"
            yield b"two"
        return StreamingResponse(chunks())

    with caplog.at_level(logging.INFO, logger="app.http"):
        response = TestClient(app).get("/stream/private-id?password=secret", headers={"Cookie": "session=secret"})
    assert response.text == "onetwo"
    assert len(response.headers["x-request-id"]) == 32
    record = next(record for record in caplog.records if record.message == "http_request")
    assert record.route == "/stream/{identifier}"
    assert record.status == 200
    assert "secret" not in JsonFormatter().format(record)
    assert "private-id" not in JsonFormatter().format(record)
    assert REQUESTS.labels("GET", "/stream/{identifier}", "200")._value.get() >= 1


def test_error_logged_without_exception_secrets(caplog):
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/failure")
    async def failure():
        raise RuntimeError("password=hidden")

    with caplog.at_level(logging.ERROR, logger="app.http"):
        response = TestClient(app, raise_server_exceptions=False).get("/failure")
    assert response.status_code == 500
    record = next(record for record in caplog.records if record.message == "request_failed")
    formatted = json.loads(JsonFormatter().format(record))
    assert formatted["error_type"] == "RuntimeError"
    assert "hidden" not in json.dumps(formatted)

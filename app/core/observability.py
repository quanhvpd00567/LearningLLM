"""Structured operational logs and bounded-cardinality HTTP metrics."""
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
import time
import traceback
from uuid import uuid4

from prometheus_client import Counter, Histogram

request_id = ContextVar("request_id", default=None)
REQUESTS = Counter("app_http_requests_total", "HTTP responses", ["method", "route", "status"])
DURATION = Histogram("app_http_request_duration_seconds", "HTTP latency including streaming", ["method", "route"])


class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                  "logger": record.name, "message": record.getMessage(), "request_id": request_id.get()}
        for key in ("method", "route", "status", "duration_ms", "username", "event"):
            if hasattr(record, key):
                result[key] = getattr(record, key)
        if record.exc_info:
            # Stack locations and error type only; exception text can contain credentials or payloads.
            result["error_type"] = record.exc_info[0].__name__
            result["stack"] = [{"file": frame.filename, "line": frame.lineno, "function": frame.name}
                               for frame in traceback.extract_tb(record.exc_info[2])]
        return json.dumps(result, ensure_ascii=False)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    # Middleware records access without query strings, cookies, headers or bodies.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class ObservabilityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = request_id.set(uuid4().hex)
        started, status = time.monotonic(), 500
        failed = False

        async def send_response(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = {**message, "headers": list(message.get("headers", [])) + [(b"x-request-id", request_id.get().encode())]}
            await send(message)
        try:
            await self.app(scope, receive, send_response)
        except Exception:
            failed = True
            logging.getLogger("app.http").exception("request_failed")
            raise
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            elapsed = time.monotonic() - started
            method = scope["method"] if scope["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"} else "OTHER"
            REQUESTS.labels(method, route, str(500 if failed else status)).inc()
            DURATION.labels(method, route).observe(elapsed)
            if scope["path"] not in {"/health", "/metrics"} or status >= 400 or failed:
                logging.getLogger("app.http").log(logging.ERROR if failed or status >= 500 else logging.WARNING if status >= 400 else logging.INFO,
                    "http_request", extra={"method": method, "route": route, "status": 500 if failed else status, "duration_ms": round(elapsed * 1000, 2)})
            request_id.reset(token)

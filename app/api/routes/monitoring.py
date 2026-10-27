"""Admin-only, fixed monitoring queries. Backends remain on the Docker network."""
import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Literal

import httpx
from fastapi import APIRouter, Depends

from app.core.admin_auth import require_admin
from app.core.config import get_settings

router = APIRouter(prefix="/admin/monitoring", tags=["Monitoring"], dependencies=[Depends(require_admin, scope="function")])
logger = logging.getLogger(__name__)


@router.get("")
async def monitoring(service: Literal["api", "worker", "postgres", "ollama", "migrate"] | None = None):
    settings = get_settings()
    errors = []
    async with httpx.AsyncClient(timeout=5) as client:
        async def query(name, expression):
            try:
                response = await client.get(settings.prometheus_url + "/api/v1/query", params={"query": expression})
                response.raise_for_status()
                data = response.json()
                if data.get("status") != "success":
                    raise ValueError("Prometheus query failed")
                return name, data["data"]["result"]
            except (httpx.HTTPError, ValueError, KeyError):
                errors.append("Không lấy được metrics: " + name)
                logger.warning("monitoring_query_failed", extra={"event": name})
                return name, []
        async def logs():
            try:
                response = await client.get(settings.loki_url + "/loki/api/v1/query_range", params={
                    "query": '{service_name="' + service + '"}' if service else '{service_name=~"api|worker|postgres|ollama|migrate"}',
                    "start": str(int((time.time() - 900) * 1e9)), "limit": 60, "direction": "backward"})
                response.raise_for_status()
                entries = [{"timestamp": timestamp, "service": stream["stream"].get("service_name", ""), "line": line}
                           for stream in response.json()["data"]["result"] for timestamp, line in stream["values"]]
                return sorted(entries, key=lambda entry: int(entry["timestamp"]), reverse=True)[:60]
            except (httpx.HTTPError, ValueError, KeyError):
                errors.append("Không lấy được log từ Loki.")
                return []
        tasks = [query("cpu", "docker_container_cpu_percent"),
                 query("memory", "docker_container_memory_bytes"),
                 query("limit", "docker_container_memory_limit_bytes"),
                 query("rx", "rate(docker_container_network_receive_bytes_total[2m])"),
                 query("tx", "rate(docker_container_network_transmit_bytes_total[2m])"),
                 query("targets", "up"), query("collector", "docker_stats_up"),
                 query("containers_up", "docker_container_stats_up"),
                 query("rps", "sum(rate(app_http_requests_total[2m]))"),
                 query("errors", 'sum(rate(app_http_requests_total{status=~"5.."}[2m]))'),
                 query("latency", "histogram_quantile(0.95, sum by (le) (rate(app_http_request_duration_seconds_bucket[5m])))")]
        results = await asyncio.gather(*tasks, logs())
    metrics = dict(results[:-1])
    containers = {}
    for key in ("cpu", "memory", "limit", "rx", "tx", "containers_up"):
        for sample in metrics[key]:
            name = sample["metric"]["container"]
            item = containers.setdefault(name, {"name": name, "service": sample["metric"].get("service", "")})
            value = float(sample["value"][1])
            item[key] = value if value == value and abs(value) != float("inf") else None
    def scalar(key):
        values = metrics[key]
        if not values:
            return None
        value = float(values[0]["value"][1])
        return value if value == value and abs(value) != float("inf") else None
    if scalar("collector") != 1:
        errors.append("Docker collector chưa có dữ liệu hoặc không truy cập được Docker.")
    return {"updated_at": datetime.now(timezone.utc).isoformat(), "grafana_url": settings.grafana_public_url.rstrip("/") + "/d/learningllm/system-monitoring",
            "containers": sorted(containers.values(), key=lambda item: item["service"]),
            "targets": [{"job": sample["metric"].get("job"), "up": sample["value"][1] == "1"} for sample in metrics["targets"]],
            "requests_per_second": scalar("rps"), "errors_per_second": scalar("errors"),
            "latency_p95_seconds": scalar("latency"), "logs": results[-1], "errors": errors}

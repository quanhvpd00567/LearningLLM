"""Read-only Docker Stats collector, including Docker Desktop and OrbStack VMs."""
import concurrent.futures
import http.client
import json
import logging
import os
import socket
import time

from prometheus_client import REGISTRY, start_http_server
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily

log = logging.getLogger("docker_metrics")


class DockerConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=4)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/var/run/docker.sock")


def docker_get(path):
    connection = DockerConnection()
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"Docker returned {response.status}")
        return json.loads(response.read())
    finally:
        connection.close()


def stats_values(stats):
    cpu = stats.get("cpu_stats", {})
    previous = stats.get("precpu_stats", {})
    delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - previous.get("cpu_usage", {}).get("total_usage", 0)
    system = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
    cores = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage", [])) or 1
    memory = stats.get("memory_stats", {})
    cache = memory.get("stats", {}).get("inactive_file", memory.get("stats", {}).get("total_inactive_file", 0))
    return {
        "cpu_percent": max(0, delta / system * cores * 100) if system > 0 and previous.get("system_cpu_usage", 0) > 0 else 0,
        "memory_bytes": max(0, memory.get("usage", 0) - cache),
        "memory_limit_bytes": memory.get("limit", 0),
        "network_receive_bytes": sum(n.get("rx_bytes", 0) for n in stats.get("networks", {}).values()),
        "network_transmit_bytes": sum(n.get("tx_bytes", 0) for n in stats.get("networks", {}).values()),
    }


class DockerCollector:
    def __init__(self):
        self.previous = {}

    def collect(self):
        labels = ["container", "service"]
        metrics = {
            key: (CounterMetricFamily if key.startswith("network") else GaugeMetricFamily)(
                "docker_container_" + key, key.replace("_", " "), labels=labels)
            for key in ("cpu_percent", "memory_bytes", "memory_limit_bytes", "network_receive_bytes", "network_transmit_bytes")
        }
        up = GaugeMetricFamily("docker_stats_up", "Docker discovery succeeded", value=0)
        container_up = GaugeMetricFamily("docker_container_stats_up", "Container stats available", labels=labels)
        try:
            from urllib.parse import quote
            filters = quote(json.dumps({"label": ["com.docker.compose.project=" + os.environ.get("COMPOSE_PROJECT", "learningllm")]}))
            containers = docker_get("/containers/json?filters=" + filters)
            active_ids = {container["Id"] for container in containers}
            self.previous = {key: value for key, value in self.previous.items() if key in active_ids}
            up = GaugeMetricFamily("docker_stats_up", "Docker discovery succeeded", value=1)
            def read(container):
                name = container["Names"][0].lstrip("/")
                service = container.get("Labels", {}).get("com.docker.compose.service", "unknown")
                try:
                    stats = docker_get(f'/containers/{container["Id"]}/stats?stream=false&one-shot=true')
                    previous = self.previous.get(container["Id"])
                    if previous is not None:
                        stats["precpu_stats"] = previous
                    self.previous[container["Id"]] = stats.get("cpu_stats", {})
                    return [name, service], stats_values(stats)
                except Exception as exc:
                    log.warning("stats_unavailable container=%s error=%s", name, type(exc).__name__)
                    return [name, service], None
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
                for values, stats in pool.map(read, containers):
                    container_up.add_metric(values, int(stats is not None))
                    if stats:
                        for key, value in stats.items():
                            metrics[key].add_metric(values, value)
        except Exception:
            log.exception("docker_discovery_failed")
        yield up
        yield container_up
        yield from metrics.values()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    REGISTRY.register(DockerCollector())
    start_http_server(9101)
    log.info("Docker metrics listening on :9101")
    while True:
        time.sleep(60)

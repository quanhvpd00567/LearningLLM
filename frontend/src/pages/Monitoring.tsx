import React, { useEffect, useState } from "react";
import { ExternalLink, Activity, Cpu, MemoryStick, Timer } from "lucide-react";
import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";

type Snapshot = {
  updated_at: string;
  grafana_url: string;
  containers: { name: string; service: string; cpu?: number; memory?: number; limit?: number; rx?: number; tx?: number; containers_up?: number }[];
  targets: { job: string; up: boolean }[];
  requests_per_second: number | null;
  errors_per_second: number | null;
  latency_p95_seconds: number | null;
  logs: { timestamp: string; service: string; line: string }[];
  errors: string[];
};
const number = (value: number | null | undefined, digits = 2) => value == null ? "—" : value.toLocaleString("vi-VN", { maximumFractionDigits: digits });
const mib = (value?: number) => value == null ? "—" : number(value / 1024 ** 2, 1) + " MiB";

export function MonitoringPage({ revision }: { revision: number }) {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [service, setService] = useState("");
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const value = await api<Snapshot>("/monitoring" + (service ? "?service=" + encodeURIComponent(service) : ""));
        if (alive) { setData(value); setError(""); }
      } catch (e) {
        if (alive) setError((e as Error).message);
      } finally {
        if (alive) timer = setTimeout(load, 15000);
      }
    }
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, [revision, service]);
  const logs = data?.logs.filter((entry) => !service || entry.service === service) || [];
  const total = (field: "cpu" | "memory") => {
    const values = data?.containers.filter((c) => c[field] != null);
    if (error) return null;
    return values?.length ? values.reduce((sum, c) => sum + (c[field] || 0), 0) : null;
  };
  return <div className="monitoring-page">
    <ErrorBox message={error} />
    {data && <ErrorBox message={data.errors.join(" ")} />}
    <div className="monitoring-toolbar">
      <span>{data ? "Cập nhật " + new Date(data.updated_at).toLocaleTimeString("vi-VN") + " · Tự làm mới mỗi 15 giây" : "Đang kết nối hệ thống giám sát…"}</span>
      {data && <a className="button primary" href={data.grafana_url} target="_blank" rel="noopener noreferrer">Mở Grafana <ExternalLink size={16} /></a>}
    </div>
    <div className="stats-grid">
      {[
        { title: "CPU các container", value: number(total("cpu")) + " %", icon: Cpu },
        { title: "RAM các container", value: total("memory") == null ? "—" : mib(total("memory")!), icon: MemoryStick },
        { title: "Request / giây", value: number(data?.requests_per_second), icon: Activity },
        { title: "Độ trễ p95", value: data?.latency_p95_seconds == null ? "—" : number(data.latency_p95_seconds * 1000) + " ms", icon: Timer },
      ].map((item) => <div className="monitoring-stat" key={item.title}><item.icon size={20} /><span>{item.title}</span><strong>{item.value}</strong></div>)}
    </div>
    <p className="monitoring-caption">100% CPU tương đương một vCPU. RAM không gồm cache có thể thu hồi. Đây là tài nguyên container trong Docker VM; không phải toàn bộ máy macOS.</p>
    <section className="monitoring-card">
      <div className="monitoring-section-title"><h2>Tài nguyên container</h2><span>Lỗi HTTP 5xx / giây: {number(data?.errors_per_second)}</span></div>
      <div className="monitoring-targets">{data?.targets.map((target) => <span key={target.job} className={target.up ? "monitoring-up" : "monitoring-down"}>{target.up ? "●" : "○"} {target.job}</span>)}</div>
      <div className="table-scroll"><table><thead><tr><th>Service</th><th>Container</th><th>CPU</th><th>RAM</th><th>Giới hạn RAM</th><th>Network nhận / gửi</th></tr></thead><tbody>
        {data?.containers.map((c) => <tr key={c.name}><td><strong>{c.service}</strong>{c.containers_up !== 1 && <small> · Mất metrics</small>}</td><td>{c.name}</td><td>{number(c.cpu)} %</td><td>{mib(c.memory)}</td><td>{mib(c.limit)}</td><td>{number(c.rx == null ? null : c.rx / 1024)} / {number(c.tx == null ? null : c.tx / 1024)} KiB/s</td></tr>)}
      </tbody></table></div>
      {data && !data.containers.length && <p className="monitoring-caption">Chưa có metrics. Kiểm tra Docker collector và Prometheus hoặc đợi lần thu thập tiếp theo.</p>}
    </section>
    <section className="monitoring-card">
      <div className="monitoring-section-title"><h2>Log gần nhất · 15 phút</h2><label>Service <select value={service} onChange={(e) => setService(e.target.value)}><option value="">Tất cả</option>{["api", "worker", "postgres", "ollama", "migrate"].map((s) => <option key={s}>{s}</option>)}</select></label></div>
      <div className="monitoring-logs" role="log" aria-label="Log hệ thống">
        {logs.map((entry) => <div className="monitoring-log" key={entry.timestamp + entry.service + entry.line}><time>{new Date(Number(BigInt(entry.timestamp) / 1000000n)).toLocaleTimeString("vi-VN")}</time><strong>{entry.service}</strong><code>{entry.line}</code></div>)}
        {!logs.length && <p>Chưa có log phù hợp. Mở Grafana để tìm trong khoảng thời gian khác.</p>}
      </div>
    </section>
  </div>;
}

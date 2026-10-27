import React, { useEffect, useRef, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";

type Provider = "gemini" | "embedding";
type Config = { models: { id: Provider; name: string; model: string; configured: boolean; dimensions?: number }[]; embedding_paused: boolean };
type Result = { model: string; status: "ok" | "error"; detail: string; latency_ms: number; checked_at: string; dimensions?: number; upstream_status?: number; http_status?: number };

export function AIHealthPage({ revision }: { revision: number }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [error, setError] = useState("");
  const [results, setResults] = useState<Partial<Record<Provider, Result>>>({});
  const [busy, setBusy] = useState<Partial<Record<Provider, boolean>>>({});
  const running = useRef(new Set<Provider>());
  useEffect(() => {
    let alive = true;
    api<Config>("/ai-health").then(value => { if (alive) { setConfig(value); setError(""); } })
      .catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [revision]);
  async function check(id: Provider) {
    if (running.current.has(id)) return;
    running.current.add(id);
    setBusy(value => ({ ...value, [id]: true }));
    setError("");
    try {
      const result = await api<Result>("/ai-health/" + id, "POST");
      setResults(value => ({ ...value, [id]: result }));
    } catch (e) { setError((e as Error).message); }
    finally {
      running.current.delete(id);
      setBusy(value => ({ ...value, [id]: false }));
    }
  }
  return <div>
    <ErrorBox message={error} />
    <p className="ai-health-note">Bấm kiểm tra để gửi một yêu cầu mẫu. Gemini có thể sử dụng quota API; trang không tự động gọi model.</p>
    {config?.embedding_paused && <div className="note">Worker đang tạm dừng nhận job mới. Model vẫn có thể hoạt động; vào Cài đặt để tiếp tục đồng bộ.</div>}
    {!config && !error && <p role="status">Đang tải cấu hình…</p>}
    <div className="ai-health-grid">{config?.models.map(model => {
      const result = results[model.id];
      return <section className="panel settings-panel" key={model.id}>
        <div className="panel-heading"><div><h3>{model.name}</h3><p>{model.id === "gemini" ? "Sinh câu trả lời và kiểm tra guardrail" : "Tạo vector qua Docker Ollama"}</p></div><Activity size={21} /></div>
        <div className="settings-body ai-health-body">
          <label>Model đang chạy<code>{model.model}</code></label>
          <p>{model.configured ? "Đã cấu hình" : "Chưa cấu hình GEMINI_API_KEY"}{model.dimensions ? ` · ${model.dimensions} chiều` : ""}</p>
          <button className="button primary" disabled={busy[model.id] || !model.configured} onClick={() => check(model.id)}><RefreshCw size={16} />{busy[model.id] ? "Đang kiểm tra…" : "Kiểm tra model"}</button>
          <div aria-live="polite" role="status" className="ai-health-result">
            {busy[model.id] ? <p>Đang chờ model phản hồi…</p> : result ? <>
              <strong>{result.status === "ok" ? "✓ Hoạt động" : "Không khả dụng"}</strong>
              <p>{result.detail}</p>
              <small>{result.latency_ms.toLocaleString("vi-VN")} ms · {new Date(result.checked_at).toLocaleString("vi-VN")}</small>
              {result.upstream_status && <p>HTTP upstream: {result.upstream_status}</p>}
              {result.dimensions && <p>Vector hợp lệ: {result.dimensions} chiều</p>}
            </> : <p>Chưa kiểm tra. Kết quả chỉ xác nhận khả năng phản hồi tại thời điểm kiểm tra.</p>}
          </div>
        </div>
      </section>;
    })}</div>
  </div>;
}

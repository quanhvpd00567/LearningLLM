import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { Activity, Check, Database, Package, ShieldCheck } from "lucide-react";
import type { Job, SiteSettings } from "../types";
import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";
export function SettingsPage({
  value,
  onSaved,
}: {
  value: SiteSettings;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
      shop_name: value.shop_name,
      contact_email: value.contact_email,
      low_stock_threshold: value.low_stock_threshold,
      embedding_paused: value.embedding_paused,
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const runtime = value.runtime;
  useEffect(
    () =>
      setForm({
        shop_name: value.shop_name,
        contact_email: value.contact_email,
        low_stock_threshold: value.low_stock_threshold,
        embedding_paused: value.embedding_paused,
      }),
    [value],
  );
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/settings", "PUT", form);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="settings-layout">
      <div>
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <h3>Thông tin cửa hàng</h3>
              <p>Những thông tin chung cho không gian quản trị.</p>
            </div>
            <Package size={21} />
          </div>
          <div className="settings-body">
            <label>
              Tên cửa hàng
              <input
                required
                maxLength={120}
                value={form.shop_name}
                onChange={(e) =>
                  setForm({ ...form, shop_name: e.target.value })
                }
              />
            </label>
            <label>
              Email liên hệ
              <input
                type="email"
                value={form.contact_email}
                onChange={(e) =>
                  setForm({ ...form, contact_email: e.target.value })
                }
                placeholder="support@example.com"
              />
            </label>
            <div className="form-row">
              <label>
                Ngưỡng cảnh báo tồn kho
                <input
                  type="number"
                  min={0}
                  max={10000}
                  step={1}
                  value={form.low_stock_threshold}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      low_stock_threshold: Number(e.target.value),
                    })
                  }
                />
                <small>
                  Cảnh báo biến thể có tồn kho nhỏ hơn hoặc bằng ngưỡng.
                </small>
              </label>
              <label>
                Đơn vị tiền tệ
                <input
                  readOnly
                  value="VND · Việt Nam Đồng"
                  className="readonly"
                />
              </label>
            </div>
          </div>
        </section>
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <h3>Đồng bộ dữ liệu</h3>
              <p>Điều khiển việc nhận job mới của embedding worker.</p>
            </div>
            <Activity size={21} />
          </div>
          <div className="settings-body">
            <label className="switch-row">
              <span>
                <strong>Tạm dừng embedding worker</strong>
                <small>
                  Job đang chạy vẫn hoàn tất; các job mới tiếp tục nằm trong
                  hàng đợi.
                </small>
              </span>
              <input
                className="switch"
                type="checkbox"
                role="switch"
                checked={form.embedding_paused}
                onChange={(e) =>
                  setForm({ ...form, embedding_paused: e.target.checked })
                }
              />
            </label>
          </div>
        </section>
        <ErrorBox message={error} />
        <div className="settings-actions">
          <span>Thay đổi chỉ có hiệu lực sau khi lưu.</span>
          <button className="button primary" disabled={busy}>
            {busy ? "Đang lưu…" : "Lưu cài đặt"}
            <Check size={16} />
          </button>
        </div>
      </div>
      <aside className="panel runtime-panel">
        <div className="panel-heading">
          <h3>
            <Database size={17} /> Cấu hình hệ thống
          </h3>
          <span className="readonly-badge">CHỈ ĐỌC</span>
        </div>
        <div className="runtime-body">
          <label>
            Embedding model<code>{runtime.embedding_model}</code>
          </label>
          <div className="runtime-grid">
            <label>
              Số chiều<strong>{runtime.embedding_dimensions}</strong>
            </label>
            <label>
              Pipeline<strong>v{runtime.pipeline_version}</strong>
            </label>
            <label>
              Batch size<strong>{runtime.batch_size}</strong>
            </label>
            <label>
              Chu kỳ quét<strong>{runtime.poll_seconds}s</strong>
            </label>
          </div>
          <label>
            Chat model hiện tại<code>{runtime.chat_model}</code>
          </label>
          <div className="note">
            <ShieldCheck size={17} />
            <p>
              Model và pipeline được quản lý qua cấu hình triển khai. Khi thay
              đổi cần tạo lại embedding.
            </p>
          </div>
        </div>
      </aside>
    </form>
  );
}

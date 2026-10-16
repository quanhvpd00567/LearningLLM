import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { FileText, Pencil, Search, Sparkles } from "lucide-react";
import type { Document, Page } from "../types";
import { api } from "../lib/api";
import { useRemote, useDebounce } from "../lib/hooks";
import { date } from "../lib/format";
import { ErrorBox, Empty, Pagination, Modal } from "../components/ui";
export function KnowledgePage({
  revision,
  onEdit,
}: {
  revision: number;
  onEdit: (d: Document) => void;
}) {
  const [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    query = useDebounce(q);
  useEffect(() => setPage(1), [query]);
  const { data, error } = useRemote<Page<Document>>(
    `/knowledge?q=${encodeURIComponent(query)}&page=${page}`,
    revision,
  );
  return (
    <section className="panel">
      <div className="list-toolbar">
        <div className="search-input">
          <Search size={17} />
          <input
            aria-label="Tìm tài liệu"
            placeholder="Tìm tài liệu, chính sách, FAQ…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <span className="result-count">{data?.total ?? "—"} tài liệu</span>
      </div>
      <ErrorBox message={error} />
      <div className="knowledge-list">
        {data?.items.map((d) => (
          <button
            className="knowledge-row"
            key={d.id}
            onClick={() => onEdit(d)}
          >
            <span className="document-icon">
              <FileText size={23} />
            </span>
            <div>
              <div>
                <h3>{d.title}</h3>
                <span
                  className={"simple-status " + (d.is_active ? "" : "muted")}
                >
                  <i />
                  {d.is_active ? "Đang sử dụng" : "Đã ẩn"}
                </span>
              </div>
              <p>{d.content}</p>
              <small>
                Phiên bản {d.source_version} · Cập nhật {date(d.updated_at)}
              </small>
            </div>
            <Pencil size={17} />
          </button>
        ))}
      </div>
      {data?.items.length === 0 && (
        <Empty
          text="Chưa tìm thấy tài liệu"
          hint="Thêm FAQ hoặc chính sách để xây dựng kho kiến thức."
        />
      )}
      <Pagination page={page} total={data?.total ?? 0} onChange={setPage} />
    </section>
  );
}
export function KnowledgeEditor({
  document: doc,
  onClose,
  onSaved,
}: {
  document: Document | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(doc?.title || ""),
    [content, setContent] = useState(doc?.content || ""),
    [active, setActive] = useState(doc?.is_active ?? true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(
        "/knowledge" + (doc ? "/" + doc.id : ""),
        doc ? "PUT" : "POST",
        {
          title,
          content,
          is_active: active,
          expected_version: doc?.source_version,
        },
      );
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={doc ? "Chỉnh sửa tài liệu" : "Thêm tài liệu kiến thức"}
      subtitle="Nội dung được đồng bộ tự động sau khi lưu."
      onClose={onClose}
      wide
      busy={busy}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <ErrorBox message={error} />
          <label>
            Tiêu đề
            <input
              autoFocus
              required
              maxLength={300}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ví dụ: Chính sách đổi trả"
            />
          </label>
          <label>
            Nội dung
            <textarea
              rows={12}
              required
              maxLength={100000}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Nhập nội dung rõ ràng, đầy đủ và có thể dùng để trả lời khách hàng…"
            />
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
            />
            Sử dụng tài liệu này
          </label>
        </div>
        <div className="modal-footer">
          <span>
            <Sparkles size={14} /> Tạo embedding khi nội dung thay đổi.
          </span>
          <div>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={onClose}
            >
              Hủy
            </button>
            <button className="button primary" disabled={busy}>
              {busy ? "Đang lưu…" : "Lưu tài liệu"}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

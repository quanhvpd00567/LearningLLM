import React, { type FormEvent, useEffect, useRef, useState } from "react";
import {
  CircleHelp,
  FileText,
  Package,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import type { Job, Overview, Page } from "../types";
import { useRemote } from "../lib/hooks";
import { date, statusNames } from "../lib/format";
import { Badge, ErrorBox, Empty, Pagination } from "../components/ui";
export function JobsPage({
  revision,
  stats,
  onRetry,
}: {
  revision: number;
  stats: Overview | null;
  onRetry: (id: string) => void;
}) {
  const [status, setStatus] = useState("all"),
    [page, setPage] = useState(1);
  useEffect(() => setPage(1), [status]);
  const { data, error, loading } = useRemote<Page<Job>>(
    `/jobs?status=${status}&page=${page}`,
    revision,
  );
  return (
    <>
      <div className="jobs-summary">
        {["pending", "processing", "completed", "failed"].map((s) => (
          <button
            key={s}
            className={"job-counter " + (status === s ? "selected" : "")}
            onClick={() => setStatus(status === s ? "all" : s)}
          >
            <Badge status={s} />
            <strong>{stats?.jobs[s] || 0}</strong>
          </button>
        ))}
      </div>
      <section className="panel">
        <div className="list-toolbar">
          <div>
            <h3>Hàng đợi embedding</h3>
            <p className="subtle">
              {stats?.embedding_paused
                ? "Worker đang tạm dừng nhận job mới."
                : "Worker tự động nhận và xử lý các job đến hạn."}
            </p>
          </div>
          <select
            aria-label="Lọc job"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">Tất cả trạng thái</option>
            {Object.entries(statusNames).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <ErrorBox message={error} />
        <div className="table-scroll">
          <table className="jobs-table">
            <thead>
              <tr>
                <th>NGUỒN DỮ LIỆU</th>
                <th>TRẠNG THÁI</th>
                <th>LẦN THỬ</th>
                <th>THỜI GIAN TẠO</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data?.items.map((j) => (
                <React.Fragment key={j.id}>
                  <tr>
                    <td>
                      <div className="job-title">
                        <span className="small-icon">
                          {j.source_type === "product" ? (
                            <Package size={18} />
                          ) : (
                            <FileText size={18} />
                          )}
                        </span>
                        <span>
                          <strong>{j.title}</strong>
                          <small>
                            {j.source_type === "product"
                              ? "Sản phẩm"
                              : "Tài liệu"}{" "}
                            · v{j.source_version} ·{" "}
                            {j.job_type === "embed_source"
                              ? "Tạo vector"
                              : "Xóa vector"}
                          </small>
                        </span>
                      </div>
                    </td>
                    <td>
                      <Badge status={j.status} />
                    </td>
                    <td>
                      {j.attempts} / {j.max_attempts}
                    </td>
                    <td>{date(j.created_at)}</td>
                    <td>
                      {j.status === "failed" && (
                        <button
                          className="button small"
                          onClick={() => onRetry(j.id)}
                        >
                          <RefreshCw size={14} />
                          Thử lại
                        </button>
                      )}
                    </td>
                  </tr>
                  {j.last_error && (
                    <tr className="job-error-row">
                      <td colSpan={5}>
                        <AlertCircle size={13} />
                        {j.last_error}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !data?.items.length && (
          <Empty
            text="Không có job trong trạng thái này"
            hint="Các thay đổi nội dung sẽ tự động tạo job mới."
          />
        )}
        <Pagination page={page} total={data?.total ?? 0} onChange={setPage} />
      </section>
      <div className="note">
        <CircleHelp size={16} />
        <p>
          Job của phiên bản cũ được bỏ qua. Giá và tồn kho thay đổi không cần
          tạo lại embedding.
        </p>
      </div>
    </>
  );
}

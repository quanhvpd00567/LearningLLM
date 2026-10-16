import React, { type FormEvent, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Database,
  FileText,
  Package,
  Sparkles,
  Boxes,
} from "lucide-react";
import type { View, Product, Job, Overview, Page } from "../types";
import { useRemote } from "../lib/hooks";
import { ErrorBox, Empty } from "../components/ui";
import { ProductTable } from "../components/ProductTable";
export function OverviewPage({
  stats,
  revision,
  onView,
  onEdit,
}: {
  stats: Overview | null;
  revision: number;
  onView: (v: View) => void;
  onEdit: (p: Product) => void;
}) {
  const { data, error } = useRemote<Page<Product>>(
    "/products?limit=5",
    revision,
  );
  const jobs = stats?.jobs || {},
    total =
      (jobs.completed || 0) +
      (jobs.pending || 0) +
      (jobs.processing || 0) +
      (jobs.failed || 0);
  return (
    <>
      <div className="welcome-strip">
        <div>
          <span className="mini-label">KHÔNG GIAN QUẢN TRỊ</span>
          <h2>
            Một ngày tốt để phát triển cửa hàng <span>✦</span>
          </h2>
          <p>Sản phẩm chỉn chu. Kiến thức đầy đủ. Dữ liệu luôn sẵn sàng.</p>
        </div>
        <div className="welcome-icon">
          <Boxes size={47} strokeWidth={1} />
          <span>
            <Sparkles size={18} />
          </span>
        </div>
      </div>
      <div className="stats-grid">
        {[
          {
            name: "Tổng sản phẩm",
            value: stats?.products,
            sub: `${stats?.active_products ?? 0} đang hiển thị`,
            icon: Package,
            color: "purple",
          },
          {
            name: "Tài liệu kiến thức",
            value: stats?.documents,
            sub: "FAQ, chính sách & hướng dẫn",
            icon: BookOpen,
            color: "blue",
          },
          {
            name: "Đoạn dữ liệu đã sẵn sàng",
            value: stats?.chunks,
            sub: "Vector thuộc model hiện tại",
            icon: Database,
            color: "green",
          },
          {
            name: "Biến thể tồn kho thấp",
            value: stats?.low_stock,
            sub: `Ngưỡng cảnh báo ≤ ${stats?.low_stock_threshold ?? 5}`,
            icon: Boxes,
            color: "orange",
          },
        ].map((c) => (
          <div className="stat-card" key={c.name}>
            <div className="stat-top">
              <span>{c.name}</span>
              <span className={"stat-icon " + c.color}>
                <c.icon size={19} />
              </span>
            </div>
            <strong>{c.value ?? "—"}</strong>
            <small>{c.sub}</small>
          </div>
        ))}
      </div>
      <div className="overview-middle">
        <section className="panel sync-panel">
          <div className="panel-heading">
            <div>
              <h3>
                <span className="heading-icon">
                  <Sparkles size={17} />
                </span>
                Đồng bộ kiến thức
              </h3>
              <p>Chuẩn bị dữ liệu cho trải nghiệm AI của cửa hàng.</p>
            </div>
            <span
              className={
                "badge " + (stats?.embedding_paused ? "pending" : "completed")
              }
            >
              <span />
              {stats?.embedding_paused ? "Đang tạm dừng" : "Worker được bật"}
            </span>
          </div>
          <div className="pipeline">
            <div>
              <span className="pipeline-icon">
                <FileText size={21} />
              </span>
              <strong>
                {(stats?.products ?? 0) + (stats?.documents ?? 0)}
              </strong>
              <small>Nguồn dữ liệu</small>
            </div>
            <ArrowRight size={17} />
            <div>
              <span className="pipeline-icon">
                <Activity size={21} />
              </span>
              <strong>{(jobs.pending || 0) + (jobs.processing || 0)}</strong>
              <small>Job đang chờ / chạy</small>
            </div>
            <ArrowRight size={17} />
            <div>
              <span className="pipeline-icon ready">
                <Database size={21} />
              </span>
              <strong>{stats?.chunks ?? 0}</strong>
              <small>Đoạn đã tạo vector</small>
            </div>
          </div>
          <div className="sync-bottom">
            <div className="progress-track">
              <i
                style={{
                  width: `${total ? ((jobs.completed || 0) / total) * 100 : 0}%`,
                }}
              />
            </div>
            <div>
              <span>
                {jobs.completed || 0} job hoàn tất · {jobs.failed || 0} lỗi
              </span>
              <button className="text-button" onClick={() => onView("jobs")}>
                Xem đồng bộ
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </section>
        <section className="quick-panel">
          <span className="mini-label">BƯỚC TIẾP THEO</span>
          <h3>
            Kiến thức tốt,
            <br />
            trải nghiệm tốt hơn.
          </h3>
          <p>
            Bổ sung chính sách giao hàng, đổi trả và hướng dẫn để chuẩn bị cho
            chatbot.
          </p>
          <button className="button" onClick={() => onView("knowledge")}>
            Quản lý kiến thức
            <ArrowRight size={15} />
          </button>
          <BookOpen className="quick-watermark" size={120} strokeWidth={0.7} />
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Sản phẩm cập nhật gần đây</h3>
            <p>Những thay đổi mới nhất trong catalog của bạn.</p>
          </div>
          <button className="text-button" onClick={() => onView("products")}>
            Tất cả sản phẩm
            <ArrowRight size={16} />
          </button>
        </div>
        <ErrorBox message={error} />
        {data?.items.length ? (
          <ProductTable items={data.items} onEdit={onEdit} compact />
        ) : (
          <Empty
            text="Catalog đang chờ bạn"
            hint="Thêm sản phẩm đầu tiên trong mục Sản phẩm."
          />
        )}
      </section>
    </>
  );
}

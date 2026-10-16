import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, X, AlertCircle, Boxes } from "lucide-react";
import { statusNames } from "../lib/format";
export function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>
      <span />
      {statusNames[status] || status}
    </span>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div role="alert" className="error-box">
      <AlertCircle size={17} />
      {message}
    </div>
  ) : null;
}
export function Empty({
  text = "Chưa có dữ liệu",
  hint = "Thêm nội dung đầu tiên để bắt đầu.",
}: {
  text?: string;
  hint?: string;
}) {
  return (
    <div className="empty">
      <Boxes size={34} />
      <h3>{text}</h3>
      <p>{hint}</p>
    </div>
  );
}
export function Pagination({
  page,
  total,
  onChange,
}: {
  page: number;
  total: number;
  onChange: (v: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / 12));
  return (
    <div className="pagination">
      <span>
        {total
          ? `${(page - 1) * 12 + 1}–${Math.min(page * 12, total)} trong ${total} kết quả`
          : "0 kết quả"}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Trang trước"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <span>
          Trang {page} / {pages}
        </span>
        <button
          className="icon-button"
          aria-label="Trang sau"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function Modal({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
  busy = false,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    ref.current?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) close.current();
      if (e.key === "Tab") {
        const focusable = ref.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),select,textarea,a[href]",
        );
        if (!focusable?.length) return;
        const first = focusable[0],
          last = focusable[focusable.length - 1];
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          last.focus();
          e.preventDefault();
        } else if (!e.shiftKey && document.activeElement === last) {
          first.focus();
          e.preventDefault();
        }
      }
    };
    document.addEventListener("keydown", handle);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handle);
      document.body.style.overflow = overflow;
      before?.focus();
    };
  }, [busy]);
  return (
    <div className="modal-backdrop">
      <div
        ref={ref}
        className={"modal " + (wide ? "wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <div className="modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button
            type="button"
            className="icon-button"
            disabled={busy}
            onClick={onClose}
            aria-label="Đóng"
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

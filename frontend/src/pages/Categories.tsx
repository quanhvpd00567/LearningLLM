import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { ArrowRight, Layers3, Pencil, Plus } from "lucide-react";
import type { Category } from "../types";
import { api } from "../lib/api";
import { ErrorBox, Modal } from "../components/ui";
export function CategoriesPage({
  items,
  onEdit,
  onCreate,
}: {
  items: Category[];
  onEdit: (c: Category) => void;
  onCreate: () => void;
}) {
  return (
    <div className="category-grid">
      {items.map((c, i) => (
        <div className="category-card" key={c.id}>
          <div>
            <span
              className={
                "stat-icon " + ["purple", "blue", "green", "orange"][i % 4]
              }
            >
              <Layers3 size={22} />
            </span>
            <button
              className="icon-button"
              aria-label={"Sửa danh mục " + c.name}
              onClick={() => onEdit(c)}
            >
              <Pencil size={16} />
            </button>
          </div>
          <h3>{c.name}</h3>
          <p>/{c.slug}</p>
          <footer>
            <span>{c.product_count} sản phẩm</span>
            <ArrowRight size={16} />
          </footer>
        </div>
      ))}
      <button className="category-card add-category" onClick={onCreate}>
        <span>
          <Plus size={25} />
        </span>
        <strong>Thêm danh mục</strong>
        <small>Sắp xếp catalog của bạn</small>
      </button>
    </div>
  );
}
export function CategoryEditor({
  category,
  onClose,
  onSaved,
}: {
  category: Category | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(category?.name || ""),
    [slug, setSlug] = useState(category?.slug || ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(
        "/categories" + (category ? "/" + category.id : ""),
        category ? "PUT" : "POST",
        { name, slug },
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
      title={category ? "Chỉnh sửa danh mục" : "Thêm danh mục"}
      subtitle="Tên danh mục giúp tổ chức và tìm kiếm sản phẩm."
      onClose={onClose}
      busy={busy}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <ErrorBox message={error} />
          <label>
            Tên danh mục
            <input
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Slug
            <input
              required
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              maxLength={120}
              placeholder="giay-di-bo"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            />
            <small>Chữ thường không dấu, số và dấu gạch ngang.</small>
          </label>
        </div>
        <div className="modal-footer">
          <span />
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
              {busy ? "Đang lưu…" : "Lưu danh mục"}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

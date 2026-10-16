import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { Check, Plus, Search, ShieldCheck, Trash2 } from "lucide-react";
import type { Variant, Product, Category, Page } from "../types";
import { api } from "../lib/api";
import { useRemote, useDebounce } from "../lib/hooks";
import { ErrorBox, Empty, Pagination, Modal } from "../components/ui";
import { ProductTable } from "../components/ProductTable";
export function ProductsPage({
  revision,
  onEdit,
  onCreate,
}: {
  revision: number;
  onEdit: (p: Product) => void;
  onCreate: () => void;
}) {
  const [q, setQ] = useState(""),
    [active, setActive] = useState("all"),
    [page, setPage] = useState(1);
  const query = useDebounce(q);
  useEffect(() => setPage(1), [query, active]);
  const { data, error, loading } = useRemote<Page<Product>>(
    `/products?q=${encodeURIComponent(query)}&active=${active}&page=${page}`,
    revision,
  );
  return (
    <section className="panel">
      <div className="list-toolbar">
        <div className="search-input">
          <Search size={17} />
          <input
            aria-label="Tìm sản phẩm"
            placeholder="Tìm sản phẩm theo tên…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="toolbar-right">
          <select
            aria-label="Lọc trạng thái"
            value={active}
            onChange={(e) => setActive(e.target.value)}
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="active">Đang hiển thị</option>
            <option value="inactive">Đã ẩn</option>
          </select>
          <span className="result-count">{data?.total ?? "—"} sản phẩm</span>
        </div>
      </div>
      <ErrorBox message={error} />
      {loading && !data ? (
        <div className="loading">Đang tải sản phẩm…</div>
      ) : data?.items.length ? (
        <ProductTable items={data.items} onEdit={onEdit} />
      ) : (
        <Empty
          text="Không có sản phẩm phù hợp"
          hint={
            q
              ? "Thử từ khóa khác hoặc đổi bộ lọc."
              : "Thêm sản phẩm để bắt đầu xây dựng catalog."
          }
        />
      )}
      <Pagination page={page} total={data?.total ?? 0} onChange={setPage} />
      {!loading && data?.total === 0 && !q && (
        <div className="empty-action">
          <button className="button primary" onClick={onCreate}>
            <Plus size={16} />
            Thêm sản phẩm
          </button>
        </div>
      )}
    </section>
  );
}
export function ProductEditor({
  product,
  categories,
  onClose,
  onSaved,
}: {
  product: Product | null;
  categories: Category[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(product?.name || ""),
    [description, setDescription] = useState(product?.description || ""),
    [category, setCategory] = useState(
      product?.category_id || categories[0]?.id || "",
    ),
    [active, setActive] = useState(product?.is_active ?? true),
    [attributes, setAttributes] = useState(
      JSON.stringify(product?.attributes || {}, null, 2),
    ),
    [variants, setVariants] = useState<Variant[]>(
      product?.variants.map((v) => ({ ...v, options: { ...v.options } })) || [],
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  function variantChange(index: number, values: Partial<Variant>) {
    setVariants((v) =>
      v.map((row, i) => (i === index ? { ...row, ...values } : row)),
    );
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    let parsed;
    try {
      parsed = JSON.parse(attributes);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
        throw Error();
    } catch {
      setError("Thuộc tính cần là một object JSON hợp lệ.");
      return;
    }
    setBusy(true);
    try {
      await api(
        "/products" + (product ? "/" + product.id : ""),
        product ? "PUT" : "POST",
        {
          name,
          description,
          category_id: category,
          is_active: active,
          attributes: parsed,
          expected_version: product?.source_version,
          variants: variants.map((v) => ({
            sku: v.sku,
            options: v.options,
            price: v.price,
            stock: Number(v.stock),
          })),
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
      title={product ? "Chỉnh sửa sản phẩm" : "Thêm sản phẩm"}
      subtitle="Thông tin thay đổi sẽ tự động được đưa vào hàng đợi đồng bộ."
      onClose={onClose}
      wide
      busy={busy}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <ErrorBox message={error} />
          <div className="section-label">THÔNG TIN CƠ BẢN</div>
          <label>
            Tên sản phẩm
            <input
              autoFocus
              required
              maxLength={300}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ví dụ: Giày đi bộ Daily Comfort"
            />
          </label>
          <div className="form-row">
            <label>
              Danh mục
              <select
                required
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="" disabled>
                  Chọn danh mục
                </option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Hiển thị
              <div className="check-field">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                />
                <span>Hiển thị sản phẩm</span>
              </div>
            </label>
          </div>
          <label>
            Mô tả sản phẩm
            <textarea
              required
              rows={4}
              maxLength={32000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Mô tả công dụng, chất liệu và điểm nổi bật…"
            />
          </label>
          <details className="attributes">
            <summary>Thuộc tính bổ sung</summary>
            <label>
              Thuộc tính sản phẩm (JSON)
              <textarea
                className="code-input"
                rows={5}
                value={attributes}
                onChange={(e) => setAttributes(e.target.value)}
              />
            </label>
          </details>
          <div className="section-label variant-heading">
            <span>BIẾN THỂ & TỒN KHO</span>
            <button
              type="button"
              className="text-button"
              onClick={() =>
                setVariants((v) => [
                  ...v,
                  {
                    sku: "",
                    options: { size: "", color: "" },
                    price: "0",
                    stock: 0,
                  },
                ])
              }
            >
              <Plus size={15} />
              Thêm biến thể
            </button>
          </div>
          {variants.length === 0 ? (
            <div className="inline-hint">
              Thêm SKU, size/màu, giá và tồn kho cho sản phẩm.
            </div>
          ) : (
            variants.map((v, i) => (
              <div className="variant-card" key={i}>
                <div className="variant-top">
                  <strong>Biến thể {i + 1}</strong>
                  <button
                    type="button"
                    className="icon-button danger-text"
                    aria-label={"Xóa biến thể " + (i + 1)}
                    onClick={() =>
                      setVariants((rows) => rows.filter((_, idx) => idx !== i))
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                <div className="variant-fields">
                  <label>
                    SKU
                    <input
                      required
                      pattern="[A-Za-z0-9_-]+"
                      maxLength={120}
                      value={v.sku}
                      onChange={(e) =>
                        variantChange(i, { sku: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Size
                    <input
                      value={String(v.options.size ?? "")}
                      onChange={(e) =>
                        variantChange(i, {
                          options: { ...v.options, size: e.target.value },
                        })
                      }
                    />
                  </label>
                  <label>
                    Màu sắc
                    <input
                      value={String(v.options.color ?? "")}
                      onChange={(e) =>
                        variantChange(i, {
                          options: { ...v.options, color: e.target.value },
                        })
                      }
                    />
                  </label>
                  <label>
                    Giá (VND)
                    <input
                      type="number"
                      required
                      min={0}
                      step={1}
                      value={v.price}
                      onChange={(e) =>
                        variantChange(i, { price: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Tồn kho
                    <input
                      type="number"
                      required
                      min={0}
                      step={1}
                      value={v.stock}
                      onChange={(e) =>
                        variantChange(i, { stock: Number(e.target.value) })
                      }
                    />
                  </label>
                </div>
              </div>
            ))
          )}
          {!categories.length && (
            <ErrorBox message="Cần tạo danh mục trước khi thêm sản phẩm." />
          )}
        </div>
        <div className="modal-footer">
          <span>
            <ShieldCheck size={14} /> Giá và tồn kho được cập nhật trực tiếp.
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
            <button
              className="button primary"
              disabled={busy || !categories.length}
            >
              {busy ? "Đang lưu…" : "Lưu sản phẩm"}
              <Check size={16} />
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

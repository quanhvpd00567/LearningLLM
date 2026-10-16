import React, { type FormEvent, useEffect, useRef, useState } from "react";
import { Footprints, Pencil } from "lucide-react";
import type { Product } from "../types";
import { money } from "../lib/format";
export function ProductAvatar({ index = 0 }: { index?: number }) {
  return (
    <span className={"product-avatar color-" + (index % 4)}>
      <Footprints size={24} strokeWidth={1.5} />
    </span>
  );
}
export function Stock({ product }: { product: Product }) {
  const stock = product.variants.reduce((s, v) => s + v.stock, 0);
  return (
    <span className={"stock " + (stock === 0 ? "zero" : "")}>
      <i />
      {stock === 0 ? "Hết hàng" : `${stock} sản phẩm`}
    </span>
  );
}
export function ProductTable({
  items,
  onEdit,
  compact = false,
}: {
  items: Product[];
  onEdit: (p: Product) => void;
  compact?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>SẢN PHẨM</th>
            <th>DANH MỤC</th>
            <th>GIÁ BÁN</th>
            <th>TỒN KHO</th>
            {!compact && <th>TRẠNG THÁI</th>}
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((p, i) => (
            <tr key={p.id}>
              <td>
                <button className="product-cell" onClick={() => onEdit(p)}>
                  <ProductAvatar index={i} />
                  <span>
                    <strong>{p.name}</strong>
                    <small>
                      {p.variants.length} biến thể · v{p.source_version}
                    </small>
                  </span>
                </button>
              </td>
              <td>
                <span className="category-tag">{p.category}</span>
              </td>
              <td className="price">
                {p.variants.length
                  ? money(Math.min(...p.variants.map((v) => Number(v.price))))
                  : "Chưa có giá"}
              </td>
              <td>
                <Stock product={p} />
              </td>
              {!compact && (
                <td>
                  <span
                    className={"simple-status " + (p.is_active ? "" : "muted")}
                  >
                    <i />
                    {p.is_active ? "Đang hiển thị" : "Đã ẩn"}
                  </span>
                </td>
              )}
              <td>
                <button
                  className="icon-button"
                  aria-label={"Sửa " + p.name}
                  onClick={() => onEdit(p)}
                >
                  <Pencil size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

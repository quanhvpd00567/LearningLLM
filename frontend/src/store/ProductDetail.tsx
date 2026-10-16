import { useState } from "react";
import { ArrowRight, Check, Package, ShieldCheck, Truck } from "lucide-react";
import { Product, image, money, options } from "./api";
import { ShopDialog } from "./ShopDialog";
export function ProductDetail({
  product,
  onClose,
  onAdd,
}: {
  product: Product;
  onClose: () => void;
  onAdd: (variant: string, quantity: number) => Promise<void>;
}) {
  const [selected, setSelected] = useState(
      product.variants.find((v) => v.stock > 0)?.id ||
        product.variants[0]?.id ||
        "",
    ),
    [quantity, setQuantity] = useState(1),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const variant = product.variants.find((v) => v.id === selected);
  async function add() {
    if (!variant) return;
    setBusy(true);
    setError("");
    try {
      await onAdd(variant.id, quantity);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <ShopDialog
      title="Chi tiết sản phẩm"
      wide
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="shop-product-detail">
        <div className="shop-detail-image">
          <img
            src={image(product.category_slug)}
            alt={"Ảnh minh họa " + product.name}
          />
          <span>Ảnh minh họa · Sản phẩm demo</span>
        </div>
        <div className="shop-detail-copy">
          <span className="shop-eyebrow">{product.category}</span>
          <h2>{product.name}</h2>
          <div className="shop-detail-price">
            {money(variant?.price || product.min_price)}
          </div>
          <p>{product.description}</p>
          <div className="shop-option-label">
            Chọn biến thể <span>{variant ? options(variant.options) : ""}</span>
          </div>
          <div className="shop-variants">
            {product.variants.map((v) => (
              <button
                key={v.id}
                className={selected === v.id ? "selected" : ""}
                disabled={v.stock === 0 || busy}
                onClick={() => {
                  setSelected(v.id);
                  setQuantity(1);
                }}
              >
                {options(v.options) || v.sku}
                {v.stock === 0 && <small>Hết hàng</small>}
              </button>
            ))}
          </div>
          <div className="shop-quantity-line">
            <label>
              Số lượng
              <input
                type="number"
                min={1}
                max={Math.min(20, variant?.stock || 1)}
                value={quantity}
                onChange={(e) =>
                  setQuantity(Math.max(1, Number(e.target.value)))
                }
              />
            </label>
            <span>
              {variant?.stock
                ? `${variant.stock} sản phẩm còn hàng`
                : "Hiện đã hết hàng"}
            </span>
          </div>
          {error && (
            <p className="shop-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="shop-button shop-primary full"
            onClick={add}
            disabled={
              busy ||
              !variant ||
              variant.stock === 0 ||
              quantity > variant.stock ||
              quantity > 20
            }
          >
            {busy ? "Đang thêm…" : "Thêm vào giỏ hàng"}
            <ArrowRight size={18} />
          </button>
          <div className="shop-detail-benefits">
            <span>
              <Truck size={16} />
              Giao hàng theo chính sách
            </span>
            <span>
              <ShieldCheck size={16} />
              Thanh toán khi nhận hàng
            </span>
          </div>
          <details className="shop-specs">
            <summary>Thông tin sản phẩm</summary>
            <dl>
              {Object.entries(product.attributes).map(([k, v]) => (
                <div key={k}>
                  <dt>
                    {(
                      {
                        purpose: "Mục đích",
                        material: "Chất liệu",
                        cushioning: "Độ đệm",
                        waterproof: "Chống nước",
                      } as Record<string, string>
                    )[k] || k}
                  </dt>
                  <dd>
                    {typeof v === "boolean"
                      ? v
                        ? "Có"
                        : "Không"
                      : typeof v === "object"
                        ? JSON.stringify(v)
                        : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
          </details>
        </div>
      </div>
    </ShopDialog>
  );
}

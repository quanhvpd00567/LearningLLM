import { type FormEvent, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Minus,
  Plus,
  ShoppingBag,
  Trash2,
  Truck,
} from "lucide-react";
import { Cart, Order, money, options, shopApi } from "./api";
import { ShopDialog } from "./ShopDialog";
export function CartPanel({
  cart,
  onClose,
  onUpdate,
  onPlaced,
  idempotencyKey,
}: {
  cart: Cart;
  onClose: () => void;
  onUpdate: (id: string, quantity: number) => Promise<void>;
  onPlaced: (order: Order) => void;
  idempotencyKey: string;
}) {
  const [checkout, setCheckout] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function change(id: string, quantity: number) {
    setBusy(true);
    setError("");
    try {
      await onUpdate(id, quantity);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const order = await shopApi<Order>("/checkout", "POST", {
        customer_name: data.get("customer_name"),
        phone: data.get("phone"),
        address: data.get("address"),
        note: data.get("note"),
        idempotency_key: idempotencyKey,
      });
      onPlaced(order);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const blocked = cart.items.some((i) => !i.available);
  return (
    <ShopDialog
      title={
        checkout
          ? "Thông tin nhận hàng"
          : `Giỏ hàng (${cart.items.reduce((n, i) => n + i.quantity, 0)})`
      }
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="shop-cart-body">
        {error && (
          <p className="shop-error" role="alert">
            {error}
          </p>
        )}
        {!cart.items.length ? (
          <div className="shop-empty">
            <ShoppingBag size={42} />
            <h3>Giỏ hàng đang chờ những bước chân mới</h3>
            <p>Khám phá bộ sưu tập và tìm một đôi giày dành cho bạn.</p>
            <button className="shop-button shop-primary" onClick={onClose}>
              Tiếp tục khám phá
              <ArrowRight size={16} />
            </button>
          </div>
        ) : (
          <>
            {checkout ? (
              <>
                <button
                  className="shop-text-button"
                  disabled={busy}
                  onClick={() => setCheckout(false)}
                >
                  <ArrowLeft size={15} />
                  Quay lại giỏ hàng
                </button>
                <form onSubmit={submit} id="shop-checkout-form">
                  <div className="shop-form-row">
                    <label>
                      Họ và tên
                      <input
                        name="customer_name"
                        autoComplete="name"
                        minLength={2}
                        maxLength={120}
                        required
                        placeholder="Nguyễn Minh An"
                        disabled={busy}
                      />
                    </label>
                    <label>
                      Số điện thoại
                      <input
                        name="phone"
                        type="tel"
                        autoComplete="tel"
                        minLength={8}
                        maxLength={20}
                        pattern="[+0-9 ()-]+"
                        required
                        placeholder="090 123 4567"
                        disabled={busy}
                      />
                    </label>
                  </div>
                  <label>
                    Địa chỉ nhận hàng
                    <textarea
                      name="address"
                      autoComplete="street-address"
                      required
                      minLength={10}
                      maxLength={500}
                      rows={3}
                      placeholder="Số nhà, đường, phường/xã, tỉnh/thành phố"
                      disabled={busy}
                    />
                  </label>
                  <label>
                    Ghi chú (không bắt buộc)
                    <textarea
                      name="note"
                      maxLength={500}
                      rows={2}
                      placeholder="Lưu ý cho đơn hàng của bạn"
                      disabled={busy}
                    />
                  </label>
                  <div className="shop-payment">
                    <CheckCircle2 size={20} />
                    <div>
                      <strong>Thanh toán khi nhận hàng (COD)</strong>
                      <p>
                        Đơn thử nghiệm trong cửa hàng demo, không phát sinh giao
                        dịch thực tế.
                      </p>
                    </div>
                  </div>
                </form>
              </>
            ) : (
              <div className="shop-cart-list">
                {cart.items.map((item) => (
                  <div key={item.variant_id} className="shop-cart-row">
                    <div className="shop-cart-item-icon">
                      <ShoppingBag size={24} />
                    </div>
                    <div>
                      <h3>{item.name}</h3>
                      <p>{options(item.options)}</p>
                      <strong>{money(item.price)}</strong>
                      {!item.available && (
                        <span className="shop-cart-warning">
                          Sản phẩm không còn đủ hàng. Vui lòng giảm số lượng
                          hoặc xóa.
                        </span>
                      )}
                      <div className="shop-cart-controls">
                        <button
                          aria-label={"Giảm " + item.name}
                          disabled={busy}
                          onClick={() =>
                            change(item.variant_id, item.quantity - 1)
                          }
                        >
                          <Minus size={13} />
                        </button>
                        <span>{item.quantity}</span>
                        <button
                          aria-label={"Tăng " + item.name}
                          disabled={
                            busy || item.quantity >= Math.min(20, item.stock)
                          }
                          onClick={() =>
                            change(item.variant_id, item.quantity + 1)
                          }
                        >
                          <Plus size={13} />
                        </button>
                        <button
                          className="remove"
                          aria-label={"Xóa " + item.name + " khỏi giỏ"}
                          disabled={busy}
                          onClick={() => change(item.variant_id, 0)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <strong>{money(item.line_total)}</strong>
                  </div>
                ))}
              </div>
            )}
            <div className="shop-cart-totals">
              <div>
                <span>Tạm tính</span>
                <strong>{money(cart.subtotal)}</strong>
              </div>
              <div>
                <span>Phí giao hàng</span>
                <span>{money(cart.shipping_fee)}</span>
              </div>
              <div className="grand-total">
                <span>Tổng cộng</span>
                <strong>{money(cart.total)}</strong>
              </div>
            </div>
            <p className="shop-cart-note">
              <Truck size={15} />
              Giá và tồn kho được kiểm tra lại khi xác nhận đặt hàng.
            </p>
          </>
        )}
      </div>
      {cart.items.length > 0 && (
        <div className="shop-cart-footer">
          {checkout ? (
            <button
              type="submit"
              form="shop-checkout-form"
              disabled={busy || blocked}
              className="shop-button shop-primary full"
            >
              {busy ? "Đang tạo đơn…" : "Xác nhận đặt đơn COD"}
              <ArrowRight size={17} />
            </button>
          ) : (
            <button
              disabled={busy || blocked}
              className="shop-button shop-primary full"
              onClick={() => {
                setCheckout(true);
                setError("");
              }}
            >
              Tiến hành đặt hàng
              <ArrowRight size={17} />
            </button>
          )}
        </div>
      )}
    </ShopDialog>
  );
}

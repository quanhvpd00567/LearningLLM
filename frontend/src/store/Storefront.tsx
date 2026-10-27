import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Footprints,
  Leaf,
  Menu,
  MessageCircle,
  Package,
  ReceiptText,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Truck,
  X,
  UserRound,
} from "lucide-react";
import { useDebounce } from "../lib/hooks";
import {
  Cart,
  Category,
  Order,
  Policy,
  Product,
  ShopConfig,
  image,
  money,
  options,
  orderStatus,
  shopApi,
} from "./api";
import { ShopDialog } from "./ShopDialog";
import { ProductDetail } from "./ProductDetail";
import { CartPanel } from "./CartPanel";
import { ChatBox } from "./ChatBox";
import { signIn, useCustomer } from "./CustomerSession";
const emptyCart: Cart = {
  items: [],
  subtotal: "0",
  shipping_fee: "0",
  total: "0",
};
function ProductCard({
  product,
  onOpen,
}: {
  product: Product;
  onOpen: (p: Product) => void;
}) {
  return (
    <article className="shop-product-card">
      <button
        className="shop-product-photo"
        onClick={() => onOpen(product)}
        aria-label={"Xem " + product.name}
      >
        <img
          src={image(product.category_slug)}
          alt={"Ảnh minh họa " + product.name}
          loading="lazy"
        />
        {product.stock === 0 ? (
          <span className="shop-sold-out">Tạm hết hàng</span>
        ) : (
          <span className="shop-product-category">{product.category}</span>
        )}
        <span className="shop-quick-view">
          <PlusIcon />
          Xem chi tiết
        </span>
      </button>
      <div className="shop-card-info">
        <span>{String(product.attributes.purpose || product.category)}</span>
        <button onClick={() => onOpen(product)}>{product.name}</button>
        <div>
          <strong>{money(product.min_price)}</strong>
          <button
            className="shop-product-arrow"
            aria-label={"Chọn biến thể " + product.name}
            onClick={() => onOpen(product)}
          >
            <ArrowUpRight size={19} />
          </button>
        </div>
        <small>
          {product.variants.length} biến thể ·{" "}
          {product.stock > 0 ? "Còn hàng" : "Hết hàng"}
        </small>
      </div>
    </article>
  );
}
function PlusIcon() {
  return <span>＋</span>;
}
export function Storefront() {
  const { user, error: sessionError, refresh: refreshSession } = useCustomer();
  const [config, setConfig] = useState<ShopConfig | null>(null),
    [categories, setCategories] = useState<Category[]>([]),
    [policies, setPolicies] = useState<Policy[]>([]),
    [products, setProducts] = useState<Product[]>([]),
    [total, setTotal] = useState(0),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [q, setQ] = useState(""),
    [category, setCategory] = useState(""),
    [sort, setSort] = useState("latest"),
    [budget, setBudget] = useState(""),
    [stockOnly, setStockOnly] = useState(false),
    [page, setPage] = useState(1),
    [revision, setRevision] = useState(0),
    [detail, setDetail] = useState<Product | null>(null),
    [cart, setCart] = useState<Cart>(emptyCart),
    [cartOpen, setCartOpen] = useState(() => !!user && new URLSearchParams(location.search).get("cart") === "1"),
    [receipt, setReceipt] = useState<Order | null>(null),
    [orders, setOrders] = useState<Order[]>([]),
    [ordersOpen, setOrdersOpen] = useState(false),
    [ordersLoading, setOrdersLoading] = useState(false),
    [ordersError, setOrdersError] = useState(""),
    [policy, setPolicy] = useState<Policy | null>(null),
    [policyListOpen, setPolicyListOpen] = useState(false),
    [chatOpen, setChatOpen] = useState(() => new URLSearchParams(location.search).get("chat") === "1"),
    [toast, setToast] = useState(""),
    [mobile, setMobile] = useState(false),
    [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const search = useDebounce(q),
    collection = useRef<HTMLElement>(null),
    searchField = useRef<HTMLInputElement>(null),
    name = config?.shop_name || "Commerce Lab";
  useEffect(() => {
    document.title = name + " · Nhẹ bước mỗi ngày";
  }, [name]);
  useEffect(() => {
    Promise.all([
      shopApi<ShopConfig>("/config"),
      shopApi<Category[]>("/categories"),
      shopApi<Cart>("/cart"),
      shopApi<Policy[]>("/knowledge"),
    ])
      .then(([a, b, c, d]) => {
        setConfig(a);
        setCategories(b);
        setCart(c);
        setPolicies(d);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => setPage(1), [search, category, sort, budget, stockOnly]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({
      q: search,
      category,
      sort,
      page: String(page),
      limit: "12",
      in_stock: String(stockOnly),
    });
    if (budget) params.set("max_price", budget);
    shopApi<{ items: Product[]; total: number }>("/products?" + params)
      .then((result) => {
        if (alive) {
          setProducts(result.items);
          setTotal(result.total);
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [search, category, sort, budget, stockOnly, page, revision]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function openProduct(p: Product) {
    try {
      setDetail(await shopApi<Product>("/products/" + p.id));
    } catch (e) {
      setToast((e as Error).message);
    }
  }
  async function updateCart(id: string, quantity: number) {
    const next = await shopApi<Cart>("/cart/items/" + id, "PUT", { quantity });
    setCart(next);
    setIdempotencyKey(crypto.randomUUID());
  }
  async function addCart(id: string, quantity: number) {
    if (!user) { signIn("cart"); return; }
    await updateCart(
      id,
      (cart.items.find((i) => i.variant_id === id)?.quantity || 0) + quantity,
    );
    setToast("Đã thêm vào giỏ hàng. Sẵn sàng cho bước chân mới!");
  }
  async function showCart() {
    if (!user) { signIn("cart"); return; }
    try {
      setCart(await shopApi<Cart>("/cart"));
      setCartOpen(true);
    } catch (e) {
      setToast((e as Error).message);
    }
  }
  async function showOrders() {
    if (!user) { signIn(); return; }
    setOrdersOpen(true);
    setOrdersLoading(true);
    setOrdersError("");
    try {
      setOrders(await shopApi<Order[]>("/orders"));
    } catch (e) {
      setOrdersError((e as Error).message);
    } finally {
      setOrdersLoading(false);
    }
  }
  function browse(slug = "") {
    setCategory(slug);
    setMobile(false);
    collection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function showPolicy(id: string) {
    const value = policies.find((p) => p.id === id);
    if (value) setPolicy(value);
    else setPolicyListOpen(true);
  }
  function placed(order: Order) {
    setCart(emptyCart);
    setCartOpen(false);
    setReceipt(order);
    setIdempotencyKey(crypto.randomUUID());
    setRevision((v) => v + 1);
  }
  const count = cart.items.reduce((n, i) => n + i.quantity, 0),
    pages = Math.max(1, Math.ceil(total / 12));
  return (
    <div className="shop">
      <div className="shop-announcement">
        <span>CỬA HÀNG DEMO</span>
        <p>
          Trải nghiệm mua sắm thử nghiệm · Không phát sinh giao dịch thực tế
        </p>
        <ArrowUpRight size={13} />
      </div>
      <header className="shop-header">
        <a className="shop-wordmark" href="/" aria-label={name + " trang chủ"}>
          <Footprints size={29} strokeWidth={1.5} />
          <span>
            {name}
            <small>EVERYDAY MOVEMENT</small>
          </span>
        </a>
        <nav className={mobile ? "open" : ""} aria-label="Điều hướng cửa hàng">
          <button onClick={() => browse()}>Bộ sưu tập</button>
          <button
            className={category === "walking" ? "active" : ""}
            onClick={() => browse("walking")}
          >
            Giày đi bộ
          </button>
          <button
            className={category === "running" ? "active" : ""}
            onClick={() => browse("running")}
          >
            Giày chạy bộ
          </button>
          <button
            onClick={() => {
              setPolicyListOpen(true);
              setMobile(false);
            }}
          >
            Chính sách
          </button>
        </nav>
        <div className="shop-header-actions">
          <button
            className="shop-icon-button"
            aria-label="Tìm sản phẩm"
            onClick={() => {
              browse(category);
              searchField.current?.focus({ preventScroll: true });
            }}
          >
            <Search size={20} />
          </button>
          <a className="shop-icon-button customer-account-link" href={user ? "/account" : "/login"} aria-label={user ? "Tài khoản của bạn" : "Đăng nhập / Đăng ký"} title={user ? user.name : "Đăng nhập / Đăng ký"}><UserRound size={20} /><span className="customer-header-label">{user ? "Tài khoản" : "Đăng nhập"}</span></a>
          <button
            className="shop-icon-button"
            aria-label="Đơn hàng của bạn"
            onClick={showOrders}
          >
            <ReceiptText size={20} />
          </button>
          <button
            className="shop-bag-button"
            aria-label={"Mở giỏ hàng, " + count + " sản phẩm"}
            onClick={showCart}
          >
            <ShoppingBag size={20} />
            <span>{count}</span>
          </button>
          <button
            className="shop-icon-button shop-menu-toggle"
            aria-label={mobile ? "Đóng menu cửa hàng" : "Mở menu cửa hàng"}
            onClick={() => setMobile((v) => !v)}
          >
            {mobile ? <X size={21} /> : <Menu size={21} />}
          </button>
        </div>
      </header>
      <main>
        {sessionError && <div className="shop-error" role="alert">{sessionError}<button onClick={refreshSession}>Thử lại</button></div>}
        <section className="shop-hero">
          <div className="shop-hero-copy">
            <span className="shop-eyebrow">
              <i /> DÀNH CHO NHỮNG BƯỚC CHÂN MỚI
            </span>
            <h1>
              Đi nhẹ hơn.
              <br />
              <em>Sống trọn hơn.</em>
            </h1>
            <p>
              Một đôi giày phù hợp, thêm nhiều điều muốn khám phá. Tìm bạn đồng
              hành cho nhịp sống mỗi ngày của bạn.
            </p>
            <div className="shop-hero-actions">
              <button
                className="shop-button shop-primary"
                onClick={() => browse()}
              >
                Khám phá bộ sưu tập
                <ArrowUpRight size={17} />
              </button>
              <button
                className="shop-hero-chat"
                onClick={() => setChatOpen(true)}
              >
                <span>
                  <Sparkles size={17} />
                </span>
                Để mình giúp bạn chọn
              </button>
            </div>
            <div className="shop-hero-footnote">
              <span>
                <Leaf size={15} />
                Thoải mái theo cách của bạn
              </span>
              <span>Everyday. Every step.</span>
            </div>
          </div>
          <div className="shop-hero-visual">
            <span className="shop-hero-outline">EVERYDAY</span>
            <img
              src="/images/walking-studio.png"
              alt="Ảnh minh họa đôi giày đi bộ màu kem trên nền đá sáng"
              fetchPriority="high"
            />
            <div className="shop-hero-product-label">
              <span className="shop-tiny-dot" />
              <div>
                <strong>Everyday essentials</strong>
                <span>Nhẹ nhàng, từ những điều đơn giản.</span>
              </div>
              <ArrowUpRight size={20} />
            </div>
            <div className="shop-hero-index">
              <span>01 / DAILY MOVEMENT</span>
              <span>Ảnh minh họa</span>
            </div>
          </div>
        </section>
        <section className="shop-service-strip" aria-label="Dịch vụ cửa hàng">
          <div>
            <Truck size={22} strokeWidth={1.4} />
            <span>
              <strong>Giao hàng tận nơi</strong>
              <small>
                Phí giao hàng {money(config?.shipping_fee ?? 30000)}
              </small>
            </span>
          </div>
          <div>
            <ShieldCheck size={22} strokeWidth={1.4} />
            <span>
              <strong>Thanh toán khi nhận</strong>
              <small>Đặt đơn COD đơn giản</small>
            </span>
          </div>
          <div>
            <Package size={22} strokeWidth={1.4} />
            <span>
              <strong>Chính sách rõ ràng</strong>
              <small>
                <button onClick={() => setPolicyListOpen(true)}>
                  Xem hướng dẫn giao hàng & đổi trả
                </button>
              </small>
            </span>
          </div>
          <div>
            <MessageCircle size={22} strokeWidth={1.4} />
            <span>
              <strong>Luôn có người đồng hành</strong>
              <small>
                <button onClick={() => setChatOpen(true)}>
                  Hỏi trợ lý để chọn giày phù hợp
                </button>
              </small>
            </span>
          </div>
        </section>
        <section className="shop-collection" ref={collection} id="collection">
          <div className="shop-section-title">
            <div>
              <span className="shop-eyebrow">TÌM NHỊP ĐI CỦA RIÊNG BẠN</span>
              <h2>
                Một đôi giày. <em>Nhiều hành trình.</em>
              </h2>
              <p>
                Từ những bước đi thường ngày đến cung đường bạn chưa từng thử.
              </p>
            </div>
            <span className="shop-collection-count">
              {total} sản phẩm
              <ArrowDown size={15} />
            </span>
          </div>
          <div className="shop-category-tabs" aria-label="Danh mục sản phẩm">
            <button
              className={!category ? "selected" : ""}
              onClick={() => setCategory("")}
            >
              Tất cả sản phẩm
              <span>{categories.reduce((n, c) => n + c.count, 0)}</span>
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                className={category === c.slug ? "selected" : ""}
                onClick={() => setCategory(c.slug)}
              >
                {c.name}
                <span>{c.count}</span>
              </button>
            ))}
          </div>
          <div className="shop-filters">
            <div className="shop-search">
              <Search size={17} />
              <input
                ref={searchField}
                aria-label="Tìm kiếm sản phẩm"
                placeholder="Tìm một đôi giày dành cho bạn…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              {q && (
                <button aria-label="Xóa tìm kiếm" onClick={() => setQ("")}>
                  <X size={15} />
                </button>
              )}
            </div>
            <div>
              <label className="shop-stock-filter">
                <input
                  type="checkbox"
                  checked={stockOnly}
                  onChange={(e) => setStockOnly(e.target.checked)}
                />
                Chỉ còn hàng
              </label>
              <select
                aria-label="Lọc theo ngân sách"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              >
                <option value="">Mọi mức giá</option>
                <option value="500000">Đến 500.000 đ</option>
                <option value="800000">Đến 800.000 đ</option>
                <option value="1000000">Đến 1.000.000 đ</option>
              </select>
              <select
                aria-label="Sắp xếp sản phẩm"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                <option value="latest">Mới cập nhật</option>
                <option value="price_asc">Giá: thấp đến cao</option>
                <option value="price_desc">Giá: cao đến thấp</option>
              </select>
            </div>
          </div>
          {error && (
            <div className="shop-error" role="alert">
              {error}
              <button onClick={() => setRevision((v) => v + 1)}>Thử lại</button>
            </div>
          )}
          {loading && !products.length ? (
            <div className="shop-empty">
              Đang tìm những đôi giày dành cho bạn…
            </div>
          ) : products.length ? (
            <div
              className={"shop-product-grid " + (loading ? "is-loading" : "")}
            >
              {products.map((p) => (
                <ProductCard key={p.id} product={p} onOpen={openProduct} />
              ))}
            </div>
          ) : (
            !error && (
              <div className="shop-empty">
                <Search size={34} />
                <h3>Chưa tìm thấy đôi giày phù hợp</h3>
                <p>Thử đổi từ khóa, mức giá hoặc để trợ lý giúp bạn nhé.</p>
                <button
                  className="shop-button"
                  onClick={() => {
                    setQ("");
                    setCategory("");
                    setBudget("");
                    setStockOnly(false);
                  }}
                >
                  Xóa bộ lọc
                </button>
              </div>
            )
          )}
          <div className="shop-catalog-footer">
            <span>Ảnh minh họa AI · Catalog sản phẩm demo</span>
            <div className="shop-pagination">
              <button
                aria-label="Trang sản phẩm trước"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                Trang {page} / {pages}
              </span>
              <button
                aria-label="Trang sản phẩm tiếp"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
        </section>
        <section className="shop-assistant-banner">
          <div className="shop-banner-symbol">
            <Sparkles size={33} strokeWidth={1.2} />
          </div>
          <div>
            <span className="shop-eyebrow">
              MỘT CHÚT GỢI Ý, MỘT LỰA CHỌN TỐT HƠN
            </span>
            <h2>Chưa biết bắt đầu từ đâu?</h2>
            <p>
              Kể về nhu cầu của bạn. Trợ lý sẽ tìm sản phẩm và thông tin phù hợp
              trong cửa hàng.
            </p>
          </div>
          <button
            className="shop-button shop-primary"
            onClick={() => setChatOpen(true)}
          >
            Trò chuyện cùng trợ lý
            <ArrowUpRight size={17} />
          </button>
        </section>
      </main>
      <footer className="shop-footer">
        <div className="shop-footer-top">
          <div>
            <a className="shop-wordmark" href="/">
              <Footprints size={28} strokeWidth={1.5} />
              <span>
                {name}
                <small>EVERYDAY MOVEMENT</small>
              </span>
            </a>
            <p>
              Những lựa chọn nhỏ.
              <br />
              Cho một ngày trọn vẹn hơn.
            </p>
          </div>
          <div>
            <h3>Khám phá</h3>
            <button onClick={() => browse()}>Tất cả sản phẩm</button>
            <button onClick={() => browse("walking")}>Giày đi bộ</button>
            <button onClick={() => browse("running")}>Giày chạy bộ</button>
          </div>
          <div>
            <h3>Thông tin hữu ích</h3>
            {policies.slice(0, 4).map((p) => (
              <button key={p.id} onClick={() => setPolicy(p)}>
                {p.title}
              </button>
            ))}
          </div>
          <div>
            <h3>Cần một người đồng hành?</h3>
            <p>
              Hỏi về sản phẩm, cách chọn size
              <br />
              hay chính sách mua sắm.
            </p>
            <button
              className="shop-footer-chat"
              onClick={() => setChatOpen(true)}
            >
              Hỏi trợ lý mua sắm
              <ArrowUpRight size={15} />
            </button>
            {config?.contact_email && (
              <a href={"mailto:" + config.contact_email}>
                {config.contact_email}
              </a>
            )}
          </div>
        </div>
        <div className="shop-footer-bottom">
          <span>
            © {new Date().getFullYear()} {name}. Cửa hàng demo phục vụ học tập.
          </span>
          <span>
            Đơn thử nghiệm · Thanh toán COD
            <a href="/admin/">
              Quản trị
              <ArrowUpRight size={12} />
            </a>
          </span>
        </div>
      </footer>
      {detail && (
        <ProductDetail
          key={detail.id}
          product={detail}
          onClose={() => setDetail(null)}
          onAdd={addCart}
        />
      )}
      {cartOpen && (
        <CartPanel
          cart={cart}
          onClose={() => setCartOpen(false)}
          onUpdate={updateCart}
          onPlaced={placed}
          idempotencyKey={idempotencyKey}
        />
      )}
      {receipt && (
        <ShopDialog title="Đơn hàng của bạn" onClose={() => setReceipt(null)}>
          <div className="shop-receipt">
            <span className="shop-receipt-check">
              <CheckCircle2 size={34} />
            </span>
            <span className="shop-eyebrow">ĐÃ GHI NHẬN ĐƠN THỬ NGHIỆM</span>
            <h2>Cảm ơn bạn đã ghé cửa hàng.</h2>
            <p>
              Đơn <strong>{receipt.code}</strong> ·{" "}
              {orderStatus[receipt.status] || receipt.status}
            </p>
            <div className="shop-receipt-items">
              {receipt.items.map((i, index) => (
                <div key={index}>
                  <span>
                    <strong>{i.name}</strong>
                    <small>
                      {options(i.options)} · SL {i.quantity}
                    </small>
                  </span>
                  <strong>{money(Number(i.unit_price) * i.quantity)}</strong>
                </div>
              ))}
            </div>
            <div className="shop-cart-totals">
              <div>
                <span>Phí giao hàng</span>
                <span>{money(receipt.shipping_fee)}</span>
              </div>
              <div className="grand-total">
                <span>Tổng COD</span>
                <strong>{money(receipt.total)}</strong>
              </div>
            </div>
            <div className="shop-receipt-address">
              <strong>
                {receipt.customer_name} · {receipt.phone}
              </strong>
              <p>{receipt.address}</p>
            </div>
            <small>
              Đây là đơn demo, không phát sinh giao dịch hoặc giao hàng thực tế.
            </small>
            <button
              className="shop-button shop-primary full"
              onClick={() => setReceipt(null)}
            >
              Tiếp tục khám phá
              <ArrowRight size={17} />
            </button>
          </div>
        </ShopDialog>
      )}
      {ordersOpen && (
        <ShopDialog
          title="Đơn hàng trong tài khoản của bạn"
          onClose={() => setOrdersOpen(false)}
        >
          <div className="shop-orders">
            {ordersLoading ? (
              <p>Đang tải đơn hàng…</p>
            ) : ordersError ? (
              <p className="shop-error">{ordersError}</p>
            ) : orders.length ? (
              orders.map((o) => (
                <button
                  key={o.id}
                  onClick={() => {
                    setOrdersOpen(false);
                    setReceipt(o);
                  }}
                >
                  <span>
                    <strong>{o.code}</strong>
                    <small>
                      {new Date(o.created_at).toLocaleString("vi-VN")} ·{" "}
                      {o.items.length} sản phẩm
                    </small>
                    <i>{orderStatus[o.status] || o.status}</i>
                  </span>
                  <strong>
                    {money(o.total)}
                    <ArrowUpRight size={15} />
                  </strong>
                </button>
              ))
            ) : (
              <div className="shop-empty">
                <ReceiptText size={35} />
                <h3>Bạn chưa có đơn hàng</h3>
                <p>
                  Đơn hàng mới sẽ được lưu vào tài khoản của bạn.
                </p>
              </div>
            )}
          </div>
        </ShopDialog>
      )}
      {policyListOpen && (
        <ShopDialog
          title="Thông tin & chính sách"
          onClose={() => setPolicyListOpen(false)}
        >
          <div className="shop-policy-list">
            {policies.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPolicyListOpen(false);
                  setPolicy(p);
                }}
              >
                {p.title}
                <ArrowUpRight size={17} />
              </button>
            ))}
            {policies.length === 0 && (
              <p>Thông tin đang được cập nhật. Bạn vui lòng thử lại sau.</p>
            )}
          </div>
        </ShopDialog>
      )}
      {policy && (
        <ShopDialog title={policy.title} onClose={() => setPolicy(null)}>
          <div className="shop-policy-content">
            {policy.content}
            <small>Thông tin từ kho kiến thức của cửa hàng demo.</small>
          </div>
        </ShopDialog>
      )}
      <ChatBox
        open={chatOpen}
        onToggle={() => setChatOpen((v) => !v)}
        onProduct={openProduct}
        onPolicy={showPolicy}
      />
      {toast && (
        <div className="shop-toast" role="status">
          <CheckCircle2 size={18} />
          {toast}
          <button aria-label="Đóng thông báo" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}

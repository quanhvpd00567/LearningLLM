import { useEffect, useState } from "react";
import { ArrowLeft, LogOut, MessageCircle, Package, RefreshCw } from "lucide-react";
import { Order, money, options, orderStatus, shopApi } from "./api";
import { notifyCustomerChange, signIn, useCustomer } from "./CustomerSession";

export function CustomerAccount() {
  const { user, loading, error: sessionError, refresh } = useCustomer();
  const [orders, setOrders] = useState<Order[]>([]);
  const [busy, setBusy] = useState(true);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => { if (!loading && !user && !sessionError) signIn(); }, [loading, user, sessionError]);
  useEffect(() => {
    if (!user) return;
    let alive = true;
    setBusy(true); setError("");
    shopApi<Order[]>("/orders").then(value => { if (alive) setOrders(value); })
      .catch(e => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setBusy(false); });
    return () => { alive = false; };
  }, [user?.id, revision]);
  async function logout() {
    setSigningOut(true);
    try { await shopApi("/auth/logout", "POST"); notifyCustomerChange(); location.replace("/"); }
    catch (e) { setError((e as Error).message); setSigningOut(false); }
  }
  return <div className="shop customer-account-page">
    <header className="customer-account-header"><a href="/"><ArrowLeft size={17} /> Về cửa hàng</a>{user && <button className="shop-button" disabled={signingOut} onClick={logout}><LogOut size={16} />Đăng xuất</button>}</header>
    <main className="customer-account-main">
      {sessionError ? <div className="shop-error" role="alert">{sessionError}<button onClick={refresh}>Thử lại</button></div> : !user ? <p>Đang kiểm tra phiên đăng nhập…</p> : <>
        <span className="shop-eyebrow">TÀI KHOẢN CỦA BẠN</span>
        <h1>Chào {user.name}.</h1><p>{user.email}</p>
        <a className="shop-button shop-primary" href="/?chat=1"><MessageCircle size={18} />Trò chuyện cùng trợ lý</a>
        <section className="customer-orders-heading"><div><h2>Đơn hàng của tôi</h2><p>Tối đa 30 đơn gần nhất của tài khoản.</p></div><button className="shop-button" disabled={busy} onClick={() => setRevision(v => v + 1)}><RefreshCw size={16} />Làm mới</button></section>
        {error && <p className="shop-error" role="alert">{error}</p>}
        {busy ? <p role="status">Đang tải đơn hàng…</p> : !error && !orders.length ? <div className="shop-empty"><Package size={32} /><h3>Bạn chưa có đơn hàng</h3><a className="shop-button" href="/">Khám phá sản phẩm</a></div> : <div className="customer-orders">{orders.map(order => <article className="customer-order" key={order.id}>
          <header><div><h3>{order.code}</h3><small>{new Date(order.created_at).toLocaleString("vi-VN")}</small></div><strong>{orderStatus[order.status] || order.status}</strong></header>
          <div className="customer-order-items">{order.items.map((item, index) => <div key={index}><span>{item.name}<small>{options(item.options)} · SL {item.quantity}</small></span><strong>{money(Number(item.unit_price) * item.quantity)}</strong></div>)}</div>
          <div className="customer-order-total"><span>Tổng COD · đã gồm phí giao hàng</span><strong>{money(order.total)}</strong></div>
          <p>{order.customer_name} · {order.phone}</p><p>{order.address}</p>
        </article>)}</div>}
      </>}
    </main>
  </div>;
}

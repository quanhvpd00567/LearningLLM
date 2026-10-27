import { useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, Eye, EyeOff, Footprints, LockKeyhole, Mail, ShieldCheck, UserRound } from "lucide-react";
import { shopApi } from "./api";
import { notifyCustomerChange } from "./CustomerSession";
import "./customer-auth.css";

export function CustomerAuthPage({ register }: { register: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (register && data.get("password") !== data.get("confirm")) {
      setError("Mật khẩu xác nhận chưa khớp.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await shopApi("/auth/" + (register ? "register" : "login"), "POST", {
        email: data.get("email"), password: data.get("password"), ...(register ? { name: data.get("name") } : {}),
      });
      notifyCustomerChange();
      location.replace("/");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return <div className="shop customer-auth-page">
    <aside className="auth-story" aria-label="Commerce Lab · Everyday movement">
      <img src="/images/walking-studio.png" alt="Đôi giày đi bộ màu kem trên bệ đá" className="auth-story-image" />
      <div className="auth-story-shade" />
      <a className="auth-brand" href="/"><Footprints size={28} strokeWidth={1.6} /><span>commerce<span className="auth-brand-light">lab</span><small>EVERYDAY MOVEMENT</small></span></a>
      <div className="auth-story-copy">
        <span className="auth-eyebrow">DÀNH CHO HÀNH TRÌNH CỦA BẠN</span>
        <h2>Một bước nhẹ.<br /><em>Một ngày mới.</em></h2>
        <p>Những đôi giày thoải mái.<br />Những trải nghiệm dành riêng cho bạn.</p>
      </div>
      <div className="auth-story-bottom"><span>THOẢI MÁI THEO CÁCH CỦA BẠN</span><span>01 — EVERYDAY</span></div>
    </aside>
    <main className="auth-content">
      <header className="auth-topbar"><a href="/"><ArrowLeft size={16} />Về cửa hàng</a><span>TÀI KHOẢN KHÁCH HÀNG</span></header>
      <div className="auth-form-wrap">
        <a href="/" className="auth-mobile-brand"><Footprints size={24} />commerce<span>lab</span></a>
        <nav className="auth-tabs" aria-label="Đăng nhập hoặc đăng ký">
          <a href="/login" aria-current={!register ? "page" : undefined} className={!register ? "selected" : ""}>Đăng nhập</a>
          <a href="/register" aria-current={register ? "page" : undefined} className={register ? "selected" : ""}>Đăng ký</a>
        </nav>
        <div className="auth-heading"><h1>{register ? "Tạo tài khoản của bạn" : "Chào bạn trở lại"}</h1><p>{register ? "Một tài khoản cho giỏ hàng, đơn hàng và trợ lý mua sắm của riêng bạn." : "Đăng nhập để tiếp tục mua sắm và theo dõi những đơn hàng của bạn."}</p></div>
        <form onSubmit={submit} className="auth-form">
          {register && <div className="auth-field"><label htmlFor="customer-name">Họ và tên</label><div className="auth-input"><UserRound size={17} /><input id="customer-name" name="name" autoComplete="name" placeholder="Nguyễn Minh Anh" required minLength={2} maxLength={120} disabled={busy} /></div></div>}
          <div className="auth-field"><label htmlFor="customer-email">Email</label><div className="auth-input"><Mail size={17} /><input id="customer-email" name="email" type="email" autoComplete="username" placeholder="ban@example.com" required maxLength={254} disabled={busy} /></div></div>
          <div className="auth-field"><label htmlFor="customer-password">Mật khẩu</label><div className="auth-input"><LockKeyhole size={17} /><input id="customer-password" aria-describedby={register ? "customer-password-help" : undefined} name="password" type={showPassword ? "text" : "password"} autoComplete={register ? "new-password" : "current-password"} placeholder={register ? "Tạo mật khẩu của bạn" : "Nhập mật khẩu"} required minLength={register ? 10 : 1} maxLength={128} disabled={busy} /><button type="button" className="auth-password-toggle" onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"} aria-pressed={showPassword} disabled={busy}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>{register && <small id="customer-password-help">Sử dụng từ 10 đến 128 ký tự.</small>}</div>
          {register && <div className="auth-field"><label htmlFor="customer-confirm">Nhập lại mật khẩu</label><div className="auth-input"><LockKeyhole size={17} /><input id="customer-confirm" name="confirm" type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="Nhập lại mật khẩu vừa tạo" required minLength={10} maxLength={128} disabled={busy} /></div></div>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" disabled={busy}>{busy ? "Đang xử lý…" : register ? "Tạo tài khoản" : "Đăng nhập"}<ArrowRight size={18} /></button>
        </form>
        <p className="auth-switch">{register ? "Đã có tài khoản? " : "Lần đầu ghé Commerce Lab? "}<a href={register ? "/login" : "/register"}>{register ? "Đăng nhập" : "Đăng ký ngay"}</a></p>
        <div className="auth-private"><ShieldCheck size={17} /><span>Đơn hàng và thông tin mua sắm thuộc riêng tài khoản của bạn.</span></div>
      </div>
      <footer className="auth-footer"><span>© {new Date().getFullYear()} Commerce Lab</span><span>Nhẹ bước mỗi ngày.</span></footer>
    </main>
  </div>;
}

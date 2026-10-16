import React, { type FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Package,
  ShieldCheck,
  Sparkles,
  Boxes,
} from "lucide-react";
import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";
export function Login({
  onLogin,
  initialError,
}: {
  onLogin: (user: string) => void;
  initialError: string;
}) {
  const [username, setUsername] = useState("admin"),
    [password, setPassword] = useState(""),
    [error, setError] = useState(initialError),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api("/auth/login", "POST", { username, password });
      onLogin(result.username);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <Boxes size={23} />
          </span>
          <span>
            commerce<span className="brand-light">lab</span>
          </span>
        </div>
        <div className="story-copy">
          <span className="eyebrow">YOUR COMMERCE WORKSPACE</span>
          <h1>
            Mọi thứ cần thiết.
            <br />
            Trong một không gian.
          </h1>
          <p>
            Quản lý sản phẩm, chăm chút kiến thức và giữ dữ liệu của bạn luôn
            sẵn sàng.
          </p>
          <div className="story-pills">
            <span>
              <Package size={16} /> Catalog
            </span>
            <span>
              <BookOpen size={16} /> Knowledge
            </span>
            <span>
              <Sparkles size={16} /> AI-ready
            </span>
          </div>
        </div>
        <div className="story-bottom">
          <span className="live-dot" /> Ecommerce × LLM · Development workspace
        </div>
        <div className="orbit o1" />
        <div className="orbit o2" />
      </div>
      <div className="login-main">
        <div className="login-card">
          <span className="login-icon">
            <ShieldCheck size={26} />
          </span>
          <h2>Chào mừng trở lại</h2>
          <p>Đăng nhập để quản lý cửa hàng của bạn.</p>
          <form onSubmit={submit}>
            <label>
              Tên đăng nhập
              <input
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </label>
            <label>
              Mật khẩu
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            <ErrorBox message={error} />
            <button className="button primary full" disabled={busy}>
              {busy ? "Đang đăng nhập…" : "Đăng nhập"}
              <ArrowRight size={17} />
            </button>
          </form>
          <p className="login-note">
            <ShieldCheck size={14} /> Phiên quản trị được bảo vệ bằng cookie
            HttpOnly.
          </p>
        </div>
        <small className="login-footer">
          Commerce Lab Admin · Built for your next idea
        </small>
      </div>
    </div>
  );
}

import React, { type FormEvent, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Database,
  LogOut,
  Menu,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  X,
  Boxes,
} from "lucide-react";
import type { View, Category, Job, SiteSettings, Overview } from "./types";
import { api } from "./lib/api";
import { ErrorBox, Modal } from "./components/ui";
import { nav } from "./lib/nav";
import { Login } from "./pages/Login";
import { OverviewPage } from "./pages/Overview";
import { ProductsPage, ProductEditor } from "./pages/Products";
import { CategoriesPage, CategoryEditor } from "./pages/Categories";
import { KnowledgePage, KnowledgeEditor } from "./pages/Knowledge";
import { JobsPage } from "./pages/Jobs";
import { OrdersPage } from "./pages/Orders";
import { MonitoringPage } from "./pages/Monitoring";
import { AIHealthPage } from "./pages/AIHealth";
import { SettingsPage } from "./pages/Settings";
export function App() {
  const [username, setUsername] = useState<string | null | undefined>(
      undefined,
    ),
    [bootError, setBootError] = useState(""),
    [view, setView] = useState<View>(() => {
      const value = new URLSearchParams(location.search).get("view");
      return nav.some((n) => n.id === value) ? (value as View) : "overview";
    }),
    [revision, setRevision] = useState(0),
    [stats, setStats] = useState<Overview | null>(null),
    [settings, setSettings] = useState<SiteSettings | null>(null),
    [categories, setCategories] = useState<Category[]>([]),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [mobile, setMobile] = useState(false),
    [editor, setEditor] = useState<{
      type: "product" | "category" | "knowledge";
      value: any;
    } | null>(null),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false);
  const refresh = () => setRevision((v) => v + 1);
  useEffect(() => {
    api("/auth/me")
      .then((v) => setUsername(v.username))
      .catch((e) => {
        if (e.status !== 401) setBootError(e.message);
        setUsername(null);
      });
    const expired = () => setUsername(null);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (!username) return;
    let alive = true;
    Promise.all([
      api<Overview>("/overview"),
      api<SiteSettings>("/settings"),
      api<Category[]>("/categories"),
    ])
      .then(([a, b, c]) => {
        if (alive) {
          setStats(a);
          setSettings(b);
          setCategories(c);
          setError("");
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [username, revision]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  function navigate(v: View) {
    setView(v);
    history.replaceState(null, "", "?view=" + v);
    setMobile(false);
  }
  function saved() {
    setEditor(null);
    refresh();
    setToast("Đã lưu thay đổi thành công.");
  }
  async function retry(id: string) {
    try {
      await api("/jobs/" + id + "/retry", "POST");
      refresh();
      setToast("Đã đưa job vào hàng đợi.");
    } catch (e) {
      setToast((e as Error).message);
    }
  }
  async function doReindex() {
    setBusy(true);
    try {
      const result = await api("/jobs/reindex", "POST");
      setConfirm(false);
      refresh();
      setToast(`Đã xếp hàng ${result.requeued} nguồn dữ liệu.`);
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (username === undefined)
    return (
      <div className="boot">
        <Boxes size={30} />
        <p>Đang mở không gian quản trị…</p>
      </div>
    );
  if (!username)
    return <Login onLogin={setUsername} initialError={bootError} />;
  const title = nav.find((n) => n.id === view)?.title;
  const subtitles: Record<View, string> = {
    "ai-health": "Kiểm tra kết nối và khả năng phản hồi của model AI.",
    monitoring: "Theo dõi tài nguyên, hiệu năng API và log hệ thống.",
    orders: "Theo dõi đơn thử nghiệm từ cửa hàng.",
    overview: "Một góc nhìn rõ ràng về cửa hàng của bạn.",
    products: "Quản lý catalog, biến thể và tồn kho tại một nơi.",
    categories: "Giúp khách hàng tìm thấy điều họ cần.",
    knowledge: "Nguồn thông tin đáng tin cậy cho trợ lý AI.",
    jobs: "Theo dõi hành trình từ nội dung đến vector.",
    settings: "Thiết lập không gian làm việc theo cách của bạn.",
  };
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
        <div className="brand">
          <span className="brand-mark">
            <Boxes size={23} />
          </span>
          <span>
            commerce<span className="brand-light">lab</span>
          </span>
        </div>
        <div className="workspace-card">
          <span className="workspace-avatar">
            {(settings?.shop_name || "C").slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{settings?.shop_name || "Commerce Lab"}</strong>
            <small>
              <span className="live-dot" /> Development workspace
            </small>
          </div>
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav>
          {nav
            .filter((n) => n.id !== "settings" && n.id !== "monitoring" && n.id !== "ai-health")
            .map((n) => (
              <button
                className={view === n.id ? "active" : ""}
                key={n.id}
                onClick={() => navigate(n.id)}
              >
                <n.icon size={19} />
                <span>{n.title}</span>
                {n.id === "products" && stats && (
                  <small>{stats.products}</small>
                )}
                {n.id === "jobs" && (stats?.jobs.failed || 0) > 0 && (
                  <i className="nav-alert" />
                )}
              </button>
            ))}
        </nav>
        <span className="nav-label system-label">HỆ THỐNG</span>
        <nav>
          <button className={view === "ai-health" ? "active" : ""} onClick={() => navigate("ai-health")}><Activity size={19} />Health check AI</button>
          <button className={view === "monitoring" ? "active" : ""} onClick={() => navigate("monitoring")}><Activity size={19} />Monitoring</button>
          <button
            className={view === "settings" ? "active" : ""}
            onClick={() => navigate("settings")}
          >
            <Settings2 size={19} />
            Cài đặt
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="ready-card">
            <Sparkles size={20} />
            <strong>Sẵn sàng cho AI</strong>
            <p>
              Quản lý dữ liệu tốt hơn.
              <br />
              Xây trải nghiệm thông minh hơn.
            </p>
            <button onClick={() => navigate("knowledge")}>
              Khám phá kho kiến thức
              <ArrowRight size={13} />
            </button>
          </div>
          <div className="profile">
            <span className="profile-avatar">A</span>
            <div>
              <strong>{username}</strong>
              <small>Quản trị viên</small>
            </div>
            <button
              className="icon-button"
              aria-label="Đăng xuất"
              onClick={async () => {
                try {
                  await api("/auth/logout", "POST");
                  setUsername(null);
                  setEditor(null);
                } catch (e) {
                  setToast((e as Error).message);
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      {mobile && (
        <button
          className="mobile-shade"
          aria-label="Đóng menu"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="Mở menu"
              onClick={() => setMobile(true)}
            >
              <Menu size={21} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div>
            <span className="environment">
              <span />
              Môi trường demo
            </span>
            <span className="topbar-divider" />
            <button
              className="icon-button"
              title="Làm mới dữ liệu"
              aria-label="Làm mới dữ liệu"
              onClick={refresh}
            >
              <RefreshCw size={17} />
            </button>
            <span className="small-avatar">A</span>
          </div>
        </header>
        <main>
          <div className="page-title">
            <div>
              <div className="breadcrumb">
                COMMERCE LAB / {(view === "settings" || view === "monitoring" || view === "ai-health") ? "SYSTEM" : "WORKSPACE"}
              </div>
              <h1>{title}</h1>
              <p>{subtitles[view]}</p>
            </div>
            <div>
              {view === "products" ? (
                <button
                  className="button primary"
                  onClick={() => setEditor({ type: "product", value: null })}
                >
                  <Plus size={17} />
                  Thêm sản phẩm
                </button>
              ) : view === "categories" ? (
                <button
                  className="button primary"
                  onClick={() => setEditor({ type: "category", value: null })}
                >
                  <Plus size={17} />
                  Thêm danh mục
                </button>
              ) : view === "knowledge" ? (
                <button
                  className="button primary"
                  onClick={() => setEditor({ type: "knowledge", value: null })}
                >
                  <Plus size={17} />
                  Thêm tài liệu
                </button>
              ) : view === "jobs" ? (
                <button
                  className="button primary"
                  onClick={() => setConfirm(true)}
                >
                  <RefreshCw size={16} />
                  Đồng bộ lại tất cả
                </button>
              ) : view === "overview" ? (
                <button className="button" onClick={() => navigate("products")}>
                  Quản lý sản phẩm
                  <ArrowRight size={16} />
                </button>
              ) : null}
            </div>
          </div>
          <ErrorBox message={error} />
          {view === "overview" && (
            <OverviewPage
              stats={stats}
              revision={revision}
              onView={navigate}
              onEdit={(p) => setEditor({ type: "product", value: p })}
            />
          )}
          {view === "products" && (
            <ProductsPage
              revision={revision}
              onEdit={(p) => setEditor({ type: "product", value: p })}
              onCreate={() => setEditor({ type: "product", value: null })}
            />
          )}
          {view === "ai-health" && <AIHealthPage revision={revision} />}
          {view === "monitoring" && <MonitoringPage revision={revision} />}
          {view === "orders" && <OrdersPage revision={revision} />}
          {view === "categories" && (
            <CategoriesPage
              items={categories}
              onEdit={(c) => setEditor({ type: "category", value: c })}
              onCreate={() => setEditor({ type: "category", value: null })}
            />
          )}
          {view === "knowledge" && (
            <KnowledgePage
              revision={revision}
              onEdit={(d) => setEditor({ type: "knowledge", value: d })}
            />
          )}
          {view === "jobs" && (
            <JobsPage revision={revision} stats={stats} onRetry={retry} />
          )}
          {view === "settings" && settings && (
            <SettingsPage
              key={revision}
              value={settings}
              onSaved={() => {
                refresh();
                setToast("Đã lưu cài đặt.");
              }}
            />
          )}
          <footer className="page-footer">
            <span>Commerce Lab · Admin workspace</span>
            <span>Catalog & knowledge, in sync.</span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={19} />
          {toast}
          <button
            className="icon-button"
            aria-label="Đóng thông báo"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {editor?.type === "product" && (
        <ProductEditor
          product={editor.value}
          categories={categories}
          onClose={() => setEditor(null)}
          onSaved={saved}
        />
      )}
      {editor?.type === "category" && (
        <CategoryEditor
          category={editor.value}
          onClose={() => setEditor(null)}
          onSaved={saved}
        />
      )}
      {editor?.type === "knowledge" && (
        <KnowledgeEditor
          document={editor.value}
          onClose={() => setEditor(null)}
          onSaved={saved}
        />
      )}
      {confirm && (
        <Modal
          title="Đồng bộ lại toàn bộ dữ liệu?"
          subtitle="Sản phẩm và tài liệu sẽ được đưa lại vào hàng đợi embedding. Job đang chạy được giữ nguyên."
          onClose={() => setConfirm(false)}
          busy={busy}
        >
          <div className="modal-body">
            <div className="note">
              <Database size={20} />
              <p>
                Các vector hiện tại được giữ cho đến khi thay thế thành công.
                Quá trình chạy nền có thể mất vài phút.
              </p>
            </div>
          </div>
          <div className="modal-footer">
            <span />
            <div>
              <button
                className="button"
                disabled={busy}
                onClick={() => setConfirm(false)}
              >
                Hủy
              </button>
              <button
                className="button primary"
                disabled={busy}
                onClick={doReindex}
              >
                {busy ? "Đang xếp hàng…" : "Xác nhận đồng bộ"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

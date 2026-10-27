import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Storefront } from "./store/Storefront";
import { CustomerProvider, useCustomer } from "./store/CustomerSession";
import { CustomerAuthPage } from "./store/CustomerAuthPage";
import { CustomerAccount } from "./store/CustomerAccount";
import "./styles.css";
import "./store/store.css";
const admin = location.pathname.startsWith("/admin");
document.title = admin
  ? "Commerce Lab · Admin"
  : "Commerce Lab · Nhẹ bước mỗi ngày";
function CustomerApp() {
  const { user, loading } = useCustomer();
  if (location.pathname === "/login" || location.pathname === "/register") return <CustomerAuthPage register={location.pathname === "/register"} />;
  if (location.pathname === "/account") return <CustomerAccount key={user?.id || "guest"} />;
  if (loading) return <div className="shop shop-empty" role="status">Đang mở cửa hàng…</div>;
  return <Storefront key={user?.id || "guest"} />;
}
createRoot(document.getElementById("root")!).render(
  admin ? <App /> : <CustomerProvider><CustomerApp /></CustomerProvider>,
);

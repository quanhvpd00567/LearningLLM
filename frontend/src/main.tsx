import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Storefront } from "./store/Storefront";
import "./styles.css";
import "./store/store.css";
const admin = location.pathname.startsWith("/admin");
document.title = admin
  ? "Commerce Lab · Admin"
  : "Commerce Lab · Nhẹ bước mỗi ngày";
createRoot(document.getElementById("root")!).render(
  admin ? <App /> : <Storefront />,
);

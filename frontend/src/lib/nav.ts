import {
  Activity,
  BookOpen,
  Layers3,
  LayoutDashboard,
  Package,
  ReceiptText,
  Settings2,
} from "lucide-react";
import type { View } from "../types";
export const nav: { id: View; title: string; icon: typeof Package }[] = [
  { id: "overview", title: "Tổng quan", icon: LayoutDashboard },
  { id: "products", title: "Sản phẩm", icon: Package },
  { id: "orders", title: "Đơn hàng", icon: ReceiptText },
  { id: "categories", title: "Danh mục", icon: Layers3 },
  { id: "knowledge", title: "Kho kiến thức", icon: BookOpen },
  { id: "jobs", title: "Đồng bộ dữ liệu", icon: Activity },
  { id: "ai-health", title: "Health check AI", icon: Activity },
  { id: "monitoring", title: "Monitoring", icon: Activity },
  { id: "settings", title: "Cài đặt", icon: Settings2 },
];

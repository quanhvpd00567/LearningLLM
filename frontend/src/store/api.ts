export type ShopConfig = {
  shop_name: string;
  contact_email: string;
  shipping_fee: number;
  currency: string;
  demo: boolean;
};
export type Category = {
  id: string;
  name: string;
  slug: string;
  count: number;
};
export type Variant = {
  id: string;
  sku: string;
  options: Record<string, unknown>;
  price: string;
  stock: number;
};
export type Product = {
  id: string;
  name: string;
  description: string;
  category: string;
  category_slug: string;
  category_id: string;
  attributes: Record<string, unknown>;
  min_price: string;
  stock: number;
  variants: Variant[];
};
export type Cart = {
  items: {
    variant_id: string;
    product_id: string;
    name: string;
    sku: string;
    options: Record<string, unknown>;
    price: string;
    stock: number;
    quantity: number;
    available: boolean;
    line_total: string;
  }[];
  subtotal: string;
  shipping_fee: string;
  total: string;
};
export type Order = {
  id: string;
  code: string;
  status: string;
  customer_name: string;
  phone: string;
  address: string;
  note: string;
  subtotal: string;
  shipping_fee: string;
  total: string;
  created_at: string;
  items: {
    name: string;
    sku: string;
    options: Record<string, unknown>;
    unit_price: string;
    quantity: number;
  }[];
};
export type Policy = { id: string; title: string; content: string };
export type ChatResponse = {
  message: string;
  products: Product[];
  sources: { id: string; type: string; title: string }[];
  degraded: boolean;
  private?: boolean;
};
export const money = (n: string | number) =>
  new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(Number(n));
export const options = (value: Record<string, unknown>) =>
  Object.entries(value)
    .map(
      ([k, v]) => `${k === "size" ? "Size" : k === "color" ? "Màu" : k}: ${v}`,
    )
    .join(" · ");
export const image = (slug: string) =>
  ["trail", "running"].includes(slug)
    ? "/images/trail-studio.png"
    : "/images/walking-studio.png";
export const orderStatus: Record<string, string> = {
  pending: "Chờ xác nhận",
  confirmed: "Đã xác nhận",
  shipping: "Đang giao",
  completed: "Hoàn tất",
  cancelled: "Đã hủy",
};
export async function shopApi<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api/v1/store" + path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/")) window.dispatchEvent(new Event("customer-session-expired"));
    const error = new Error(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? "Thông tin chưa hợp lệ. Vui lòng kiểm tra lại các trường đã nhập."
          : "Chưa kết nối được cửa hàng. Vui lòng thử lại.",
    );
    throw Object.assign(error, { status: response.status });
  }
  return data;
}

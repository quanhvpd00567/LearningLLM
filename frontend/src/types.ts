export type View =
  | "overview"
  | "orders"
  | "products"
  | "categories"
  | "knowledge"
  | "jobs"
  | "ai-health"
  | "monitoring"
  | "settings";
export type Variant = {
  id?: string;
  sku: string;
  options: Record<string, unknown>;
  price: string;
  stock: number;
};
export type Product = {
  id: string;
  name: string;
  description: string;
  category_id: string;
  category: string;
  attributes: Record<string, unknown>;
  is_active: boolean;
  source_version: number;
  variants: Variant[];
  updated_at: string;
};
export type Category = {
  id: string;
  name: string;
  slug: string;
  product_count: number;
};
export type Document = {
  id: string;
  title: string;
  content: string;
  is_active: boolean;
  source_version: number;
  updated_at: string;
};
export type Job = {
  id: string;
  title: string;
  source_type: string;
  source_version: number;
  status: string;
  attempts: number;
  max_attempts: number;
  created_at: string;
  last_error: string | null;
  embedding_model: string;
  job_type: string;
};
export type SiteSettings = {
  shop_name: string;
  contact_email: string;
  low_stock_threshold: number;
  embedding_paused: boolean;
  runtime: {
    embedding_model: string;
    embedding_dimensions: number;
    chat_model: string;
    pipeline_version: number;
    batch_size: number;
    poll_seconds: number;
    lease_seconds: number;
    currency: string;
  };
};
export type Overview = {
  products: number;
  active_products: number;
  documents: number;
  variants: number;
  low_stock: number;
  chunks: number;
  jobs: Record<string, number>;
  shop_name: string;
  embedding_paused: boolean;
  low_stock_threshold: number;
};
export type Page<T> = { items: T[]; total: number };

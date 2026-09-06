const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface PostLog {
  id: number;
  product_id?: number | null;
  product_name: string;
  affiliate_url: string;
  extra_commission_url?: string | null;
  target_thread_url?: string | null;
  target_thread_snippet?: string | null;
  post_text?: string | null;
  threads_post_url?: string | null;
  threads_post_id?: string | null;
  status: "running" | "success" | "failed";
  error_message?: string | null;
  final_screenshot?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface AgentStepLog {
  id: number;
  step_number: number;
  tool_name: string;
  tool_arguments?: string | null;
  tool_output?: string | null;
  thought?: string | null;
  screenshot_path?: string | null;
  created_at: string;
}

export interface PostLogDetail extends PostLog {
  steps: AgentStepLog[];
}

export interface Product {
  id: number;
  product_id?: string | null;
  product_name: string;
  price?: string | null;
  sales_count?: string | null;
  shop_name?: string | null;
  commission_rate?: string | null;
  commission_amount?: string | null;
  product_url?: string | null;
  extra_commission_url?: string | null;
  affiliate_url: string;
  is_posted: boolean;
  post_count: number;
  last_posted_at?: string | null;
  status: "pending" | "in_progress" | "posted" | "failed";
  retry_count: number;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SystemSettings {
  openrouter_api_key_set: boolean;
  openrouter_model: string;
  threads_username: string;
  threads_password_set: boolean;
  admin_passcode_set?: boolean;
  scheduler_enabled: boolean;
  scheduler_window_minutes: number;
  scheduler_posts_per_window: number;
  calculated_interval_minutes: number;
  min_thread_comments: number;
  min_thread_likes: number;
  headless_browser: boolean;
}

export interface CronStatus {
  is_running: boolean;
  scheduler_enabled: boolean;
  interval_minutes: number;
  window_minutes: number;
  posts_per_window: number;
  next_run_time?: string | null;
  total_products_count: number;
  unposted_products_count: number;
  commented_threads_count: number;
  is_currently_posting: boolean;
}

export interface CSVUploadResponse {
  total_parsed: number;
  added: number;
  skipped_duplicates: number;
  failed: number;
  message: string;
}

export async function fetchPublicLogs(search?: string): Promise<PostLog[]> {
  const url = new URL(`${API_BASE}/api/logs`);
  if (search) url.searchParams.set("search", search);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch public logs");
  return res.json();
}

export async function fetchLogDetail(id: number, adminKey: string): Promise<PostLogDetail> {
  const res = await fetch(`${API_BASE}/api/logs/${id}`, {
    headers: { "x-admin-key": adminKey },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch log details");
  return res.json();
}

export async function fetchProducts(adminKey: string, isPosted?: boolean): Promise<Product[]> {
  const url = new URL(`${API_BASE}/api/products`);
  if (isPosted !== undefined) url.searchParams.set("is_posted", String(isPosted));
  const res = await fetch(url.toString(), {
    headers: { "x-admin-key": adminKey },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch products");
  return res.json();
}

export async function uploadProductsCsv(file: File, adminKey: string): Promise<CSVUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/products/upload-csv`, {
    method: "POST",
    headers: { "x-admin-key": adminKey },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload CSV");
  }
  return res.json();
}

export async function deleteProduct(id: number, adminKey: string) {
  const res = await fetch(`${API_BASE}/api/products/${id}`, {
    method: "DELETE",
    headers: { "x-admin-key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to delete product");
  return res.json();
}

export async function bulkDeleteProducts(productIds: number[], adminKey: string) {
  const res = await fetch(`${API_BASE}/api/products/bulk-delete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-admin-key": adminKey,
    },
    body: JSON.stringify({ product_ids: productIds }),
  });
  if (!res.ok) throw new Error("Failed to delete selected products");
  return res.json();
}

export async function deleteAllProducts(adminKey: string) {
  const res = await fetch(`${API_BASE}/api/products/delete-all`, {
    method: "POST",
    headers: { "x-admin-key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to delete all products");
  return res.json();
}

export async function retryProduct(id: number, adminKey: string) {
  const res = await fetch(`${API_BASE}/api/products/${id}/retry`, {
    method: "POST",
    headers: { "x-admin-key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to retry product");
  return res.json();
}

export async function fetchSettings(adminKey: string): Promise<SystemSettings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    headers: { "x-admin-key": adminKey },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function updateSettings(
  data: Partial<SystemSettings> & { threads_password?: string; openrouter_api_key?: string; admin_passcode?: string },
  adminKey: string
) {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "x-admin-key": adminKey,
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update settings");
  return res.json();
}

export async function fetchCronStatus(): Promise<CronStatus> {
  const res = await fetch(`${API_BASE}/api/cron/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch cron status");
  return res.json();
}

export async function triggerPostNow(adminKey: string) {
  const res = await fetch(`${API_BASE}/api/cron/trigger-now`, {
    method: "POST",
    headers: { "x-admin-key": adminKey },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to trigger post");
  }
  return res.json();
}

export async function toggleCronScheduler(
  enabled: boolean,
  adminKey: string
): Promise<{ success: boolean; scheduler_enabled: boolean; message: string; cron_status: CronStatus }> {
  const res = await fetch(`${API_BASE}/api/cron/toggle`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-admin-key": adminKey,
    },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Gagal mengubah status scheduler cron");
  }
  return res.json();
}

export async function deleteLog(logId: number, adminKey: string) {
  const res = await fetch(`${API_BASE}/api/logs/${logId}`, {
    method: "DELETE",
    headers: { "x-admin-key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to delete log");
  return res.json();
}

export async function deleteAllLogs(adminKey: string) {
  const res = await fetch(`${API_BASE}/api/logs`, {
    method: "DELETE",
    headers: { "x-admin-key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to delete all logs");
  return res.json();
}

export function getFullImageUrl(url?: string | null): string {
  if (!url) return "";
  if (url.startsWith("http") || url.startsWith("data:")) return url;
  return `${API_BASE}${url}`;
}

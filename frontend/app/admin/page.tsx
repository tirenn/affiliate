"use client";

import { useEffect, useState } from "react";
import {
  fetchProducts,
  uploadProductsCsv,
  deleteProduct,
  bulkDeleteProducts,
  deleteAllProducts,
  retryProduct,
  fetchSettings,
  updateSettings,
  fetchCronStatus,
  triggerPostNow,
  toggleCronScheduler,
  fetchPublicLogs,
  fetchLogDetail,
  deleteLog,
  deleteAllLogs,
  uploadSessionFile,
  deleteSessionFile,
  Product,
  SystemSettings,
  CronStatus,
  PostLog,
  PostLogDetail,
  getFullImageUrl,
} from "@/lib/api";
import {
  Lock,
  UploadCloud,
  Play,
  Pause,
  Trash2,
  RotateCw,
  Settings as SettingsIcon,
  ListOrdered,
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  EyeOff,
  ChevronRight,
  ShieldCheck,
  Flame,
  ExternalLink,
  Download,
  Layers,
  Sparkles,
  CheckSquare,
  Square,
  AlertTriangle,
  Globe,
  FileText,
} from "lucide-react";

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authInput, setAuthInput] = useState("");
  const [authError, setAuthError] = useState("");
  const [showAdminPasscode, setShowAdminPasscode] = useState(false);
  const [showNewAdminPasscode, setShowNewAdminPasscode] = useState(false);
  const [showThreadsPassword, setShowThreadsPassword] = useState(false);
  const [showThreadsSessionId, setShowThreadsSessionId] = useState(false);

  // Data states
  const [products, setProducts] = useState<Product[]>([]);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [cronStatus, setCronStatus] = useState<CronStatus | null>(null);
  const [logs, setLogs] = useState<PostLog[]>([]);
  const [selectedLogDetail, setSelectedLogDetail] = useState<PostLogDetail | null>(null);
  const [selectedScreenshot, setSelectedScreenshot] = useState<string | null>(null);

  // Selection state for bulk delete
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);

  // Form states
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [toggleCronLoading, setToggleCronLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"queue" | "traces" | "settings">("queue");
  const [filterPosted, setFilterPosted] = useState<"all" | "unposted" | "posted">("all");

  // Settings form
  const [settingsForm, setSettingsForm] = useState<{
    openrouter_api_key: string;
    openrouter_model: string;
    threads_username: string;
    threads_password: string;
    threads_session_id: string;
    admin_passcode: string;
    scheduler_enabled: boolean;
    scheduler_window_minutes: number | string;
    scheduler_posts_per_window: number | string;
    min_thread_comments: number | string;
    min_thread_likes: number | string;
    headless_browser: boolean;
    proxy_url: string;
  }>({
    openrouter_api_key: "",
    openrouter_model: "openrouter/free",
    threads_username: "",
    threads_password: "",
    threads_session_id: "",
    admin_passcode: "",
    scheduler_enabled: false,
    scheduler_window_minutes: 60,
    scheduler_posts_per_window: 10,
    min_thread_comments: 100,
    min_thread_likes: 100,
    headless_browser: true,
    proxy_url: "",
  });

  const [sessionFile, setSessionFile] = useState<File | null>(null);
  const [sessionUploading, setSessionUploading] = useState(false);
  const [sessionMessage, setSessionMessage] = useState("");
  const [sessionDeleting, setSessionDeleting] = useState(false);

  useEffect(() => {
    const savedKey = sessionStorage.getItem("admin_key");
    if (savedKey) {
      setAdminKey(savedKey);
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    try {
      await fetchProducts(authInput);
      setAdminKey(authInput);
      setIsAuthenticated(true);
      sessionStorage.setItem("admin_key", authInput);
    } catch (err: any) {
      setAuthError("Incorrect admin passcode. Please try again.");
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem("admin_key");
    setIsAuthenticated(false);
    setAdminKey("");
  };

  const reloadData = async () => {
    if (!adminKey) return;
    try {
      const isPostedFilter = filterPosted === "unposted" ? false : filterPosted === "posted" ? true : undefined;
      const [prods, s, cs, l] = await Promise.all([
        fetchProducts(adminKey, isPostedFilter),
        fetchSettings(adminKey),
        fetchCronStatus(),
        fetchPublicLogs(),
      ]);
      setProducts(prods);
      setSettings(s);
      setCronStatus(cs);
      setLogs(l);

      setSettingsForm((prev) => ({
        ...prev,
        openrouter_model: s.openrouter_model || "openrouter/free",
        threads_username: s.threads_username || "",
        scheduler_enabled: s.scheduler_enabled,
        scheduler_window_minutes: s.scheduler_window_minutes,
        scheduler_posts_per_window: s.scheduler_posts_per_window,
        min_thread_comments: s.min_thread_comments,
        min_thread_likes: s.min_thread_likes ?? 100,
        headless_browser: s.headless_browser,
        proxy_url: s.proxy_url || "",
      }));
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      reloadData();
      const timer = setInterval(reloadData, 10000);
      return () => clearInterval(timer);
    }
  }, [isAuthenticated, adminKey, filterPosted]);

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setUploadLoading(true);
    setUploadMessage("");
    try {
      const res = await uploadProductsCsv(csvFile, adminKey);
      setUploadMessage(`Success! Added: ${res.added}, Duplicates Skipped: ${res.skipped_duplicates}.`);
      setCsvFile(null);
      await reloadData();
    } catch (err: any) {
      setUploadMessage(`Upload failed: ${err.message}`);
    } finally {
      setUploadLoading(false);
    }
  };

  // Checkbox Selection
  const toggleSelectAll = () => {
    if (selectedProductIds.length === products.length) {
      setSelectedProductIds([]);
    } else {
      setSelectedProductIds(products.map((p) => p.id));
    }
  };

  const toggleSelectProduct = (id: number) => {
    setSelectedProductIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleDeleteProduct = async (id: number) => {
    if (!confirm("Delete this product from the database?")) return;
    try {
      await deleteProduct(id, adminKey);
      setSelectedProductIds((prev) => prev.filter((i) => i !== id));
      await reloadData();
    } catch (err) {
      alert("Failed to delete product");
    }
  };

  const handleBulkDelete = async () => {
    if (selectedProductIds.length === 0) return;
    if (!confirm(`Delete ${selectedProductIds.length} selected products?`)) return;
    try {
      await bulkDeleteProducts(selectedProductIds, adminKey);
      setSelectedProductIds([]);
      await reloadData();
    } catch (err) {
      alert("Failed to delete selected products");
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm("WARNING: Are you sure you want to delete ALL products from database?")) return;
    try {
      await deleteAllProducts(adminKey);
      setSelectedProductIds([]);
      await reloadData();
    } catch (err) {
      alert("Failed to clear products");
    }
  };

  const handleToggleCron = async () => {
    if (!adminKey) return;
    const currentEnabled = cronStatus?.scheduler_enabled ?? false;
    const nextEnabled = !currentEnabled;
    setToggleCronLoading(true);
    try {
      const res = await toggleCronScheduler(nextEnabled, adminKey);
      setCronStatus(res.cron_status);
      setSettingsForm((prev) => ({ ...prev, scheduler_enabled: nextEnabled }));
      await reloadData();
    } catch (err: any) {
      alert(err.message || "Failed to update cron schedule status");
    } finally {
      setToggleCronLoading(false);
    }
  };

  const handleTriggerNow = async () => {
    setTriggerLoading(true);
    try {
      await triggerPostNow(adminKey);
      alert("Threads bot triggered! Searching for viral threads and commenting in the background.");
      await reloadData();
    } catch (err: any) {
      alert(err.message || "Failed to trigger bot");
    } finally {
      setTriggerLoading(false);
    }
  };

  const handleSessionUpload = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!sessionFile) return;
    setSessionUploading(true);
    setSessionMessage("");
    try {
      const res = await uploadSessionFile(sessionFile, adminKey);
      setSessionMessage(res.message || "Session file uploaded successfully!");
      setSessionFile(null);
      await reloadData();
    } catch (err: any) {
      setSessionMessage(`Upload failed: ${err.message}`);
    } finally {
      setSessionUploading(false);
    }
  };

  const handleDeleteSession = async () => {
    if (!confirm("Are you sure you want to delete the active Threads session? The bot will attempt a fresh login.")) return;
    setSessionDeleting(true);
    try {
      await deleteSessionFile(adminKey);
      alert("Session file deleted successfully.");
      await reloadData();
    } catch (err: any) {
      alert(err.message || "Failed to delete session file");
    } finally {
      setSessionDeleting(false);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...settingsForm,
        scheduler_window_minutes: Number(settingsForm.scheduler_window_minutes) || 60,
        scheduler_posts_per_window: Number(settingsForm.scheduler_posts_per_window) || 10,
        min_thread_comments: Number(settingsForm.min_thread_comments) || 100,
        min_thread_likes: Number(settingsForm.min_thread_likes) || 100,
        proxy_url: settingsForm.proxy_url.trim(),
        threads_session_id: settingsForm.threads_session_id.trim(),
      };
      await updateSettings(payload, adminKey);
      if (settingsForm.threads_session_id.trim()) {
        setSettingsForm((prev) => ({ ...prev, threads_session_id: "" }));
      }
      if (settingsForm.admin_passcode.trim()) {
        const newKey = settingsForm.admin_passcode.trim();
        sessionStorage.setItem("admin_key", newKey);
        setAdminKey(newKey);
        setSettingsForm((prev) => ({ ...prev, admin_passcode: "" }));
      }
      alert("Settings successfully saved to database!");
      await reloadData();
    } catch (err) {
      alert("Failed to save settings");
    }
  };

  const handleInspectLog = async (logId: number) => {
    try {
      const detail = await fetchLogDetail(logId, adminKey);
      setSelectedLogDetail(detail);
    } catch (err) {
      alert("Failed to load log detail");
    }
  };

  const handleDeleteLog = async (logId: number) => {
    if (!confirm(`Delete log entry #${logId}?`)) return;
    try {
      await deleteLog(logId, adminKey);
      if (selectedLogDetail?.id === logId) setSelectedLogDetail(null);
      await reloadData();
    } catch (err) {
      alert("Failed to delete log");
    }
  };

  const handleDeleteAllLogs = async () => {
    if (!confirm("WARNING: Are you sure you want to delete ALL logs and traces? This cannot be undone.")) return;
    try {
      await deleteAllLogs(adminKey);
      setSelectedLogDetail(null);
      await reloadData();
    } catch (err) {
      alert("Failed to clear logs");
    }
  };

  const postsNum = Number(settingsForm.scheduler_posts_per_window) || 0;
  const windowNum = Number(settingsForm.scheduler_window_minutes) || 0;
  const calculatedInterval =
    postsNum > 0
      ? (windowNum / postsNum).toFixed(1)
      : "0";

  // Auth gate
  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto my-16 bg-threads-card border border-threads-border rounded-2xl p-8 shadow-2xl">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-purple-900/50 border border-purple-700/50 text-purple-400 flex items-center justify-center mx-auto">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-white">Admin Authentication</h2>
          <p className="text-xs text-gray-400">
            Enter admin passcode to manage Shopee affiliate products, cron schedules, and bot execution logs.
          </p>
        </div>

        <form onSubmit={handleLogin} className="mt-6 space-y-4" autoComplete="off">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-threads-muted mb-1.5">
              Admin Passcode
            </label>
            <div className="relative">
              <input
                type={showAdminPasscode ? "text" : "password"}
                name="admin_passcode"
                autoComplete="new-password"
                value={authInput}
                onChange={(e) => setAuthInput(e.target.value)}
                placeholder="Enter passcode..."
                className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowAdminPasscode(!showAdminPasscode)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-threads-muted hover:text-white transition-colors focus:outline-none p-1"
                title={showAdminPasscode ? "Hide passcode" : "Show passcode"}
              >
                {showAdminPasscode ? (
                  <EyeOff className="w-4 h-4 text-purple-400" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {authError && <p className="text-xs text-rose-400 font-medium">{authError}</p>}

          <button
            type="submit"
            className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 font-semibold text-sm text-white transition-colors shadow-md"
          >
            Enter Admin Portal
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Admin Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-threads-card border border-threads-border rounded-2xl p-5 sm:p-6 shadow-sm">
        <div>
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h1 className="text-2xl font-bold text-white tracking-tight">Admin Console</h1>
            <span className="px-2.5 py-0.5 rounded-full bg-purple-950 text-purple-300 text-xs font-medium border border-purple-800">
              Viral Threads Bot
            </span>
          </div>
          <p className="text-xs sm:text-sm text-threads-muted mt-1">
            Shopee Affiliate Auto-Comment • Viral Thread ({settingsForm.min_thread_comments || 0}+ Comments / {settingsForm.min_thread_likes || 0}+ Likes) • OpenRouter Free
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {cronStatus?.scheduler_enabled ? (
            <button
              onClick={handleToggleCron}
              disabled={toggleCronLoading}
              className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-sm font-semibold shadow-md transition-all disabled:opacity-50"
              title="Click to pause automated cron"
            >
              <Pause className={`w-4 h-4 ${toggleCronLoading ? "animate-pulse" : ""}`} />
              <span>{toggleCronLoading ? "Pausing..." : "Pause Cron"}</span>
              <span className="text-[10px] bg-amber-800/90 px-1.5 py-0.5 rounded font-mono font-medium">
                Every {calculatedInterval}m
              </span>
            </button>
          ) : (
            <button
              onClick={handleToggleCron}
              disabled={toggleCronLoading}
              className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-md transition-all disabled:opacity-50"
              title="Click to start automated cron"
            >
              <Play className={`w-4 h-4 ${toggleCronLoading ? "animate-spin" : ""}`} />
              <span>{toggleCronLoading ? "Starting..." : "Start Cron"}</span>
            </button>
          )}

          <button
            onClick={handleTriggerNow}
            disabled={triggerLoading || cronStatus?.is_currently_posting}
            className="inline-flex items-center space-x-2 px-3.5 py-2.5 rounded-xl bg-purple-700/60 hover:bg-purple-600 text-white text-xs font-semibold shadow-sm border border-purple-500/30 transition-all disabled:opacity-50"
            title="Post a promotional comment to 1 viral thread immediately"
          >
            <Sparkles className={`w-3.5 h-3.5 ${triggerLoading ? "animate-spin" : ""}`} />
            <span>{cronStatus?.is_currently_posting ? "Processing..." : "Trigger Manual (1x)"}</span>
          </button>

          <button
            onClick={handleLogout}
            className="px-3.5 py-2.5 rounded-xl bg-threads-border/60 hover:bg-threads-border text-xs text-gray-300 transition-colors"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Info Status Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-threads-card border border-threads-border rounded-xl p-4">
          <span className="text-[11px] text-threads-muted uppercase font-medium">Total Products</span>
          <p className="text-2xl font-bold text-white mt-1">{cronStatus?.total_products_count ?? products.length}</p>
          <span className="text-[11px] text-purple-400">Shopee Database</span>
        </div>

        <div className="bg-threads-card border border-threads-border rounded-xl p-4">
          <span className="text-[11px] text-threads-muted uppercase font-medium">Pending Posts</span>
          <p className="text-2xl font-bold text-amber-400 mt-1">{cronStatus?.unposted_products_count ?? 0}</p>
          <span className="text-[11px] text-threads-muted">Current Cycle</span>
        </div>

        <div className="bg-threads-card border border-threads-border rounded-xl p-4">
          <span className="text-[11px] text-threads-muted uppercase font-medium">Commented Threads</span>
          <p className="text-2xl font-bold text-emerald-400 mt-1">{cronStatus?.commented_threads_count ?? 0}</p>
          <span className="text-[11px] text-threads-muted">Anti-Spam Active</span>
        </div>

        <div className="bg-threads-card border border-threads-border rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-threads-muted uppercase font-medium">Cron Status</span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                cronStatus?.scheduler_enabled
                  ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                  : "bg-zinc-800 text-zinc-400 border-zinc-700"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  cronStatus?.scheduler_enabled ? "bg-emerald-400 animate-ping" : "bg-zinc-500"
                }`}
              />
              {cronStatus?.scheduler_enabled ? "Running" : "Paused"}
            </span>
          </div>
          <p className="text-2xl font-bold text-white mt-1">
            {calculatedInterval} <span className="text-sm font-normal text-threads-muted">min</span>
          </p>
          <span className="text-[11px] text-threads-muted">
            {settingsForm.scheduler_posts_per_window || 0} posts / {settingsForm.scheduler_window_minutes || 0}m
          </span>
        </div>
      </div>

      {cronStatus?.ai_quota_exceeded && (
        <div className="bg-amber-950/40 border border-amber-800/60 rounded-xl p-3 flex items-center justify-between text-amber-300 text-xs">
          <div className="flex items-center space-x-2">
            <span className="text-base">⚠️</span>
            <span>
              <strong>AI Quota Limit Active:</strong> OpenRouter AI token credits or rate limit exceeded. Subsequent execution errors will be automatically throttled to prevent database flooding, and normal logging will resume as soon as a post succeeds.
            </span>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-threads-border pb-2">
        <button
          onClick={() => setActiveTab("queue")}
          className={`inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            activeTab === "queue"
              ? "bg-purple-600 text-white"
              : "text-gray-400 hover:text-white hover:bg-threads-card"
          }`}
        >
          <ListOrdered className="w-4 h-4" />
          <span>Manage Products ({products.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("traces")}
          className={`inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            activeTab === "traces"
              ? "bg-purple-600 text-white"
              : "text-gray-400 hover:text-white hover:bg-threads-card"
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Logs & Traces ({logs.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={`inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
            activeTab === "settings"
              ? "bg-purple-600 text-white"
              : "text-gray-400 hover:text-white hover:bg-threads-card"
          }`}
        >
          <SettingsIcon className="w-4 h-4" />
          <span>Schedule & AI Settings</span>
        </button>
      </div>

      {/* TAB 1: MANAGE PRODUCTS & CSV UPLOAD */}
      {activeTab === "queue" && (
        <div className="space-y-6">
          {/* CSV Upload Dropzone */}
          <div className="bg-threads-card border border-threads-border rounded-2xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                <UploadCloud className="w-5 h-5 text-purple-400" />
                <span>Upload Shopee Affiliate CSV File</span>
              </h2>
              <span className="text-xs text-purple-300 bg-purple-950 px-2.5 py-0.5 rounded-full border border-purple-800">
                Auto-Deduplication Active
              </span>
            </div>
            <p className="text-xs text-threads-muted mb-4">
              Supports Shopee Affiliate export (Tab / Comma separated). Columns supported: <code className="text-purple-300">ID Produk</code>, <code className="text-purple-300">Nama Produk</code>, <code className="text-purple-300">Harga</code>, <code className="text-purple-300">Link Komisi Ekstra</code>. Existing records will be skipped automatically.
            </p>

            <form onSubmit={handleCsvUpload} className="space-y-4">
              <div className="border-2 border-dashed border-threads-border rounded-xl p-6 text-center hover:border-purple-500/60 transition-colors">
                <input
                  type="file"
                  accept=".csv,.tsv,.txt"
                  id="csv-input"
                  onChange={(e) => setCsvFile(e.target.files ? e.target.files[0] : null)}
                  className="hidden"
                />
                <label htmlFor="csv-input" className="cursor-pointer block space-y-2">
                  <div className="w-10 h-10 rounded-full bg-purple-900/30 text-purple-400 flex items-center justify-center mx-auto">
                    <UploadCloud className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-medium text-gray-200">
                    {csvFile ? csvFile.name : "Click to browse or drag your Shopee CSV file here"}
                  </p>
                  <p className="text-xs text-threads-muted">Shopee Export TSV / CSV</p>
                </label>
              </div>

              {uploadMessage && (
                <div className="text-xs font-medium px-3 py-2 rounded-lg bg-purple-950/60 text-purple-300 border border-purple-800">
                  {uploadMessage}
                </div>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={!csvFile || uploadLoading}
                  className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold disabled:opacity-50 transition-colors"
                >
                  {uploadLoading ? "Processing & Saving..." : "Add to Database"}
                </button>
              </div>
            </form>
          </div>

          {/* Action Bar (Bulk Delete & Filter) */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-threads-card p-4 rounded-xl border border-threads-border">
            <div className="flex items-center space-x-2">
              <button
                onClick={toggleSelectAll}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-threads-dark hover:bg-threads-border text-xs text-gray-200 transition-colors"
              >
                {selectedProductIds.length === products.length && products.length > 0 ? (
                  <CheckSquare className="w-4 h-4 text-purple-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-400" />
                )}
                <span>Select All</span>
              </button>

              {selectedProductIds.length > 0 && (
                <button
                  onClick={handleBulkDelete}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 text-xs font-semibold border border-rose-800 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete Selected ({selectedProductIds.length})</span>
                </button>
              )}

              <button
                onClick={handleDeleteAll}
                className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-threads-dark hover:bg-rose-950 text-gray-400 hover:text-rose-300 text-xs transition-colors"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Delete All Products</span>
              </button>
            </div>

            <div className="flex items-center space-x-2 text-xs">
              <span className="text-threads-muted">Filter:</span>
              <button
                onClick={() => setFilterPosted("all")}
                className={`px-2.5 py-1 rounded-lg ${
                  filterPosted === "all" ? "bg-purple-600 text-white" : "bg-threads-dark text-gray-400"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilterPosted("unposted")}
                className={`px-2.5 py-1 rounded-lg ${
                  filterPosted === "unposted" ? "bg-purple-600 text-white" : "bg-threads-dark text-gray-400"
                }`}
              >
                Pending
              </button>
              <button
                onClick={() => setFilterPosted("posted")}
                className={`px-2.5 py-1 rounded-lg ${
                  filterPosted === "posted" ? "bg-purple-600 text-white" : "bg-threads-dark text-gray-400"
                }`}
              >
                Posted
              </button>
            </div>
          </div>

          {/* Product Table */}
          <div className="bg-threads-card border border-threads-border rounded-2xl overflow-hidden shadow-sm">
            {products.length === 0 ? (
              <div className="py-12 text-center text-threads-muted text-sm">
                No products found in database. Upload a Shopee CSV file above to add products.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-threads-dark text-xs uppercase tracking-wider text-threads-muted border-b border-threads-border">
                    <tr>
                      <th className="px-4 py-3 w-8">
                        <input
                          type="checkbox"
                          checked={selectedProductIds.length === products.length && products.length > 0}
                          onChange={toggleSelectAll}
                          className="w-4 h-4 rounded text-purple-600 bg-threads-dark border-threads-border"
                        />
                      </th>
                      <th className="px-4 py-3">Product</th>
                      <th className="px-4 py-3">Price / Sales</th>
                      <th className="px-4 py-3">Extra Commission</th>
                      <th className="px-4 py-3">Cycle Status</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-threads-border">
                    {products.map((p) => (
                      <tr key={p.id} className="hover:bg-threads-border/20 transition-colors">
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedProductIds.includes(p.id)}
                            onChange={() => toggleSelectProduct(p.id)}
                            className="w-4 h-4 rounded text-purple-600 bg-threads-dark border-threads-border"
                          />
                        </td>
                        <td className="px-4 py-3 max-w-xs">
                          <p className="font-semibold text-white truncate" title={p.product_name}>
                            {p.product_name}
                          </p>
                          <div className="flex items-center space-x-2 text-[11px] text-threads-muted mt-0.5">
                            {p.product_id && <span>ID: {p.product_id}</span>}
                            {p.shop_name && <span>• {p.shop_name}</span>}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <p className="text-gray-200 font-medium">{p.price || "-"}</p>
                          <p className="text-threads-muted">{p.sales_count || "-"}</p>
                        </td>
                        <td className="px-4 py-3 text-xs max-w-[220px]">
                          <p className="text-emerald-400 font-medium">{p.commission_amount || p.commission_rate || "-"}</p>
                          <a
                            href={p.extra_commission_url || p.affiliate_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-purple-400 hover:underline truncate block"
                            title={p.extra_commission_url || p.affiliate_url}
                          >
                            {p.extra_commission_url || p.affiliate_url}
                          </a>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          {p.is_posted ? (
                            <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 font-medium">
                              <CheckCircle className="w-3 h-3 text-emerald-400" />
                              <span>Posted ({p.post_count}x)</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-blue-950 text-blue-300 border border-blue-800 font-medium">
                              <Clock className="w-3 h-3 text-blue-400" />
                              <span>Queued</span>
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleDeleteProduct(p.id)}
                            className="p-1.5 rounded bg-rose-900/40 hover:bg-rose-800 text-rose-300 transition-colors"
                            title="Delete Product"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: LOGS & STEP TRACES */}
      {activeTab === "traces" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-threads-card border border-threads-border rounded-2xl p-5 shadow-sm space-y-3 lg:col-span-1">
            <div className="flex items-center justify-between pb-2 border-b border-threads-border">
              <div>
                <h3 className="font-bold text-white text-base">Execution History</h3>
                <p className="text-xs text-threads-muted">Select an entry to view steps & proof:</p>
              </div>
              {logs.length > 0 && (
                <button
                  onClick={handleDeleteAllLogs}
                  className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 text-xs font-semibold border border-rose-800 transition-colors"
                  title="Delete all execution logs"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear All</span>
                </button>
              )}
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {logs.length === 0 ? (
                <div className="py-12 text-center text-threads-muted text-xs">
                  No execution logs recorded yet.
                </div>
              ) : (
                logs.map((log) => (
                  <div
                    key={log.id}
                    className={`p-3 rounded-xl border transition-all flex items-center justify-between gap-2 ${
                      selectedLogDetail?.id === log.id
                        ? "bg-purple-950/40 border-purple-600 text-white"
                        : "bg-threads-dark border-threads-border text-gray-300 hover:border-gray-600"
                    }`}
                  >
                    <button
                      onClick={() => handleInspectLog(log.id)}
                      className="text-left flex-1 min-w-0"
                    >
                      <p className="font-semibold text-sm truncate">{log.product_name}</p>
                      <div className="flex items-center space-x-2 text-xs text-threads-muted mt-0.5">
                        <span>{new Date(log.created_at).toLocaleTimeString()}</span>
                        <span>•</span>
                        <span className={log.status === "success" ? "text-emerald-400 font-medium" : log.status === "failed" ? "text-rose-400 font-medium" : "text-amber-400 font-medium"}>
                          {log.status === "success" ? "Published" : log.status === "failed" ? "Failed" : "Running"}
                        </span>
                      </div>
                    </button>
                    <div className="flex items-center space-x-1">
                      {(log.threads_post_url || log.target_thread_url) && log.status === "success" && (
                        <a
                          href={log.threads_post_url || log.target_thread_url || ""}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 rounded-lg text-purple-400 hover:text-white hover:bg-purple-600/30 transition-colors"
                          title="Open Thread in New Tab"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                      <button
                        onClick={() => handleDeleteLog(log.id)}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-rose-300 hover:bg-rose-950/50 transition-colors"
                        title="Delete this log"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="bg-threads-card border border-threads-border rounded-2xl p-5 shadow-sm space-y-4 lg:col-span-2">
            {selectedLogDetail ? (
              <div className="space-y-4">
                <div className="border-b border-threads-border pb-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-white">{selectedLogDetail.product_name}</h3>
                    <div className="flex items-center space-x-2">
                      {(selectedLogDetail.threads_post_url || selectedLogDetail.target_thread_url) && selectedLogDetail.status === "success" && (
                        <a
                          href={selectedLogDetail.threads_post_url || selectedLogDetail.target_thread_url || ""}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center space-x-1 px-3 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-sm transition-colors"
                        >
                          <span>Open Thread in New Tab</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                      <button
                        onClick={() => handleDeleteLog(selectedLogDetail.id)}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 text-xs font-semibold border border-rose-800 transition-colors"
                        title="Delete this log"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Delete Log</span>
                      </button>
                      <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                        selectedLogDetail.status === "success" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-rose-950 text-rose-300 border border-rose-800"
                      }`}>
                        {selectedLogDetail.status === "success" ? "PUBLISHED" : selectedLogDetail.status === "failed" ? "FAILED" : "RUNNING"}
                      </span>
                    </div>
                  </div>

                  {selectedLogDetail.target_thread_url && (
                    <div className="text-xs flex items-center space-x-1.5 text-purple-400">
                      <Flame className="w-3.5 h-3.5 text-amber-400" />
                      <span>Target Viral Thread:</span>
                      <a
                        href={selectedLogDetail.target_thread_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline truncate hover:text-purple-300 inline-flex items-center gap-1"
                      >
                        <span className="truncate max-w-md">{selectedLogDetail.target_thread_url}</span>
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    </div>
                  )}

                  {selectedLogDetail.target_thread_snippet && (
                    <div className="bg-threads-dark p-3 rounded-xl border border-threads-border text-xs text-gray-300 italic">
                      <span className="text-amber-400 font-semibold not-italic mr-1">Thread Context:</span>
                      "{selectedLogDetail.target_thread_snippet}"
                    </div>
                  )}
                </div>

                {/* Error Banner if Failed */}
                {selectedLogDetail.error_message && (
                  <div className="bg-rose-950/60 border border-rose-800/80 rounded-xl p-4 text-rose-200 text-xs space-y-1.5 shadow-sm">
                    <div className="flex items-center space-x-2 font-bold text-rose-300">
                      <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                      <span>EXECUTION ERROR</span>
                    </div>
                    <p className="text-sm font-semibold text-white">{selectedLogDetail.error_message}</p>
                    <p className="text-[11px] text-rose-300/80">
                      Check the step-by-step breakdown below to view which step failed and inspect the screenshot.
                    </p>
                  </div>
                )}

                {/* 4 Execution Steps Timeline */}
                <div className="space-y-3 pt-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-threads-muted flex items-center justify-between">
                    <span>Bot Execution Timeline (4 Steps):</span>
                    <span className="text-[11px] font-normal lowercase text-gray-400">
                      login → find viral threads → generate post → post reply
                    </span>
                  </h4>

                  <div className="space-y-3">
                    {[
                      { key: "login", num: 1, title: "1. Login to Threads", desc: "Visit https://www.threads.com/login & verify active session" },
                      { key: "find_viral_threads", num: 2, title: "2. Find Viral Threads", desc: "Scan feed for threads matching comments or likes criteria" },
                      { key: "generate_post", num: 3, title: "3. Generate Post (AI OpenRouter)", desc: "AI matches Shopee product & crafts Indonesian affiliate comment" },
                      { key: "post_reply", num: 4, title: "4. Publish Reply", desc: "Submit reply comment to target thread and capture proof" },
                    ].map((step) => {
                      const stepLog = selectedLogDetail.steps?.find(
                        (s) => s.tool_name === step.key || s.step_number === step.num
                      );
                      const isFailed = stepLog?.tool_output?.toUpperCase().includes("GAGAL") || stepLog?.tool_output?.toUpperCase().includes("FAILED");
                      const isSuccess = stepLog && !isFailed;

                      return (
                        <div
                          key={step.num}
                          className={`rounded-xl border p-3.5 transition-all text-xs ${
                            isFailed
                              ? "bg-rose-950/25 border-rose-800/80"
                              : isSuccess
                              ? "bg-emerald-950/20 border-emerald-800/60"
                              : "bg-threads-dark/40 border-threads-border text-gray-500 opacity-60"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2.5">
                              {isFailed ? (
                                <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                              ) : isSuccess ? (
                                <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                              ) : (
                                <div className="w-4 h-4 rounded-full border border-gray-600 flex items-center justify-center text-[10px] text-gray-400 font-bold">
                                  {step.num}
                                </div>
                              )}
                              <div>
                                <span className={`font-semibold text-sm ${isFailed ? "text-rose-200" : isSuccess ? "text-emerald-200" : "text-gray-400"}`}>
                                  {step.title}
                                </span>
                                <p className="text-[11px] text-gray-400">{step.desc}</p>
                              </div>
                            </div>

                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                isFailed
                                  ? "bg-rose-900/50 text-rose-300 border-rose-700"
                                  : isSuccess
                                  ? "bg-emerald-900/50 text-emerald-300 border-emerald-700"
                                  : "bg-gray-800 text-gray-400 border-gray-700"
                              }`}
                            >
                              {isFailed ? "FAILED" : isSuccess ? "SUCCESS" : "NOT EXECUTED"}
                            </span>
                          </div>

                          {stepLog && (
                            <div className="mt-2.5 pt-2.5 border-t border-white/5 space-y-1.5">
                              {stepLog.thought && (
                                <p className="text-gray-300 italic text-[11px]">"{stepLog.thought}"</p>
                              )}
                              {stepLog.tool_output && (
                                <div className={`p-2.5 rounded-lg text-xs whitespace-pre-line font-mono ${
                                  isFailed ? "bg-rose-950/40 text-rose-300 border border-rose-900/50" : "bg-threads-dark text-gray-300 border border-threads-border/50"
                                }`}>
                                  {stepLog.tool_output}
                                </div>
                              )}
                              {stepLog.screenshot_path && (
                                <div className="pt-1">
                                  <button
                                    type="button"
                                    onClick={() => setSelectedScreenshot(getFullImageUrl(stepLog.screenshot_path))}
                                    className="inline-flex items-center space-x-1.5 text-xs text-purple-400 hover:text-purple-300 underline"
                                  >
                                    <Eye className="w-3.5 h-3.5" />
                                    <span>View Screenshot for this Step</span>
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {selectedLogDetail.post_text && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-threads-muted mb-2">
                      AI Generated Comment (Indonesian):
                    </h4>
                    <div className="bg-[#121212] rounded-xl p-4 text-sm text-gray-200 whitespace-pre-line border border-[#222]">
                      {selectedLogDetail.post_text}
                    </div>
                  </div>
                )}

                {selectedLogDetail.final_screenshot && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-threads-muted mb-2">
                      Final Browser Screenshot:
                    </h4>
                    <button
                      onClick={() => setSelectedScreenshot(getFullImageUrl(selectedLogDetail.final_screenshot))}
                      className="inline-flex items-center space-x-1.5 text-xs text-purple-400 hover:text-purple-300 underline font-medium"
                    >
                      <Eye className="w-4 h-4" />
                      <span>View Final Screenshot</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-24 text-center text-threads-muted text-sm">
                Select an execution log entry from the left list to view step-by-step traces and screenshots.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: SCHEDULING & OPENROUTER SETTINGS */}
      {activeTab === "settings" && (
        <form onSubmit={handleSaveSettings} className="space-y-6 max-w-2xl bg-threads-card border border-threads-border rounded-2xl p-6 sm:p-8 shadow-sm">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <SettingsIcon className="w-5 h-5 text-purple-400" />
            <span>Scheduling & AI Settings</span>
          </h2>

          {/* Cron Interval Window Config */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted">
              1. Continuous Automated Scheduling
            </h3>

            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="cron-toggle"
                checked={settingsForm.scheduler_enabled}
                onChange={(e) => setSettingsForm({ ...settingsForm, scheduler_enabled: e.target.checked })}
                className="w-4 h-4 rounded text-purple-600 focus:ring-purple-500 bg-threads-dark border-threads-border"
              />
              <label htmlFor="cron-toggle" className="text-sm font-medium text-gray-200 cursor-pointer">
                Enable Automated Auto-Commenting
              </label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Time Window (Minutes)</label>
                <input
                  type="number"
                  min="1"
                  value={settingsForm.scheduler_window_minutes}
                  onChange={(e) =>
                    setSettingsForm({
                      ...settingsForm,
                      scheduler_window_minutes: e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Posts per Window</label>
                <input
                  type="number"
                  min="1"
                  value={settingsForm.scheduler_posts_per_window}
                  onChange={(e) =>
                    setSettingsForm({
                      ...settingsForm,
                      scheduler_posts_per_window: e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            <div className="bg-purple-950/40 border border-purple-800/60 rounded-xl p-3 text-xs text-purple-200 flex items-center space-x-2">
              <Clock className="w-4 h-4 text-purple-400 flex-shrink-0" />
              <span>
                Calculation: Bot will post a comment every <strong>{calculatedInterval} minutes</strong> ({settingsForm.scheduler_posts_per_window || 0} posts per {settingsForm.scheduler_window_minutes || 0} minutes).
              </span>
            </div>
          </div>

          {/* Viral Thread Criteria */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted flex items-center space-x-1.5">
              <Flame className="w-4 h-4 text-amber-400" />
              <span>2. Viral Thread Criteria</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Minimum Thread Comments</label>
                <input
                  type="number"
                  min="1"
                  value={settingsForm.min_thread_comments}
                  onChange={(e) =>
                    setSettingsForm({
                      ...settingsForm,
                      min_thread_comments: e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                />
                <p className="text-[11px] text-threads-muted mt-1">
                  Target thread if comments ≥ {settingsForm.min_thread_comments || 0}
                </p>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Minimum Thread Likes</label>
                <input
                  type="number"
                  min="1"
                  value={settingsForm.min_thread_likes}
                  onChange={(e) =>
                    setSettingsForm({
                      ...settingsForm,
                      min_thread_likes: e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                />
                <p className="text-[11px] text-threads-muted mt-1">
                  Target thread if likes ≥ {settingsForm.min_thread_likes || 0}
                </p>
              </div>
            </div>

            <p className="text-[11px] text-purple-300 bg-purple-950/40 p-2.5 rounded-lg border border-purple-800/40 leading-relaxed">
              💡 <strong>Logic Rule:</strong> The bot will comment on a thread if <strong>EITHER condition is met</strong> (Comments ≥ {settingsForm.min_thread_comments || 0} <em>OR</em> Likes ≥ {settingsForm.min_thread_likes || 0}) and has not been commented on before.
            </p>
          </div>

          {/* OpenRouter Config */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted">
              3. OpenRouter AI (Free Tier)
            </h3>

            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                OpenRouter API Key {settings?.openrouter_api_key_set && <span className="text-emerald-400 font-semibold">(Saved)</span>}
              </label>
              <input
                type="password"
                placeholder="sk-or-v1-..."
                value={settingsForm.openrouter_api_key}
                onChange={(e) => setSettingsForm({ ...settingsForm, openrouter_api_key: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
              />
              <p className="text-[11px] text-threads-muted mt-1">
                Get a free API Key at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-purple-400 underline">openrouter.ai/keys</a>
              </p>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Model Identifier</label>
              <input
                type="text"
                value={settingsForm.openrouter_model}
                onChange={(e) => setSettingsForm({ ...settingsForm, openrouter_model: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500 font-mono text-xs"
              />
              <p className="text-[11px] text-threads-muted mt-1">
                Default: <code className="text-purple-300">openrouter/free</code> (auto-routes to best free tier model).
              </p>
            </div>
          </div>

          {/* Section 4: Threads Authentication via sessionID */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-400" />
                4. Meta Threads Authentication (sessionID)
              </h3>
              <div>
                {settings?.threads_session_id_set ? (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle className="w-3.5 h-3.5 mr-1" /> sessionID Active
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    <AlertTriangle className="w-3.5 h-3.5 mr-1" /> No sessionID Configured
                  </span>
                )}
              </div>
            </div>

            {/* Primary: sessionID Cookie Input */}
            <div className="bg-purple-950/20 border border-purple-800/30 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-purple-200">
                  Threads <code>sessionid</code> Cookie Value{" "}
                  {settings?.threads_session_id_set && (
                    <span className="text-emerald-400 font-semibold">(Saved in Database)</span>
                  )}
                </label>
              </div>

              <div className="relative">
                <input
                  type={showThreadsSessionId ? "text" : "password"}
                  placeholder={
                    settings?.threads_session_id_set
                      ? "Leave blank to keep current sessionID, or paste new sessionID to replace"
                      : "Paste your sessionid cookie here (e.g. 768291...%3A...)"
                  }
                  value={settingsForm.threads_session_id}
                  onChange={(e) => setSettingsForm({ ...settingsForm, threads_session_id: e.target.value })}
                  className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-threads-dark border border-purple-700/50 text-white text-sm focus:outline-none focus:border-purple-400 font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={() => setShowThreadsSessionId(!showThreadsSessionId)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-threads-muted hover:text-white transition-colors focus:outline-none p-1"
                  title={showThreadsSessionId ? "Hide sessionID" : "Show sessionID"}
                >
                  {showThreadsSessionId ? (
                    <EyeOff className="w-4 h-4 text-purple-400" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>

              <div className="bg-threads-dark/70 rounded-lg p-3 text-[11px] text-gray-300 leading-relaxed border border-threads-border space-y-1.5">
                <p className="font-semibold text-purple-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" /> How to copy your <code>sessionid</code> in 10 seconds:
                </p>
                <ol className="list-decimal list-inside space-y-1 text-gray-400 pl-1">
                  <li>Open <a href="https://www.threads.net" target="_blank" rel="noopener noreferrer" className="text-purple-400 underline">threads.net</a> in Chrome/Edge on your PC where you are already logged in.</li>
                  <li>Press <kbd className="px-1.5 py-0.5 bg-gray-800 rounded border border-gray-700 text-[10px] text-white">F12</kbd> (Developer Tools) and click the <strong>Application</strong> tab (or <strong>Storage</strong> in Firefox).</li>
                  <li>In the left sidebar, expand <strong>Cookies</strong> &rarr; click <code>https://www.threads.net</code>.</li>
                  <li>Find the cookie named <strong>sessionid</strong>, double-click its <strong>Value</strong> to copy, and paste it into the field above.</li>
                </ol>
                <p className="text-emerald-400/90 text-[11px] pt-1">
                  ✨ <strong>Why this is best for VPS:</strong> Using <code>sessionid</code> bypasses datacenter IP checkpoints, login captchas, and 2FA locks completely.
                </p>
              </div>
            </div>

            {/* Optional Fallback: Username & Password */}
            <div className="pt-2">
              <p className="text-xs text-threads-muted mb-3 font-medium">
                Fallback Credentials (Optional — used only if sessionID is not configured)
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Username / Email</label>
                  <input
                    type="text"
                    placeholder="username_threads"
                    value={settingsForm.threads_username}
                    onChange={(e) => setSettingsForm({ ...settingsForm, threads_username: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">
                    Password {settings?.threads_password_set && <span className="text-emerald-400">(Saved)</span>}
                  </label>
                  <div className="relative">
                    <input
                      type={showThreadsPassword ? "text" : "password"}
                      placeholder="Leave blank to keep existing password"
                      value={settingsForm.threads_password}
                      onChange={(e) => setSettingsForm({ ...settingsForm, threads_password: e.target.value })}
                      className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowThreadsPassword(!showThreadsPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-threads-muted hover:text-white transition-colors focus:outline-none p-1"
                      title={showThreadsPassword ? "Hide password" : "Show password"}
                    >
                      {showThreadsPassword ? (
                        <EyeOff className="w-4 h-4 text-purple-400" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Active Session State & Export Actions */}
            {settings?.session_file_exists && (
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 bg-threads-dark/40 p-3 rounded-lg border border-threads-border/60 text-xs">
                <span className="text-gray-400 flex items-center gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                  Synced storage state file exists on disk (<code>threads_session.json</code>)
                </span>
                <div className="flex items-center gap-2">
                  <a
                    href={`/api/settings/export-session?admin_key=${encodeURIComponent(adminKey)}`}
                    download="threads_session.json"
                    className="px-2.5 py-1 bg-threads-border hover:bg-threads-dark text-white rounded text-[11px] flex items-center gap-1 transition-colors border border-gray-700"
                  >
                    <Download className="w-3 h-3 text-purple-400" />
                    Export JSON
                  </a>
                  <button
                    type="button"
                    disabled={sessionDeleting}
                    onClick={handleDeleteSession}
                    className="px-2.5 py-1 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded text-[11px] flex items-center gap-1 transition-colors border border-red-800/40"
                  >
                    <Trash2 className="w-3 h-3" />
                    {sessionDeleting ? "Deleting..." : "Reset Session"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Section 5: Indonesian / Regional Proxy Routing */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted flex items-center gap-2">
              <Globe className="w-4 h-4 text-purple-400" />
              5. Regional Proxy Routing (Indonesian IP)
            </h3>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                Proxy URL (Optional - HTTP / HTTPS / SOCKS5)
              </label>
              <input
                type="text"
                placeholder="http://username:password@proxy-ip:port or socks5://host:port"
                value={settingsForm.proxy_url}
                onChange={(e) => setSettingsForm({ ...settingsForm, proxy_url: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500 font-mono text-xs"
              />
              <p className="text-[11px] text-threads-muted mt-1.5 leading-relaxed">
                If your VPS is located outside Indonesia (e.g. Singapore, Taiwan, US) and you wish to post from an Indonesian IP address, supply an Indonesian residential or mobile proxy URL here. The Playwright browser will route all network traffic through this proxy while enforcing Jakarta timezone, geolocation, and Indonesian headers.
              </p>
            </div>
          </div>

          {/* Section 6: Admin Portal Passcode */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted">
              6. Admin Portal Security
            </h3>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                Admin Passcode <span className="text-emerald-400 font-semibold">(Stored in Database)</span>
              </label>
              <div className="relative">
                <input
                  type={showNewAdminPasscode ? "text" : "password"}
                  placeholder="Leave blank to keep current passcode"
                  value={settingsForm.admin_passcode}
                  onChange={(e) => setSettingsForm({ ...settingsForm, admin_passcode: e.target.value })}
                  className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-threads-dark border border-threads-border text-white text-sm focus:outline-none focus:border-purple-500"
                />
                <button
                  type="button"
                  onClick={() => setShowNewAdminPasscode(!showNewAdminPasscode)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-threads-muted hover:text-white transition-colors focus:outline-none p-1"
                  title={showNewAdminPasscode ? "Hide passcode" : "Show passcode"}
                >
                  {showNewAdminPasscode ? (
                    <EyeOff className="w-4 h-4 text-purple-400" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              <p className="text-[11px] text-purple-300 bg-purple-950/40 p-2.5 rounded-lg border border-purple-800/40 mt-2 leading-relaxed">
                🔒 <strong>100% Database Driven:</strong> All configurations (passcodes, API keys, intervals, thresholds) are stored in the SQLite database without requiring <code>.env</code> file edits. Screenshots are saved as Base64 in the database with zero raw files on disk.
              </p>
            </div>
          </div>

          {/* Section 7: Headless Toggle */}
          <div className="space-y-4 border-b border-threads-border pb-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-threads-muted">
              7. Browser Automation Engine
            </h3>
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="headless-toggle"
                checked={settingsForm.headless_browser}
                onChange={(e) => setSettingsForm({ ...settingsForm, headless_browser: e.target.checked })}
                className="w-4 h-4 rounded text-purple-600 focus:ring-purple-500 bg-threads-dark border-threads-border"
              />
              <label htmlFor="headless-toggle" className="text-sm text-gray-200 cursor-pointer">
                Headless Browser (run without opening visible browser window)
              </label>
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-sm transition-colors shadow-md"
          >
            Save Settings & Update Schedule
          </button>
        </form>
      )}

      {/* Screenshot Modal */}
      {selectedScreenshot && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setSelectedScreenshot(null)}
        >
          <div
            className="bg-threads-card border border-threads-border rounded-2xl max-w-4xl w-full p-4 overflow-hidden shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-threads-border mb-3">
              <h3 className="text-sm font-semibold text-white">Browser Screenshot Proof</h3>
              <button
                onClick={() => setSelectedScreenshot(null)}
                className="text-gray-400 hover:text-white text-sm px-2 py-1 rounded-md"
              >
                ✕ Close
              </button>
            </div>
            <div className="overflow-auto max-h-[75vh] flex justify-center bg-black rounded-lg">
              <img src={selectedScreenshot} alt="Comment Proof Screenshot" className="object-contain" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

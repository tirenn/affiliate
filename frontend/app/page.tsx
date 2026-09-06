"use client";

import { useEffect, useState } from "react";
import { fetchPublicLogs, PostLog, getFullImageUrl } from "@/lib/api";
import { Search, ExternalLink, RefreshCw, CheckCircle2, XCircle, Clock, Image as ImageIcon, Sparkles } from "lucide-react";

export default function PublicHistoryPage() {
  const [logs, setLogs] = useState<PostLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedScreenshot, setSelectedScreenshot] = useState<string | null>(null);

  const loadLogs = async (query = search) => {
    try {
      setLoading(true);
      const data = await fetchPublicLogs(query);
      setLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs("");
    const interval = setInterval(() => loadLogs(search), 15000); // Polling every 15s
    return () => clearInterval(interval);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadLogs(search);
  };

  const successCount = logs.filter((l) => l.status === "success").length;
  const runningCount = logs.filter((l) => l.status === "running").length;

  return (
    <div className="space-y-8">
      {/* Hero Banner */}
      <div className="relative rounded-2xl bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-black p-6 sm:p-8 border border-threads-border overflow-hidden">
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-xs font-semibold text-purple-300">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Autonomous Activity Feed</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Threads Affiliate Feed
          </h1>
          <p className="text-sm sm:text-base text-gray-400">
            Real-time public log of AI-generated product promotions published directly to Meta Threads with affiliate attribution.
          </p>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-threads-card border border-threads-border rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-threads-muted">Total Posts</span>
            <CheckCircle2 className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-2xl sm:text-3xl font-bold mt-2 text-white">{logs.length}</p>
          <span className="text-xs text-threads-muted">Historical recorded entries</span>
        </div>

        <div className="bg-threads-card border border-threads-border rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-threads-muted">Published Live</span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>
          <p className="text-2xl sm:text-3xl font-bold mt-2 text-emerald-400">{successCount}</p>
          <span className="text-xs text-threads-muted">Confirmed on Threads</span>
        </div>

        <div className="bg-threads-card border border-threads-border rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-threads-muted">Current Status</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-xl sm:text-2xl font-bold mt-2 text-white">
            {runningCount > 0 ? (
              <span className="text-amber-400 flex items-center gap-2">
                <span className="animate-spin text-sm">⏳</span> Agent Posting...
              </span>
            ) : (
              <span className="text-gray-300">Idle / Ready</span>
            )}
          </p>
          <span className="text-xs text-threads-muted">Autonomous Playwright runner</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <form onSubmit={handleSearch} className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by product name or keywords..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-threads-card border border-threads-border text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
          />
        </form>

        <button
          onClick={() => loadLogs()}
          disabled={loading}
          className="inline-flex items-center justify-center space-x-2 px-4 py-2.5 rounded-xl bg-threads-card border border-threads-border text-sm font-medium text-gray-300 hover:text-white hover:bg-threads-border transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Feed Cards */}
      {loading && logs.length === 0 ? (
        <div className="py-16 text-center text-gray-500 space-y-3">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-sm">Loading affiliate history...</p>
        </div>
      ) : logs.length === 0 ? (
        <div className="py-20 text-center bg-threads-card rounded-2xl border border-threads-border p-8">
          <p className="text-gray-300 font-medium text-lg">No affiliate posts recorded yet</p>
          <p className="text-gray-500 text-sm mt-1">
            Posts will appear here automatically when the bot runs through the CSV queue.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {logs.map((log) => (
            <div
              key={log.id}
              className="bg-threads-card border border-threads-border hover:border-gray-700 transition-all rounded-2xl p-5 sm:p-6 space-y-4 shadow-sm"
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-threads-border pb-3">
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">{log.product_name}</h2>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-threads-muted mt-1">
                    <span>{new Date(log.created_at).toLocaleString()}</span>
                    <span>•</span>
                    <a
                      href={log.extra_commission_url || log.affiliate_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-purple-400 hover:text-purple-300 inline-flex items-center gap-1 truncate max-w-xs"
                    >
                      <span className="truncate">Extra Commission Link</span>
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    </a>

                    {log.target_thread_url && (
                      <>
                        <span>•</span>
                        <a
                          href={log.target_thread_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-amber-400 hover:text-amber-300 inline-flex items-center gap-1 truncate max-w-xs"
                        >
                          <span>Target Viral Thread</span>
                          <ExternalLink className="w-3 h-3 flex-shrink-0" />
                        </a>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  {log.status === "success" && (
                    <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Published</span>
                    </span>
                  )}
                  {log.status === "running" && (
                    <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950 text-amber-300 border border-amber-800 animate-pulse">
                      <Clock className="w-3.5 h-3.5 text-amber-400" />
                      <span>Processing</span>
                    </span>
                  )}
                  {log.status === "failed" && (
                    <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-950 text-rose-300 border border-rose-800">
                      <XCircle className="w-3.5 h-3.5 text-rose-400" />
                      <span>Failed</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Context Thread Snippet if present */}
              {log.target_thread_snippet && (
                <div className="bg-threads-dark/70 border border-threads-border/70 rounded-xl p-3 text-xs text-gray-400 italic">
                  <span className="text-amber-400 font-semibold not-italic mr-1">Thread Context:</span>
                  "{log.target_thread_snippet}"
                </div>
              )}

              {/* Card Body: Post Text */}
              {log.post_text ? (
                <div className="bg-[#121212] rounded-xl p-4 text-sm text-gray-200 whitespace-pre-line border border-[#222] font-sans leading-relaxed">
                  {log.post_text}
                </div>
              ) : (
                <p className="text-xs text-threads-muted italic">Drafting comment...</p>
              )}

              {/* Card Footer: Links & Screenshots */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex items-center space-x-3">
                  {log.threads_post_url && (
                    <a
                      href={log.threads_post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center space-x-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition-colors"
                    >
                      <span>View on Threads</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}

                  {log.final_screenshot && (
                    <button
                      onClick={() => setSelectedScreenshot(getFullImageUrl(log.final_screenshot))}
                      className="inline-flex items-center space-x-1 text-xs text-gray-400 hover:text-white px-2.5 py-1.5 rounded-lg bg-threads-border/50 hover:bg-threads-border transition-colors"
                    >
                      <ImageIcon className="w-3.5 h-3.5" />
                      <span>Screenshot</span>
                    </button>
                  )}
                </div>

                {log.error_message && (
                  <p className="text-xs text-rose-400 truncate max-w-md" title={log.error_message}>
                    Error: {log.error_message}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Screenshot Preview Modal */}
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
              <h3 className="text-sm font-semibold text-white">Browser Screenshot</h3>
              <button
                onClick={() => setSelectedScreenshot(null)}
                className="text-gray-400 hover:text-white text-sm px-2 py-1 rounded-md"
              >
                ✕ Close
              </button>
            </div>
            <div className="overflow-auto max-h-[75vh] flex justify-center bg-black rounded-lg">
              <img src={selectedScreenshot} alt="Browser Step Screenshot" className="object-contain" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

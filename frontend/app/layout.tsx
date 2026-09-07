import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Threads Affiliate Bot - Post History & Admin",
  description: "Autonomous LLM + Playwright Affiliate Marketing on Meta Threads",
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-threads-dark text-threads-text min-h-screen flex flex-col">
        {/* Navigation Header */}
        <header className="sticky top-0 z-40 w-full border-b border-threads-border bg-threads-dark/80 backdrop-blur-md">
          <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-purple-600 via-pink-500 to-amber-400 flex items-center justify-center font-bold text-white shadow-lg text-lg">
                @
              </div>
              <div>
                <span className="font-bold text-lg tracking-tight">Threads Affiliate</span>
                <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-purple-900/50 text-purple-300 border border-purple-700/50">
                  Agentic Bot
                </span>
              </div>
            </div>

            <nav className="flex items-center space-x-2 sm:space-x-4 text-sm font-medium">
              <Link
                href="/"
                className="px-3.5 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-threads-card transition-colors"
              >
                Public Logs
              </Link>
              <Link
                href="/admin"
                className="px-3.5 py-2 rounded-lg bg-threads-card text-white hover:bg-threads-border border border-threads-border transition-all flex items-center space-x-1.5 shadow-sm"
              >
                <span>Admin Portal</span>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              </Link>
            </nav>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-8">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t border-threads-border py-6 text-center text-xs text-threads-muted">
          <p>Powered by FastAPI • SQLite • Playwright • Agentic LLM • Next.js</p>
        </footer>
      </body>
    </html>
  );
}

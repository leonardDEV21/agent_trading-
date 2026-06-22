import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Kronos Alpha Terminal",
  description: "Local-first AI-assisted trading research terminal (paper/research only).",
};

const nav = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/forecasts", label: "Forecasts" },
  { href: "/signals", label: "Signals" },
  { href: "/backtests", label: "Backtests" },
  { href: "/paper", label: "Paper" },
  { href: "/assets", label: "Assets" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-mono">
        <Providers>
          <div className="min-h-screen flex flex-col">
            <header className="border-b border-base-border bg-base-panel/60 backdrop-blur sticky top-0 z-10">
              <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
                <Link href="/dashboard" className="font-bold text-accent">
                  KRONOS<span className="text-gray-400"> · ALPHA TERMINAL</span>
                </Link>
                <nav className="flex gap-1 text-sm">
                  {nav.map((n) => (
                    <Link key={n.href} href={n.href} className="px-3 py-1.5 rounded hover:bg-base-border/40">
                      {n.label}
                    </Link>
                  ))}
                </nav>
                <span className="ml-auto badge bg-accent-warn/20 text-accent-warn">
                  PAPER / RESEARCH — NO LIVE TRADING
                </span>
              </div>
            </header>
            <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">{children}</main>
            <footer className="border-t border-base-border text-xs text-gray-500 px-4 py-3 text-center">
              Not financial advice. Forecasts are probabilistic and may be mock output. Verify mode on every chart.
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}

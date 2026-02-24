import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradePilot",
  description: "Professional-grade AI trade plan generator",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-bg-primary">
        <nav className="border-b border-border-primary bg-bg-secondary/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-14">
              <div className="flex items-center gap-8">
                <h1 className="text-lg font-bold tracking-tight">
                  <span className="text-accent-blue">Trade</span>
                  <span className="text-text-primary">Pilot</span>
                </h1>
                <div className="flex gap-1">
                  <NavLink href="/" label="Dashboard" />
                  <NavLink href="/analyze" label="Analyze" />
                  <NavLink href="/journal" label="Journal" />
                  <NavLink href="/performance" label="Performance" />
                </div>
              </div>
              <div id="session-status" className="text-xs text-text-muted font-mono">
                No active session
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover rounded-md transition-colors"
    >
      {label}
    </a>
  );
}

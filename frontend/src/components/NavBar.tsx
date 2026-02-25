"use client";

import { useSession } from "@/components/SessionProvider";
import { usePathname } from "next/navigation";
import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/plans", label: "Plans" },
  { href: "/chat", label: "Chat" },
  { href: "/performance", label: "Performance" },
];

export default function NavBar() {
  const { isActive, sessionId, endSession } = useSession();
  const pathname = usePathname();

  return (
    <nav className="border-b border-border-primary bg-bg-secondary/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-8">
            <Link href="/" className="text-lg font-bold tracking-tight">
              <span className="text-accent-blue">Trade</span>
              <span className="text-text-primary">Pilot</span>
            </Link>
            <div className="flex gap-1">
              {NAV_ITEMS.map(({ href, label }) => {
                const isActive =
                  href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                      isActive
                        ? "text-text-primary bg-bg-hover font-medium"
                        : "text-text-secondary hover:text-text-primary hover:bg-bg-hover"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Session indicator */}
          <div className="flex items-center gap-3">
            {isActive ? (
              <>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
                  <span className="text-xs text-text-muted font-mono">
                    Session Active
                  </span>
                </div>
                <button
                  onClick={endSession}
                  className="text-xs text-text-muted hover:text-accent-red transition-colors"
                  title="End current session"
                >
                  End
                </button>
              </>
            ) : (
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-text-muted" />
                <span className="text-xs text-text-muted font-mono">
                  No session
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

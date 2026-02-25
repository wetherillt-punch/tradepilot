"use client";

import { useState } from "react";
import { useSession } from "@/components/SessionProvider";
import Link from "next/link";

export default function PlansPage() {
  const { isActive } = useSession();
  const [view, setView] = useState<"today" | "history">("today");

  // Session gate
  if (!isActive) {
    return (
      <div className="bg-bg-secondary border border-border-primary rounded-lg p-8 text-center">
        <h2 className="text-xl font-semibold mb-2">No Active Session</h2>
        <p className="text-text-secondary text-sm mb-6">
          Initialize a session on the Dashboard to start generating trade plans.
        </p>
        <Link
          href="/"
          className="px-6 py-2.5 bg-accent-blue hover:bg-accent-blue/80 text-white font-medium rounded-lg transition-colors inline-block"
        >
          Go to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in">
      {/* View Toggle + Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold">Plans</h2>
          <div className="flex bg-bg-secondary rounded-lg p-0.5 border border-border-primary">
            <button
              onClick={() => setView("today")}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                view === "today"
                  ? "bg-bg-hover text-text-primary font-medium"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Today
            </button>
            <button
              onClick={() => setView("history")}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                view === "history"
                  ? "bg-bg-hover text-text-primary font-medium"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              History
            </button>
          </div>
        </div>
        <button className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary border border-border-primary hover:border-border-hover rounded-lg transition-colors">
          + Manual
        </button>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex gap-2">
        {["All", "Watching", "Entered", "Exited", "Cancelled"].map((tab) => (
          <button
            key={tab}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              tab === "All"
                ? "bg-accent-blue/20 text-accent-blue"
                : "bg-bg-secondary text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Empty State */}
      {view === "today" ? (
        <div className="bg-bg-secondary border border-border-primary rounded-lg p-12 text-center">
          <div className="text-3xl mb-3">📋</div>
          <h3 className="text-lg font-medium mb-2">No Plans Yet</h3>
          <p className="text-text-secondary text-sm mb-6">
            Scan your watchlist on the Dashboard to generate your first trade plan.
          </p>
          <Link
            href="/"
            className="px-4 py-2 bg-accent-blue hover:bg-accent-blue/80 text-white text-sm font-medium rounded-lg transition-colors inline-block"
          >
            Go to Dashboard
          </Link>
        </div>
      ) : (
        <div className="bg-bg-secondary border border-border-primary rounded-lg p-12 text-center">
          <div className="text-3xl mb-3">📅</div>
          <h3 className="text-lg font-medium mb-2">No History Yet</h3>
          <p className="text-text-secondary text-sm">
            Your trading history will appear here after your first completed plan.
          </p>
        </div>
      )}
    </div>
  );
}

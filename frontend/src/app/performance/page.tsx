"use client";

import { useState, useEffect } from "react";
import api, { PerformanceStats } from "@/lib/api";

export default function PerformancePage() {
  const [stats, setStats] = useState<PerformanceStats | null>(null);
  const [digest, setDigest] = useState<string | null>(null);
  const [period, setPeriod] = useState(30);
  const [loading, setLoading] = useState(true);
  const [digestLoading, setDigestLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStats();
  }, [period]);

  const loadStats = async () => {
    setLoading(true);
    try {
      const res = await api.getPerformance(period);
      setStats(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const generateDigest = async () => {
    setDigestLoading(true);
    try {
      const res = await api.getWeeklyDigest();
      setDigest(res.digest);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDigestLoading(false);
    }
  };

  if (loading) {
    return <p className="text-text-muted text-sm text-center py-12">Loading performance data...</p>;
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Performance</h2>
        <div className="flex gap-2">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                period === d ? "bg-accent-blue text-white" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {!stats || stats.total_trades === 0 ? (
        <div className="text-center py-12 bg-bg-secondary border border-border-primary rounded-lg">
          <p className="text-text-muted text-sm">No trades in the last {period} days.</p>
          <p className="text-xs text-text-muted mt-1">Log trades in the Journal to see performance stats.</p>
        </div>
      ) : (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total Trades" value={stats.total_trades.toString()} />
            <StatCard
              label="Win Rate"
              value={`${stats.win_rate}%`}
              color={stats.win_rate >= 55 ? "green" : stats.win_rate >= 45 ? "amber" : "red"}
            />
            <StatCard
              label="Total P/L"
              value={`${stats.total_pnl_pct >= 0 ? "+" : ""}${stats.total_pnl_pct}%`}
              color={stats.total_pnl_pct >= 0 ? "green" : "red"}
            />
            <StatCard
              label="Profit Factor"
              value={stats.profit_factor === Infinity ? "∞" : stats.profit_factor.toFixed(2)}
              color={stats.profit_factor >= 1.5 ? "green" : stats.profit_factor >= 1 ? "amber" : "red"}
            />
          </div>

          {/* Win/Loss Detail */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Avg Win" value={`+${stats.avg_win}%`} color="green" />
            <StatCard label="Avg Loss" value={`${stats.avg_loss}%`} color="red" />
            <StatCard label="Best Trade" value={`+${stats.best_trade}%`} color="green" />
            <StatCard label="Worst Trade" value={`${stats.worst_trade}%`} color="red" />
          </div>

          {/* Setup Breakdown */}
          {Object.keys(stats.setup_breakdown).length > 0 && (
            <div className="bg-bg-secondary border border-border-primary rounded-lg p-5">
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-4">By Setup Type</h3>
              <div className="space-y-3">
                {Object.entries(stats.setup_breakdown).map(([setup, data]) => {
                  const total = data.wins + data.losses;
                  const wr = total > 0 ? (data.wins / total) * 100 : 0;
                  return (
                    <div key={setup} className="flex items-center gap-4">
                      <span className="text-sm font-mono text-text-primary w-40 truncate">{setup}</span>
                      <div className="flex-1 h-2 bg-bg-primary rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${wr >= 55 ? "bg-accent-green" : wr >= 45 ? "bg-accent-amber" : "bg-accent-red"}`}
                          style={{ width: `${wr}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-text-secondary w-16 text-right">
                        {wr.toFixed(0)}% ({total})
                      </span>
                      <span className={`text-xs font-mono w-16 text-right ${
                        data.total_pnl >= 0 ? "text-accent-green" : "text-accent-red"
                      }`}>
                        {data.total_pnl >= 0 ? "+" : ""}{data.total_pnl.toFixed(1)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Weekly Digest */}
          <div className="bg-bg-secondary border border-border-primary rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider">AI Performance Review</h3>
              <button
                onClick={generateDigest}
                disabled={digestLoading}
                className="px-4 py-1.5 text-xs bg-accent-purple hover:bg-accent-purple/80 text-white rounded-md transition-colors disabled:opacity-50"
              >
                {digestLoading ? "Analyzing..." : "Generate Weekly Digest"}
              </button>
            </div>
            {digest ? (
              <pre className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">{digest}</pre>
            ) : (
              <p className="text-sm text-text-muted">Click the button to generate an AI-powered analysis of your recent trading patterns.</p>
            )}
          </div>
        </>
      )}

      {error && <p className="text-accent-red text-sm">{error}</p>}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  const c = color === "green" ? "text-accent-green" : color === "red" ? "text-accent-red" : color === "amber" ? "text-accent-amber" : "text-text-primary";
  return (
    <div className="bg-bg-secondary border border-border-primary rounded-lg p-4">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`text-xl font-bold font-mono ${c}`}>{value}</div>
    </div>
  );
}

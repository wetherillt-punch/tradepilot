"use client";

import { useState } from "react";
import api, { SessionResponse, AnalysisResponse } from "@/lib/api";

export default function Dashboard() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [ticker, setTicker] = useState("");
  const [direction, setDirection] = useState("bullish");
  const [tradeType, setTradeType] = useState("swing");
  const [analyzing, setAnalyzing] = useState(false);

  const initSession = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.initSession([]);
      setSession(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const quickAnalyze = async () => {
    if (!ticker.trim()) return;
    setAnalyzing(true);
    setError(null);
    try {
      const res = await api.analyzeQuick(ticker.trim(), tradeType, direction);
      setAnalysis(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in">
      {/* Session Init */}
      {!session ? (
        <div className="bg-bg-secondary border border-border-primary rounded-lg p-8 text-center">
          <h2 className="text-xl font-semibold mb-2">Start Your Trading Day</h2>
          <p className="text-text-secondary text-sm mb-6">
            Initialize a session to analyze market regime, catalysts, and generate trade plans.
          </p>
          <button
            onClick={initSession}
            disabled={loading}
            className="px-6 py-2.5 bg-accent-blue hover:bg-accent-blue/80 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? "Initializing... (fetching market data)" : "Initialize Session"}
          </button>
          {error && <p className="text-accent-red text-sm mt-4">{error}</p>}
        </div>
      ) : (
        <>
          {/* Market Regime Panel */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-bg-secondary border border-border-primary rounded-lg p-4">
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Market Regime</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">SPY</span>
                  <span className="text-sm font-mono">{session.regime.spy}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">QQQ</span>
                  <span className="text-sm font-mono">{session.regime.qqq}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">Bias</span>
                  <span className={`text-sm font-mono ${
                    session.regime.bias === "bullish" ? "text-accent-green" :
                    session.regime.bias === "bearish" ? "text-accent-red" : "text-accent-amber"
                  }`}>
                    {session.regime.bias.toUpperCase()}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-bg-secondary border border-border-primary rounded-lg p-4">
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Volatility</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">VIX</span>
                  <span className={`text-sm font-mono ${
                    session.regime.vix > 25 ? "text-accent-red" :
                    session.regime.vix > 18 ? "text-accent-amber" : "text-accent-green"
                  }`}>
                    {session.regime.vix}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">Percentile</span>
                  <span className="text-sm font-mono">{session.regime.vix_percentile}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">Regime</span>
                  <span className="text-sm font-mono">{session.regime.volatility}</span>
                </div>
              </div>
            </div>

            <div className="bg-bg-secondary border border-border-primary rounded-lg p-4">
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Catalysts</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">Earnings</span>
                  <span className="text-sm font-mono">{session.catalysts.earnings_count} this week</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">Event Risk</span>
                  <span className={`text-sm font-mono ${
                    session.catalysts.event_risk === "extreme" ? "text-accent-red" :
                    session.catalysts.event_risk === "high" ? "text-accent-amber" : "text-text-primary"
                  }`}>
                    {session.catalysts.event_risk.toUpperCase()}
                  </span>
                </div>
                {session.catalysts.earnings.filter(e => e.bellwether).slice(0, 3).map(e => (
                  <div key={e.ticker} className="text-xs text-accent-amber">
                    ⚡ {e.ticker} reports {e.date}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Analyze */}
          <div className="bg-bg-secondary border border-border-primary rounded-lg p-6">
            <h3 className="text-sm font-medium text-text-primary mb-4">Quick Analysis</h3>
            <div className="flex gap-3 items-end">
              <div>
                <label className="text-xs text-text-muted block mb-1">Ticker</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="NVDA"
                  className="w-28 px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
                />
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Direction</label>
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  className="px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
                >
                  <option value="bullish">Bullish</option>
                  <option value="bearish">Bearish</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-text-muted block mb-1">Type</label>
                <select
                  value={tradeType}
                  onChange={(e) => setTradeType(e.target.value)}
                  className="px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
                >
                  <option value="swing">Swing</option>
                  <option value="day_trade">Day Trade</option>
                </select>
              </div>
              <button
                onClick={quickAnalyze}
                disabled={analyzing || !ticker.trim()}
                className="px-5 py-2 bg-accent-blue hover:bg-accent-blue/80 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50"
              >
                {analyzing ? "Analyzing..." : "Generate Plan"}
              </button>
            </div>
            {error && <p className="text-accent-red text-sm mt-3">{error}</p>}
          </div>

          {/* Trade Plan Output */}
          {analysis && (
            <div className="bg-bg-secondary border border-border-primary rounded-lg p-6 animate-in space-y-6">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold font-mono">{analysis.plan.ticker}</h2>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    analysis.plan.direction === "bullish" ? "badge-bullish" : "badge-bearish"
                  }`}>
                    {analysis.plan.direction.toUpperCase()}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-bg-tertiary text-text-secondary">
                    {analysis.plan.trade_type === "day_trade" ? "Day Trade" : "Swing"}
                  </span>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-bold font-mono ${
                    analysis.confidence.composite >= 65 ? "confidence-a" :
                    analysis.confidence.composite >= 50 ? "confidence-c" : "confidence-f"
                  }`}>
                    {analysis.confidence.composite.toFixed(0)}
                  </div>
                  <div className="text-xs text-text-muted">{analysis.confidence.rating}</div>
                </div>
              </div>

              {/* Thesis */}
              <div>
                <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Thesis</h4>
                <p className="text-sm text-text-primary leading-relaxed">{analysis.plan.thesis}</p>
              </div>

              {/* Levels */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <LevelCard label="Entry" value={analysis.plan.entry_zone} />
                <LevelCard label="Stop Loss" value={`$${analysis.plan.stop_loss}`} color="red" />
                {analysis.plan.targets.map((t, i) => (
                  <LevelCard
                    key={i}
                    label={`Target ${i + 1} (${t.pct_exit}%)`}
                    value={`$${t.price}`}
                    color="green"
                  />
                ))}
              </div>

              {/* R:R */}
              <div className="flex gap-6 text-sm">
                <div>
                  <span className="text-text-muted">R:R</span>{" "}
                  <span className="font-mono font-medium">{analysis.plan.risk_reward_ratio.toFixed(1)}:1</span>
                </div>
                <div>
                  <span className="text-text-muted">Setup</span>{" "}
                  <span className="font-mono">{analysis.plan.setup_type}</span>
                </div>
              </div>

              {/* Thesis Invalidation */}
              <div className="bg-accent-red/5 border border-accent-red/20 rounded-lg p-4">
                <h4 className="text-xs font-medium text-accent-red uppercase tracking-wider mb-1">Thesis Invalidation</h4>
                <p className="text-sm text-text-primary">{analysis.plan.thesis_invalidation}</p>
              </div>

              {/* Catalyst Awareness */}
              <div className="bg-accent-amber/5 border border-accent-amber/20 rounded-lg p-4">
                <h4 className="text-xs font-medium text-accent-amber uppercase tracking-wider mb-1">Catalyst Awareness</h4>
                <p className="text-sm text-text-primary">{analysis.plan.catalyst_awareness}</p>
              </div>

              {/* Correlation Warnings */}
              {analysis.plan.correlation_warnings.length > 0 && (
                <div className="bg-accent-purple/5 border border-accent-purple/20 rounded-lg p-4">
                  <h4 className="text-xs font-medium text-accent-purple uppercase tracking-wider mb-1">Correlation Warnings</h4>
                  {analysis.plan.correlation_warnings.map((w, i) => (
                    <p key={i} className="text-sm text-text-primary">{w}</p>
                  ))}
                </div>
              )}

              {/* Options Recommendation */}
              {analysis.plan.options_rec && (
                <div className="bg-accent-blue/5 border border-accent-blue/20 rounded-lg p-4">
                  <h4 className="text-xs font-medium text-accent-blue uppercase tracking-wider mb-1">Options Strategy</h4>
                  <p className="text-sm font-mono text-text-primary mb-1">{analysis.plan.options_rec.strategy}</p>
                  <p className="text-sm text-text-secondary">{analysis.plan.options_rec.rationale}</p>
                  <p className="text-sm text-text-primary mt-2 font-mono">{analysis.plan.options_rec.structure}</p>
                </div>
              )}

              {/* Confidence Breakdown */}
              <div>
                <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Confidence Breakdown</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(analysis.confidence.breakdown).map(([key, val]) => (
                    <ConfidenceBar key={key} label={key} value={val} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Session Analysis (collapsible) */}
          <details className="bg-bg-secondary border border-border-primary rounded-lg">
            <summary className="p-4 cursor-pointer text-sm font-medium text-text-secondary hover:text-text-primary">
              View Full Session Analysis (Stages 1 & 2)
            </summary>
            <div className="px-4 pb-4 space-y-4">
              <div>
                <h4 className="text-xs font-medium text-accent-blue uppercase mb-2">Stage 1: Catalyst & Macro Context</h4>
                <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono bg-bg-primary p-4 rounded-lg overflow-auto max-h-96">
                  {session.stage1_analysis}
                </pre>
              </div>
              <div>
                <h4 className="text-xs font-medium text-accent-purple uppercase mb-2">Stage 2: Market Regime Analysis</h4>
                <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono bg-bg-primary p-4 rounded-lg overflow-auto max-h-96">
                  {session.stage2_analysis}
                </pre>
              </div>
            </div>
          </details>
        </>
      )}
    </div>
  );
}

function LevelCard({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorClass = color === "red" ? "text-accent-red" : color === "green" ? "text-accent-green" : "text-text-primary";
  return (
    <div className="bg-bg-primary border border-border-primary rounded-lg p-3">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`text-sm font-mono font-medium ${colorClass}`}>{value}</div>
    </div>
  );
}

function ConfidenceBar({ label, value }: { label: string; value: number }) {
  const color =
    value >= 70 ? "bg-accent-green" :
    value >= 50 ? "bg-accent-amber" : "bg-accent-red";

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-text-muted capitalize">{label.replace('_', ' ')}</span>
        <span className="font-mono">{value.toFixed(0)}</span>
      </div>
      <div className="h-1.5 bg-bg-primary rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

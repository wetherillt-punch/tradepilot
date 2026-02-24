"use client";

import { useState, useCallback } from "react";
import api, { AnalysisResponse } from "@/lib/api";

export default function AnalyzePage() {
  const [mode, setMode] = useState<"quick" | "upload">("quick");
  const [ticker, setTicker] = useState("");
  const [direction, setDirection] = useState("bullish");
  const [tradeType, setTradeType] = useState("swing");
  const [timeframe, setTimeframe] = useState("1d");
  const [source, setSource] = useState("auto");
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);

  const handleAnalyze = async () => {
    if (!ticker.trim()) return;
    setAnalyzing(true);
    setError(null);
    try {
      let res: AnalysisResponse;
      if (mode === "upload" && file) {
        res = await api.analyzeWithUpload(file, ticker.trim(), tradeType, direction, timeframe, source);
      } else {
        res = await api.analyzeQuick(ticker.trim(), tradeType, direction);
      }
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith(".csv") || f.name.endsWith(".txt"))) {
      setFile(f);
      setMode("upload");
    }
  }, []);

  return (
    <div className="space-y-6 animate-in">
      <h2 className="text-lg font-semibold">Analyze Ticker</h2>

      {/* Mode Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setMode("quick")}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            mode === "quick" ? "bg-accent-blue text-white" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
          }`}
        >
          Quick (Auto-Fetch)
        </button>
        <button
          onClick={() => setMode("upload")}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            mode === "upload" ? "bg-accent-blue text-white" : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
          }`}
        >
          Upload CSV
        </button>
      </div>

      {/* Input Form */}
      <div className="bg-bg-secondary border border-border-primary rounded-lg p-6 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-text-muted block mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="NVDA"
              className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Direction</label>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
            >
              <option value="bullish">Bullish</option>
              <option value="bearish">Bearish</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Trade Type</label>
            <select
              value={tradeType}
              onChange={(e) => setTradeType(e.target.value)}
              className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
            >
              <option value="swing">Swing Trade</option>
              <option value="day_trade">Day Trade</option>
            </select>
          </div>
          {mode === "upload" && (
            <div>
              <label className="text-xs text-text-muted block mb-1">Source</label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
              >
                <option value="auto">Auto-Detect</option>
                <option value="thinkorswim">ThinkorSwim</option>
                <option value="tradingview">TradingView</option>
              </select>
            </div>
          )}
        </div>

        {/* File Drop Zone */}
        {mode === "upload" && (
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-border-primary rounded-lg p-8 text-center hover:border-accent-blue/50 transition-colors cursor-pointer"
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".csv,.txt"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) setFile(f);
              }}
            />
            {file ? (
              <div>
                <p className="text-sm text-accent-green font-mono">{file.name}</p>
                <p className="text-xs text-text-muted mt-1">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div>
                <p className="text-sm text-text-secondary">Drop CSV file here or click to browse</p>
                <p className="text-xs text-text-muted mt-1">Supports ThinkorSwim and TradingView exports</p>
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleAnalyze}
          disabled={analyzing || !ticker.trim() || (mode === "upload" && !file)}
          className="w-full px-5 py-2.5 bg-accent-blue hover:bg-accent-blue/80 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50"
        >
          {analyzing ? "Running 5-Stage Analysis Pipeline..." : "Generate Trade Plan"}
        </button>

        {error && <p className="text-accent-red text-sm">{error}</p>}
      </div>

      {/* Results */}
      {result && <TradePlanDisplay analysis={result} />}
    </div>
  );
}

function TradePlanDisplay({ analysis }: { analysis: AnalysisResponse }) {
  const plan = analysis.plan;
  const conf = analysis.confidence;

  return (
    <div className="bg-bg-secondary border border-border-primary rounded-lg p-6 animate-in space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold font-mono">{plan.ticker}</h2>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
            plan.direction === "bullish" ? "badge-bullish" : "badge-bearish"
          }`}>
            {plan.direction.toUpperCase()}
          </span>
          <span className="px-2 py-0.5 rounded text-xs font-medium bg-bg-tertiary text-text-secondary">
            {plan.setup_type}
          </span>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold font-mono ${
            conf.composite >= 65 ? "confidence-a" : conf.composite >= 50 ? "confidence-c" : "confidence-f"
          }`}>
            {conf.composite.toFixed(0)}
          </div>
          <div className="text-xs text-text-muted">{conf.rating}</div>
        </div>
      </div>

      {/* Thesis */}
      <Section title="Thesis">
        <p className="text-sm text-text-primary leading-relaxed">{plan.thesis}</p>
      </Section>

      {/* Levels Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <LevelCard label="Entry" value={plan.entry_zone} />
        <LevelCard label="Stop Loss" value={`$${plan.stop_loss}`} sub={plan.stop_loss_rationale} color="red" />
        {plan.targets.map((t, i) => (
          <LevelCard key={i} label={`TP${i + 1} (${t.pct_exit}%)`} value={`$${t.price}`} sub={t.rationale} color="green" />
        ))}
        <LevelCard label="R:R Ratio" value={`${plan.risk_reward_ratio.toFixed(1)}:1`} />
      </div>

      {/* Thesis Invalidation */}
      <div className="bg-accent-red/5 border border-accent-red/20 rounded-lg p-4">
        <h4 className="text-xs font-medium text-accent-red uppercase tracking-wider mb-1">Thesis Invalidation</h4>
        <p className="text-sm text-text-primary">{plan.thesis_invalidation}</p>
      </div>

      {/* Catalyst Awareness */}
      <div className="bg-accent-amber/5 border border-accent-amber/20 rounded-lg p-4">
        <h4 className="text-xs font-medium text-accent-amber uppercase tracking-wider mb-1">Catalyst Awareness</h4>
        <p className="text-sm text-text-primary">{plan.catalyst_awareness}</p>
      </div>

      {/* Correlation Warnings */}
      {plan.correlation_warnings.length > 0 && (
        <div className="bg-accent-purple/5 border border-accent-purple/20 rounded-lg p-4">
          <h4 className="text-xs font-medium text-accent-purple uppercase tracking-wider mb-1">Correlation Warnings</h4>
          {plan.correlation_warnings.map((w, i) => (
            <p key={i} className="text-sm text-text-primary">{w}</p>
          ))}
        </div>
      )}

      {/* Options Rec */}
      {plan.options_rec && (
        <div className="bg-accent-blue/5 border border-accent-blue/20 rounded-lg p-4">
          <h4 className="text-xs font-medium text-accent-blue uppercase tracking-wider mb-1">
            Options: {plan.options_rec.strategy}
          </h4>
          <p className="text-sm text-text-secondary mb-2">{plan.options_rec.rationale}</p>
          <p className="text-sm text-text-primary font-mono">{plan.options_rec.structure}</p>
        </div>
      )}

      {/* Confidence Breakdown */}
      <Section title="Confidence Breakdown">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(conf.breakdown).map(([key, val]) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-text-muted capitalize">{key.replace("_", " ")}</span>
                <span className="font-mono">{val.toFixed(0)}</span>
              </div>
              <div className="h-1.5 bg-bg-primary rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${val >= 70 ? "bg-accent-green" : val >= 50 ? "bg-accent-amber" : "bg-accent-red"}`}
                  style={{ width: `${val}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Key Indicators */}
      <details className="group">
        <summary className="cursor-pointer text-xs text-text-muted hover:text-text-secondary">
          View Raw Indicator Data
        </summary>
        <pre className="mt-2 text-xs text-text-muted font-mono bg-bg-primary p-4 rounded-lg overflow-auto max-h-64">
          {JSON.stringify(analysis.indicators, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">{title}</h4>
      {children}
    </div>
  );
}

function LevelCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  const c = color === "red" ? "text-accent-red" : color === "green" ? "text-accent-green" : "text-text-primary";
  return (
    <div className="bg-bg-primary border border-border-primary rounded-lg p-3">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`text-sm font-mono font-medium ${c}`}>{value}</div>
      {sub && <div className="text-xs text-text-muted mt-1 leading-tight">{sub}</div>}
    </div>
  );
}

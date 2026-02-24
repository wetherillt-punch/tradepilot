"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

export default function JournalPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [form, setForm] = useState({
    ticker: "",
    trade_type: "swing",
    direction: "bullish",
    actual_entry: "",
    actual_exit: "",
    pnl_percent: "",
    pnl_dollar: "",
    position_size: "",
    followed_plan: true,
    notes: "",
    trade_plan_id: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [debrief, setDebrief] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadEntries();
  }, []);

  const loadEntries = async () => {
    try {
      const res = await api.getJournal(50);
      setEntries(res.entries);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!form.ticker || !form.actual_entry || !form.actual_exit || !form.pnl_percent) return;
    setSubmitting(true);
    setError(null);
    setDebrief(null);
    try {
      const res = await api.logTrade({
        ticker: form.ticker.toUpperCase(),
        trade_type: form.trade_type,
        direction: form.direction,
        actual_entry: parseFloat(form.actual_entry),
        actual_exit: parseFloat(form.actual_exit),
        pnl_percent: parseFloat(form.pnl_percent),
        pnl_dollar: form.pnl_dollar ? parseFloat(form.pnl_dollar) : undefined,
        position_size: form.position_size ? parseFloat(form.position_size) : undefined,
        followed_plan: form.followed_plan,
        notes: form.notes,
        trade_plan_id: form.trade_plan_id || undefined,
      });
      setDebrief(res.debrief);
      await loadEntries();
      // Reset form
      setForm({
        ticker: "", trade_type: "swing", direction: "bullish",
        actual_entry: "", actual_exit: "", pnl_percent: "",
        pnl_dollar: "", position_size: "", followed_plan: true,
        notes: "", trade_plan_id: "",
      });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Trade Journal</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-1.5 text-sm bg-accent-blue hover:bg-accent-blue/80 text-white rounded-md transition-colors"
        >
          {showForm ? "Hide Form" : "+ Log Trade"}
        </button>
      </div>

      {/* Log Trade Form */}
      {showForm && (
        <div className="bg-bg-secondary border border-border-primary rounded-lg p-6 space-y-4">
          <h3 className="text-sm font-medium">Log Completed Trade</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Input label="Ticker" value={form.ticker} onChange={(v) => setForm({ ...form, ticker: v.toUpperCase() })} placeholder="NVDA" />
            <Select label="Direction" value={form.direction} onChange={(v) => setForm({ ...form, direction: v })} options={[["bullish", "Bullish"], ["bearish", "Bearish"]]} />
            <Select label="Type" value={form.trade_type} onChange={(v) => setForm({ ...form, trade_type: v })} options={[["swing", "Swing"], ["day_trade", "Day Trade"]]} />
            <Input label="Plan ID (optional)" value={form.trade_plan_id} onChange={(v) => setForm({ ...form, trade_plan_id: v })} placeholder="Link to plan" />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Input label="Entry Price" value={form.actual_entry} onChange={(v) => setForm({ ...form, actual_entry: v })} placeholder="185.50" type="number" />
            <Input label="Exit Price" value={form.actual_exit} onChange={(v) => setForm({ ...form, actual_exit: v })} placeholder="192.30" type="number" />
            <Input label="P/L %" value={form.pnl_percent} onChange={(v) => setForm({ ...form, pnl_percent: v })} placeholder="3.7" type="number" />
            <Input label="P/L $" value={form.pnl_dollar} onChange={(v) => setForm({ ...form, pnl_dollar: v })} placeholder="370" type="number" />
            <Input label="Position Size" value={form.position_size} onChange={(v) => setForm({ ...form, position_size: v })} placeholder="10000" type="number" />
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={form.followed_plan}
                onChange={(e) => setForm({ ...form, followed_plan: e.target.checked })}
                className="rounded border-border-primary"
              />
              Followed the plan
            </label>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Notes</label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="What happened? What did you learn?"
              rows={3}
              className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue resize-none"
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={submitting || !form.ticker || !form.actual_entry || !form.actual_exit || !form.pnl_percent}
            className="px-5 py-2 bg-accent-green hover:bg-accent-green/80 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50"
          >
            {submitting ? "Logging & Generating Debrief..." : "Log Trade"}
          </button>
          {error && <p className="text-accent-red text-sm">{error}</p>}
        </div>
      )}

      {/* AI Debrief */}
      {debrief && (
        <div className="bg-accent-blue/5 border border-accent-blue/20 rounded-lg p-5 animate-in">
          <h4 className="text-xs font-medium text-accent-blue uppercase tracking-wider mb-2">AI Post-Trade Debrief</h4>
          <pre className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">{debrief}</pre>
        </div>
      )}

      {/* Journal Entries */}
      <div className="space-y-3">
        {loading ? (
          <p className="text-text-muted text-sm text-center py-8">Loading journal...</p>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-text-muted">
            <p className="text-sm">No trades logged yet.</p>
            <p className="text-xs mt-1">Log your first trade to start building your performance history.</p>
          </div>
        ) : (
          entries.map((entry, i) => (
            <div key={entry._id || i} className="bg-bg-secondary border border-border-primary rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-sm">{entry.ticker}</span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    entry.direction === "bullish" ? "badge-bullish" : "badge-bearish"
                  }`}>
                    {entry.direction?.toUpperCase()}
                  </span>
                  <span className="text-xs text-text-muted">{entry.trade_type === "day_trade" ? "Day" : "Swing"}</span>
                </div>
                <span className={`font-mono text-sm font-medium ${
                  (entry.pnl_percent || 0) >= 0 ? "text-accent-green" : "text-accent-red"
                }`}>
                  {(entry.pnl_percent || 0) >= 0 ? "+" : ""}{entry.pnl_percent?.toFixed(1)}%
                  {entry.pnl_dollar != null && (
                    <span className="text-text-muted ml-2">
                      (${entry.pnl_dollar >= 0 ? "+" : ""}{entry.pnl_dollar?.toFixed(0)})
                    </span>
                  )}
                </span>
              </div>
              <div className="flex gap-4 text-xs text-text-muted mb-2">
                <span>Entry: <span className="font-mono text-text-secondary">${entry.actual_entry}</span></span>
                <span>Exit: <span className="font-mono text-text-secondary">${entry.actual_exit}</span></span>
                {!entry.followed_plan && <span className="text-accent-amber">⚠ Deviated from plan</span>}
              </div>
              {entry.notes && <p className="text-xs text-text-secondary">{entry.notes}</p>}
              {entry.ai_debrief && (
                <details className="mt-2">
                  <summary className="text-xs text-accent-blue cursor-pointer hover:text-accent-blue/80">View AI Debrief</summary>
                  <pre className="mt-2 text-xs text-text-secondary whitespace-pre-wrap bg-bg-primary p-3 rounded-md">{entry.ai_debrief}</pre>
                </details>
              )}
              <div className="text-xs text-text-muted mt-2">
                {entry.created_at && new Date(entry.created_at).toLocaleDateString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function Input({ label, value, onChange, placeholder, type = "text" }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string;
}) {
  return (
    <div>
      <label className="text-xs text-text-muted block mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
      />
    </div>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
}) {
  return (
    <div>
      <label className="text-xs text-text-muted block mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-bg-primary border border-border-primary rounded-md text-sm text-text-primary focus:outline-none focus:border-accent-blue"
      >
        {options.map(([val, lbl]) => <option key={val} value={val}>{lbl}</option>)}
      </select>
    </div>
  );
}

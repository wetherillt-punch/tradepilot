/**
 * TradePilot API Client
 * Communicates with the Python backend on Railway.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class TradePilotAPI {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_URL;
  }

  private async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `API Error: ${res.status}`);
    }

    return res.json();
  }

  // ─── Session ─────────────────────────────────────────────────────────

  async initSession(watchlist: string[] = []) {
    return this.fetch<SessionResponse>("/api/session/init", {
      method: "POST",
      body: JSON.stringify(watchlist),
    });
  }

  // ─── Analysis ────────────────────────────────────────────────────────

  async analyzeWithUpload(
    file: File,
    ticker: string,
    tradeType: string = "swing",
    direction: string = "bullish",
    timeframe: string = "1d",
    source: string = "auto"
  ) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("ticker", ticker);
    formData.append("trade_type", tradeType);
    formData.append("direction", direction);
    formData.append("timeframe", timeframe);
    formData.append("source", source);

    const res = await fetch(`${this.baseUrl}/api/analyze/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `API Error: ${res.status}`);
    }

    return res.json() as Promise<AnalysisResponse>;
  }

  async analyzeQuick(ticker: string, tradeType: string = "swing", direction: string = "bullish") {
    return this.fetch<AnalysisResponse>("/api/analyze/quick", {
      method: "POST",
      body: JSON.stringify({
        ticker,
        trade_type: tradeType,
        direction,
      }),
    });
  }

  // ─── Journal ─────────────────────────────────────────────────────────

  async logTrade(entry: JournalEntry) {
    return this.fetch<{ id: string; debrief: string }>("/api/journal/log", {
      method: "POST",
      body: JSON.stringify(entry),
    });
  }

  async getJournal(limit: number = 50) {
    return this.fetch<{ entries: any[] }>(`/api/journal?limit=${limit}`);
  }

  // ─── Performance ─────────────────────────────────────────────────────

  async getPerformance(days: number = 30) {
    return this.fetch<PerformanceStats>(`/api/performance?days=${days}`);
  }

  async getWeeklyDigest() {
    return this.fetch<{ digest: string }>("/api/performance/weekly-digest", {
      method: "POST",
    });
  }

  // ─── Plans (v1 - legacy) ────────────────────────────────────────────

  async getPlans(limit: number = 20) {
    return this.fetch<{ plans: any[] }>(`/api/plans?limit=${limit}`);
  }

  async getPlan(planId: string) {
    return this.fetch<any>(`/api/plans/${planId}`);
  }

  // ─── Plans v2 (lifecycle-tracked) ──────────────────────────────────

  async getPlansV2(date?: string, status?: string, sessionId?: string) {
    const params = new URLSearchParams();
    if (date) params.set("date", date);
    if (status) params.set("status", status);
    if (sessionId) params.set("session_id", sessionId);
    return this.fetch<{ plans: PlanV2[] }>(`/api/v2/plans?${params}`);
  }

  async getPlanV2(planId: string) {
    return this.fetch<PlanV2>(`/api/v2/plans/${planId}`);
  }

  async createPlanV2(plan: CreatePlanV2) {
    return this.fetch<PlanV2>("/api/v2/plans", {
      method: "POST",
      body: JSON.stringify(plan),
    });
  }

  async logEntry(planId: string, entry: { fill_price: number; contracts: number; self_reported_deviations?: string[] }) {
    return this.fetch<{ status: string; entry: any; auto_deviations: string[] }>(`/api/v2/plans/${planId}/entry`, {
      method: "POST",
      body: JSON.stringify(entry),
    });
  }

  async logExit(planId: string, exit: { price: number; contracts: number; exit_type: string; followed_plan?: boolean; deviations?: string[] }) {
    return this.fetch<{ status: string; exit: any; total_pnl_dollars: number; remaining_contracts: number }>(`/api/v2/plans/${planId}/exit`, {
      method: "POST",
      body: JSON.stringify(exit),
    });
  }

  async cancelPlan(planId: string, reason: string) {
    return this.fetch<{ status: string; reason: string }>(`/api/v2/plans/${planId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  }

  async getPlansHistory(days: number = 30) {
    return this.fetch<{ history: PlanHistoryDay[] }>(`/api/v2/plans/history?days=${days}`);
  }

  async searchPlansByTicker(ticker: string) {
    return this.fetch<{ plans: PlanV2[]; ticker: string }>(`/api/v2/plans/search/${ticker}`);
  }

  // ─── Settings ─────────────────────────────────────────────────────

  async getSettings() {
    return this.fetch<UserSettings>("/api/v2/settings");
  }

  async updateSettings(settings: Partial<UserSettings>) {
    return this.fetch<UserSettings>("/api/v2/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  }

  // ─── Watchlist ────────────────────────────────────────────────────

  async getWatchlist() {
    return this.fetch<{ tickers: string[] }>("/api/v2/watchlist");
  }

  async updateWatchlist(tickers: string[]) {
    return this.fetch<{ tickers: string[] }>("/api/v2/watchlist", {
      method: "PUT",
      body: JSON.stringify(tickers),
    });
  }

  // ─── Catalysts ───────────────────────────────────────────────────────

  async getBellwethers() {
    return this.fetch<Record<string, any>>("/api/catalysts/bellwethers");
  }

  async getMacroProfiles() {
    return this.fetch<Record<string, any>>("/api/catalysts/macro-profiles");
  }

  async getGeoTemplates() {
    return this.fetch<Record<string, any>>("/api/catalysts/geo-templates");
  }

  // ─── Chat ──────────────────────────────────────────────────────────

  async chat(messages: ChatMessage[]) {
    return this.fetch<{ response: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ messages }),
    });
  }

  // ─── Chart Data ─────────────────────────────────────────────────────

  async getChartData(ticker: string, period: string = "6mo", interval: string = "1d") {
    return this.fetch<ChartDataResponse>(`/api/chart/${ticker}?period=${period}&interval=${interval}`);
  }

  // ─── Health ──────────────────────────────────────────────────────────

  async health() {
    return this.fetch<{ status: string; timestamp: string }>("/health");
  }
}

// ─── Types ─────────────────────────────────────────────────────────────────

export interface SessionResponse {
  session_id: string;
  regime: {
    spy: string;
    qqq: string;
    vix: number;
    vix_percentile: number;
    volatility: string;
    bias: string;
    sectors: {
      leaders: Array<{ sector: string; etf: string; perf: number }>;
      laggards: Array<{ sector: string; etf: string; perf: number }>;
    };
  };
  catalysts: {
    earnings_count: number;
    earnings: Array<{ ticker: string; date: string; bellwether: boolean }>;
    event_risk: string;
  };
  stage1_analysis: string;
  stage2_analysis: string;
}

export interface AnalysisResponse {
  plan: {
    id: string;
    ticker: string;
    trade_type: string;
    direction: string;
    thesis: string;
    setup_type: string;
    entry_zone: string;
    stop_loss: number;
    stop_loss_rationale: string;
    targets: Array<{ price: number; pct_exit: number; rationale: string }>;
    risk_reward_ratio: number;
    thesis_invalidation: string;
    catalyst_awareness: string;
    correlation_warnings: string[];
    market_regime_summary: string;
    options_rec?: {
      strategy: string;
      rationale: string;
      structure: string;
    };
  };
  indicators: Record<string, any>;
  confidence: {
    composite: number;
    rating: string;
    breakdown: {
      trend: number;
      momentum: number;
      volume: number;
      volatility: number;
      regime: number;
      catalyst: number;
      historical: number;
      personal: number;
    };
  };
}

export interface JournalEntry {
  trade_plan_id?: string;
  ticker: string;
  trade_type: string;
  direction: string;
  actual_entry: number;
  actual_exit: number;
  position_size?: number;
  pnl_dollar?: number;
  pnl_percent: number;
  followed_plan: boolean;
  notes: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChartDataResponse {
  candles: Array<{ time: string; open: number; high: number; low: number; close: number }>;
  volumes: Array<{ time: string; value: number; color: string }>;
  ticker: string;
}

export interface PerformanceStats {
  period_days: number;
  total_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  total_pnl_pct: number;
  best_trade: number;
  worst_trade: number;
  setup_breakdown: Record<string, { wins: number; losses: number; total_pnl: number }>;
}

// ─── V2 Plan Types ──────────────────────────────────────────────────────────

export type PlanStatus = "watching" | "entered" | "exited" | "stopped_out" | "cancelled" | "reviewed";

export interface PlanV2 {
  _id: string;
  session_id: string;
  date: string;
  ticker: string;
  direction: "call" | "put";
  status: PlanStatus;
  source: "generated" | "manual";

  confidence: { score: number | null; grade: string | null };
  entry_zone: { low: number | null; high: number | null };
  stop: { price: number | null; reason: string | null };
  targets: Array<{ level: number; price: number; exit_pct: number }>;
  strike: string | null;
  risk_reward: number | null;
  size: { contracts: number | null; risk_dollars: number | null };
  kill_switch: string | null;

  timing: {
    primary: string | null;
    secondary: string | null;
    dead_zones: string[];
    hard_cutoff: string | null;
  };

  expected_premium: { low: number | null; high: number | null; max_pay: number | null };

  thesis: string | null;
  regime_context: string | null;
  catalyst_risk: string | null;
  invalidation: string[];
  cross_asset_note: string | null;
  options_detail: string | null;
  scaling_strategy: string | null;
  position_kill: string[];
  discipline_note: string | null;

  checklist_premarket: Record<string, any>;
  checklist_intraday: Record<string, any>;
  confidence_breakdown: Record<string, number>;

  entry: {
    fill_price: number;
    contracts: number;
    time: string;
    auto_deviations: string[];
    self_reported_deviations: string[];
    deviation_count: number;
  } | null;

  exits: Array<{
    price: number;
    contracts: number;
    time: string;
    type: string;
    followed_plan: boolean;
    deviations: string[];
    pnl_dollars: number;
    pnl_percent: number;
    remaining_after: number;
  }>;

  remaining_contracts: number;
  total_pnl_dollars: number;
  total_pnl_percent: number;
  r_realized: number;

  debrief: {
    summary: string;
    what_worked: string;
    improve: string;
    discipline_score: number;
  } | null;

  cancellation: { reason: string; time: string } | null;

  created_at: string;
  updated_at: string;
}

export interface CreatePlanV2 {
  session_id: string;
  date: string;
  ticker: string;
  direction: string;
  source?: string;
  [key: string]: any;  // Allow additional card/deep-dive fields
}

export interface PlanHistoryDay {
  date: string;
  plans: PlanV2[];
  total_pnl: number;
  entered_count: number;
  rules_broken: number;
}

export interface UserSettings {
  daily_loss_limit: number;
  account_size: number;
  risk_per_trade_pct: number;
  confidence_threshold: number;
  commission_per_contract: number;
  revenge_cooldown_minutes: number;
  quick_check_cooldown_minutes: number;
}

// Export singleton
export const api = new TradePilotAPI();
export default api;

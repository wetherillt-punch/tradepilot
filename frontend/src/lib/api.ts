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

  // ─── Plans ───────────────────────────────────────────────────────────

  async getPlans(limit: number = 20) {
    return this.fetch<{ plans: any[] }>(`/api/plans?limit=${limit}`);
  }

  async getPlan(planId: string) {
    return this.fetch<any>(`/api/plans/${planId}`);
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

// Export singleton
export const api = new TradePilotAPI();
export default api;

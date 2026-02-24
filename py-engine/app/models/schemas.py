"""
TradePilot Data Models
Pydantic models for all data structures used across the engine.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    DAILY = "1d"
    WEEKLY = "1wk"

class TradeType(str, Enum):
    DAY_TRADE = "day_trade"
    SWING = "swing"

class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class RegimeType(str, Enum):
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGE_BOUND = "range_bound"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    HIGH_VOLATILITY = "high_volatility"

class CatalystType(str, Enum):
    MACRO = "macro"
    EARNINGS = "earnings"
    GEOPOLITICAL = "geopolitical"
    FED = "fed"
    SECTOR = "sector"

class OptionsStrategy(str, Enum):
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    IRON_CONDOR = "iron_condor"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    STOCK_ONLY = "stock_only"

class EventRisk(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


# ─── OHLCV Data ──────────────────────────────────────────────────────────────

class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class TickerData(BaseModel):
    ticker: str
    timeframe: Timeframe
    bars: list[OHLCVBar]
    source: Literal["thinkorswim", "tradingview", "yfinance", "manual"]


# ─── Indicator Output ─────────────────────────────────────────────────────────

class MACDValues(BaseModel):
    line: float
    signal: float
    histogram: float

class BollingerValues(BaseModel):
    upper: float
    middle: float
    lower: float
    bandwidth: float
    squeeze: bool  # bandwidth < 20-period low of bandwidth

class StochRSIValues(BaseModel):
    k: float
    d: float

class IndicatorSnapshot(BaseModel):
    """Complete indicator state for a single point in time."""
    ticker: str
    timestamp: datetime
    timeframe: Timeframe
    price: float

    # Moving Averages
    ema_9: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    ema_stack: Optional[Direction] = None  # bullish if 9>20>50>200

    # Momentum
    rsi_14: Optional[float] = None
    rsi_divergence: Optional[str] = None  # "bullish_divergence", "bearish_divergence", None
    macd: Optional[MACDValues] = None
    stoch_rsi: Optional[StochRSIValues] = None

    # Volume
    volume: Optional[float] = None
    rvol: Optional[float] = None  # relative volume vs 20-day avg
    obv_trend: Optional[Direction] = None
    vwap: Optional[float] = None
    price_vs_vwap: Optional[str] = None  # "above", "below", "at"

    # Volatility
    atr_14: Optional[float] = None
    atr_percent: Optional[float] = None  # ATR as % of price
    bollinger: Optional[BollingerValues] = None

    # Trend Strength
    adx_14: Optional[float] = None
    adx_trend: Optional[str] = None  # "strong", "moderate", "weak", "no_trend"

    # Options-specific (if available)
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    put_call_oi_ratio: Optional[float] = None

    # Detected patterns
    patterns: list[str] = Field(default_factory=list)


# ─── Market Regime ────────────────────────────────────────────────────────────

class SectorRotation(BaseModel):
    sector: str
    etf: str
    performance_1w: Optional[float] = None
    performance_1m: Optional[float] = None
    relative_strength: Optional[float] = None  # vs SPY

class MarketRegime(BaseModel):
    """Market-wide regime assessment. Computed once per session."""
    timestamp: datetime

    # Broad market
    spy_regime: RegimeType
    qqq_regime: RegimeType
    spy_vs_emas: dict[str, str] = Field(default_factory=dict)  # {"ema_20": "above", ...}
    market_direction: Direction

    # Volatility
    vix: float
    vix_percentile: Optional[float] = None  # where current VIX sits vs 1yr range
    vix_term_structure: Optional[str] = None  # "contango" or "backwardation"
    volatility_regime: str  # "low", "normal", "elevated", "extreme"

    # Breadth (when available)
    advance_decline_ratio: Optional[float] = None
    pct_above_200ema: Optional[float] = None
    breadth_assessment: Optional[str] = None

    # Sector rotation
    sector_leaders: list[SectorRotation] = Field(default_factory=list)
    sector_laggards: list[SectorRotation] = Field(default_factory=list)

    # Overall assessment
    bias: Direction  # risk-on, risk-off, neutral
    summary: str = ""


# ─── Catalysts ────────────────────────────────────────────────────────────────

class ScheduledEvent(BaseModel):
    date: date
    time: Optional[str] = None
    event_name: str
    category: CatalystType
    expected_impact: EventRisk
    details: Optional[str] = None
    historical_avg_move_spy: Optional[float] = None  # avg SPY move on this event

class EarningsEvent(BaseModel):
    ticker: str
    date: date
    time: Optional[str] = None  # "BMO" (before market open) or "AMC" (after market close)
    expected_move: Optional[float] = None  # from options implied
    last_4q_reactions: list[float] = Field(default_factory=list)  # % moves last 4 quarters
    is_bellwether: bool = False
    affected_tickers: list[str] = Field(default_factory=list)  # tickers correlated to this

class GeopoliticalEvent(BaseModel):
    event_name: str
    classification: str  # "military_conflict", "trade_war", "debt_crisis", etc.
    status: str  # "active", "escalating", "de-escalating", "resolved"
    historical_analog: Optional[str] = None
    analog_market_reaction: Optional[dict] = None
    estimated_duration: Optional[str] = None
    sector_impacts: dict[str, str] = Field(default_factory=dict)  # sector: "positive"/"negative"
    risk_level: EventRisk = EventRisk.MODERATE

class CatalystContext(BaseModel):
    """Complete catalyst environment. Computed once per session."""
    timestamp: datetime
    macro_events_this_week: list[ScheduledEvent] = Field(default_factory=list)
    earnings_this_week: list[EarningsEvent] = Field(default_factory=list)
    active_geopolitical: list[GeopoliticalEvent] = Field(default_factory=list)
    overall_event_risk: EventRisk = EventRisk.LOW
    week_narrative: str = ""
    positioning_bias: str = ""  # "risk-on", "risk-off", "neutral", "wait-for-catalyst"


# ─── Confidence Score ─────────────────────────────────────────────────────────

class ConfidenceBreakdown(BaseModel):
    trend_alignment: float = Field(ge=0, le=100)        # 15%
    momentum_confirmation: float = Field(ge=0, le=100)   # 12%
    volume_confirmation: float = Field(ge=0, le=100)     # 12%
    volatility_context: float = Field(ge=0, le=100)      # 8%
    regime_alignment: float = Field(ge=0, le=100)        # 13%
    catalyst_alignment: float = Field(ge=0, le=100)      # 13%
    historical_analog: float = Field(ge=0, le=100)       # 12%
    personal_edge: float = Field(ge=0, le=100, default=50)  # 15% - starts neutral

    @property
    def composite(self) -> float:
        return round(
            self.trend_alignment * 0.15 +
            self.momentum_confirmation * 0.12 +
            self.volume_confirmation * 0.12 +
            self.volatility_context * 0.08 +
            self.regime_alignment * 0.13 +
            self.catalyst_alignment * 0.13 +
            self.historical_analog * 0.12 +
            self.personal_edge * 0.15,
            1
        )

    @property
    def rating(self) -> str:
        score = self.composite
        if score >= 80:
            return "A — High Conviction"
        elif score >= 65:
            return "B — Favorable Setup"
        elif score >= 50:
            return "C — Mixed Signals"
        elif score >= 35:
            return "D — Proceed With Caution"
        else:
            return "F — Avoid"


# ─── Options Recommendation ──────────────────────────────────────────────────

class OptionsRecommendation(BaseModel):
    strategy: OptionsStrategy
    rationale: str
    structure: str  # e.g., "Buy NVDA 140C 3/21 @ $4.20"
    max_loss: Optional[float] = None
    max_profit: Optional[float] = None
    breakeven: Optional[float] = None
    probability_of_profit: Optional[float] = None
    greeks_notes: Optional[str] = None


# ─── Trade Plan ───────────────────────────────────────────────────────────────

class TradePlan(BaseModel):
    """The final output — a complete trade plan."""
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ticker: str
    trade_type: TradeType
    direction: Direction

    # Thesis
    thesis: str
    setup_type: str  # "bull_flag", "breakout", "mean_reversion", etc.

    # Levels
    entry_zone: str  # price range or condition
    stop_loss: float
    stop_loss_rationale: str
    targets: list[dict] = Field(default_factory=list)  # [{"price": 150, "pct_exit": 50}, ...]
    risk_reward_ratio: float

    # Invalidation
    thesis_invalidation: str  # condition that kills the trade regardless of stop

    # Options (if applicable)
    options_rec: Optional[OptionsRecommendation] = None

    # Context
    confidence: ConfidenceBreakdown
    catalyst_awareness: str  # free text from LLM about relevant catalysts
    correlation_warnings: list[str] = Field(default_factory=list)

    # Regime context at time of plan
    market_regime_summary: str = ""

    # Indicator snapshot used
    indicators_used: Optional[IndicatorSnapshot] = None

    # Feedback (filled later)
    outcome: Optional[dict] = None  # filled when trade is journaled


# ─── Trade Journal Entry ──────────────────────────────────────────────────────

class JournalEntry(BaseModel):
    id: Optional[str] = None
    trade_plan_id: Optional[str] = None  # links to the plan
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ticker: str
    trade_type: TradeType
    direction: Direction

    # Execution
    actual_entry: float
    actual_exit: float
    position_size: Optional[float] = None
    pnl_dollar: Optional[float] = None
    pnl_percent: float

    # Assessment
    followed_plan: bool = True
    notes: str = ""
    what_worked: Optional[str] = None
    what_failed: Optional[str] = None
    lesson: Optional[str] = None

    # LLM debrief (auto-generated)
    ai_debrief: Optional[str] = None


# ─── Session Cache ────────────────────────────────────────────────────────────

class SessionContext(BaseModel):
    """Cached session-level context (Stages 1-2). Computed once, used for all tickers."""
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    regime: MarketRegime
    catalysts: CatalystContext
    stage1_output: str = ""  # raw LLM output from Stage 1
    stage2_output: str = ""  # raw LLM output from Stage 2

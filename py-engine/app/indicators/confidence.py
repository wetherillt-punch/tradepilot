"""
TradePilot Confidence Scoring Engine
Transparent, composite scoring with 7 components.
No black box — every component is visible and auditable.
"""

from app.models.schemas import (
    ConfidenceBreakdown, IndicatorSnapshot, MarketRegime, CatalystContext,
    Direction, RegimeType, EventRisk, TradeType
)
from typing import Optional


class ConfidenceScorer:
    """
    Computes a transparent confidence score from indicator data,
    market regime, catalyst context, and personal trade history.
    """

    def score(
        self,
        indicators: IndicatorSnapshot,
        direction: Direction,
        trade_type: TradeType,
        regime: Optional[MarketRegime] = None,
        catalysts: Optional[CatalystContext] = None,
        personal_win_rate: Optional[float] = None,  # 0-100, from journal data
    ) -> ConfidenceBreakdown:

        return ConfidenceBreakdown(
            trend_alignment=self._score_trend(indicators, direction),
            momentum_confirmation=self._score_momentum(indicators, direction),
            volume_confirmation=self._score_volume(indicators, direction),
            volatility_context=self._score_volatility(indicators, trade_type),
            regime_alignment=self._score_regime(regime, direction) if regime else 50,
            catalyst_alignment=self._score_catalysts(catalysts, direction) if catalysts else 50,
            historical_analog=50,  # populated by LLM in Stage 4
            personal_edge=personal_win_rate if personal_win_rate is not None else 50,
        )

    # ─── Trend Alignment (15%) ────────────────────────────────────────────

    def _score_trend(self, ind: IndicatorSnapshot, direction: Direction) -> float:
        score = 50  # neutral baseline

        # EMA stack alignment
        if ind.ema_stack == direction:
            score += 25
        elif ind.ema_stack and ind.ema_stack != Direction.NEUTRAL and ind.ema_stack != direction:
            score -= 25

        # Price vs key EMAs
        if direction == Direction.BULLISH:
            if ind.ema_20 and ind.price > ind.ema_20:
                score += 10
            if ind.ema_50 and ind.price > ind.ema_50:
                score += 8
            if ind.ema_200 and ind.price > ind.ema_200:
                score += 7
            # Price below 200 EMA on a bullish trade is concerning
            if ind.ema_200 and ind.price < ind.ema_200:
                score -= 15
        elif direction == Direction.BEARISH:
            if ind.ema_20 and ind.price < ind.ema_20:
                score += 10
            if ind.ema_50 and ind.price < ind.ema_50:
                score += 8
            if ind.ema_200 and ind.price < ind.ema_200:
                score += 7
            if ind.ema_200 and ind.price > ind.ema_200:
                score -= 15

        return max(0, min(100, score))

    # ─── Momentum Confirmation (12%) ─────────────────────────────────────

    def _score_momentum(self, ind: IndicatorSnapshot, direction: Direction) -> float:
        score = 50
        signals = 0
        confirmations = 0

        # RSI
        if ind.rsi_14 is not None:
            signals += 1
            if direction == Direction.BULLISH:
                if 40 <= ind.rsi_14 <= 70:
                    confirmations += 1  # healthy bullish range
                elif ind.rsi_14 > 70:
                    score -= 10  # overbought risk
                elif ind.rsi_14 < 30:
                    confirmations += 0.5  # oversold bounce potential
            elif direction == Direction.BEARISH:
                if 30 <= ind.rsi_14 <= 60:
                    confirmations += 1
                elif ind.rsi_14 < 30:
                    score -= 10  # oversold bounce risk
                elif ind.rsi_14 > 70:
                    confirmations += 0.5

        # MACD
        if ind.macd is not None:
            signals += 1
            if direction == Direction.BULLISH:
                if ind.macd.histogram > 0:
                    confirmations += 1
                if ind.macd.line > ind.macd.signal:
                    confirmations += 0.5
            elif direction == Direction.BEARISH:
                if ind.macd.histogram < 0:
                    confirmations += 1
                if ind.macd.line < ind.macd.signal:
                    confirmations += 0.5

        # Stoch RSI
        if ind.stoch_rsi is not None:
            signals += 1
            if direction == Direction.BULLISH and ind.stoch_rsi.k > ind.stoch_rsi.d:
                confirmations += 1
            elif direction == Direction.BEARISH and ind.stoch_rsi.k < ind.stoch_rsi.d:
                confirmations += 1

        # RSI divergence bonus
        if ind.rsi_divergence:
            if direction == Direction.BULLISH and ind.rsi_divergence == "bullish_divergence":
                score += 15
            elif direction == Direction.BEARISH and ind.rsi_divergence == "bearish_divergence":
                score += 15
            # Wrong-way divergence is a warning
            elif direction == Direction.BULLISH and ind.rsi_divergence == "bearish_divergence":
                score -= 15
            elif direction == Direction.BEARISH and ind.rsi_divergence == "bullish_divergence":
                score -= 15

        if signals > 0:
            confirmation_pct = confirmations / signals
            score += (confirmation_pct - 0.5) * 40  # -20 to +20 range

        return max(0, min(100, score))

    # ─── Volume Confirmation (12%) ───────────────────────────────────────

    def _score_volume(self, ind: IndicatorSnapshot, direction: Direction) -> float:
        score = 50

        # RVOL
        if ind.rvol is not None:
            if ind.rvol >= 2.0:
                score += 25  # strong volume confirmation
            elif ind.rvol >= 1.5:
                score += 15
            elif ind.rvol >= 1.0:
                score += 5
            elif ind.rvol < 0.7:
                score -= 15  # low volume is a warning

        # OBV trend alignment
        if ind.obv_trend is not None:
            if ind.obv_trend == direction:
                score += 15
            elif ind.obv_trend != Direction.NEUTRAL and ind.obv_trend != direction:
                score -= 15  # divergence between OBV and trade direction

        # Price vs VWAP
        if ind.price_vs_vwap:
            if direction == Direction.BULLISH and ind.price_vs_vwap == "above":
                score += 5
            elif direction == Direction.BEARISH and ind.price_vs_vwap == "below":
                score += 5
            elif direction == Direction.BULLISH and ind.price_vs_vwap == "below":
                score -= 5
            elif direction == Direction.BEARISH and ind.price_vs_vwap == "above":
                score -= 5

        return max(0, min(100, score))

    # ─── Volatility Context (8%) ─────────────────────────────────────────

    def _score_volatility(self, ind: IndicatorSnapshot, trade_type: TradeType) -> float:
        score = 50

        # ATR% context
        if ind.atr_percent is not None:
            if trade_type == TradeType.DAY_TRADE:
                # Day trades want volatility for movement
                if ind.atr_percent >= 3:
                    score += 20  # good intraday range
                elif ind.atr_percent >= 2:
                    score += 10
                elif ind.atr_percent < 1:
                    score -= 20  # too tight for day trading
            else:
                # Swing trades: moderate volatility is ideal
                if 1.5 <= ind.atr_percent <= 4:
                    score += 15
                elif ind.atr_percent > 6:
                    score -= 15  # too volatile for swing holds

        # Bollinger squeeze
        if ind.bollinger and ind.bollinger.squeeze:
            score += 15  # squeeze = potential breakout, elevated opportunity

        return max(0, min(100, score))

    # ─── Regime Alignment (13%) ──────────────────────────────────────────

    def _score_regime(self, regime: MarketRegime, direction: Direction) -> float:
        score = 50

        # Market direction alignment
        if regime.market_direction == direction:
            score += 20
        elif regime.market_direction != Direction.NEUTRAL and regime.market_direction != direction:
            score -= 20  # trading against the trend

        # Regime type
        if direction == Direction.BULLISH:
            if regime.spy_regime in [RegimeType.STRONG_UPTREND, RegimeType.UPTREND]:
                score += 15
            elif regime.spy_regime in [RegimeType.STRONG_DOWNTREND, RegimeType.DOWNTREND]:
                score -= 15
        elif direction == Direction.BEARISH:
            if regime.spy_regime in [RegimeType.STRONG_DOWNTREND, RegimeType.DOWNTREND]:
                score += 15
            elif regime.spy_regime in [RegimeType.STRONG_UPTREND, RegimeType.UPTREND]:
                score -= 15

        # VIX context
        if regime.vix < 15:
            if direction == Direction.BULLISH:
                score += 5  # low VIX favors bulls
            else:
                score -= 5  # complacency makes shorts harder
        elif regime.vix > 30:
            score -= 10  # extreme vol is risky for both directions
        elif regime.vix > 25:
            if direction == Direction.BEARISH:
                score += 5  # elevated VIX confirms bearish
            else:
                score -= 5

        return max(0, min(100, score))

    # ─── Catalyst Alignment (13%) ────────────────────────────────────────

    def _score_catalysts(self, catalysts: CatalystContext, direction: Direction) -> float:
        score = 50

        # Overall event risk
        risk_penalty = {
            EventRisk.LOW: 0,
            EventRisk.MODERATE: -5,
            EventRisk.HIGH: -15,
            EventRisk.EXTREME: -25,
        }
        score += risk_penalty.get(catalysts.overall_event_risk, 0)

        # Positioning bias alignment
        if catalysts.positioning_bias == "risk-on" and direction == Direction.BULLISH:
            score += 15
        elif catalysts.positioning_bias == "risk-off" and direction == Direction.BEARISH:
            score += 15
        elif catalysts.positioning_bias == "risk-on" and direction == Direction.BEARISH:
            score -= 10
        elif catalysts.positioning_bias == "risk-off" and direction == Direction.BULLISH:
            score -= 10
        elif catalysts.positioning_bias == "wait-for-catalyst":
            score -= 10  # uncertainty

        # High-impact macro events this week reduce confidence for all trades
        high_impact_count = sum(
            1 for e in catalysts.macro_events_this_week
            if e.expected_impact in [EventRisk.HIGH, EventRisk.EXTREME]
        )
        score -= high_impact_count * 5

        # Active geopolitical events reduce confidence
        active_geo = len(catalysts.active_geopolitical)
        if active_geo > 0:
            score -= min(active_geo * 8, 20)

        return max(0, min(100, score))

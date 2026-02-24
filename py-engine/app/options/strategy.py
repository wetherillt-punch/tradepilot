"""
TradePilot Options Strategy Decision Tree
Deterministic rules for selecting the optimal options structure.
The LLM can override with reasoning, but this is the quantitative default.
"""

from app.models.schemas import (
    OptionsStrategy, TradeType, Direction, ConfidenceBreakdown,
    IndicatorSnapshot, OptionsRecommendation, EventRisk
)
from typing import Optional


class OptionsStrategyEngine:
    """
    Selects options strategy based on:
    - Trade type (day vs swing)
    - Direction (bullish/bearish/neutral)
    - IV environment (rank/percentile)
    - Confidence level
    - Upcoming catalyst risk
    """

    def recommend(
        self,
        trade_type: TradeType,
        direction: Direction,
        indicators: IndicatorSnapshot,
        confidence: ConfidenceBreakdown,
        catalyst_risk: EventRisk = EventRisk.LOW,
        days_to_earnings: Optional[int] = None,
    ) -> OptionsRecommendation:

        iv_rank = indicators.iv_rank or 50  # default to mid if unavailable
        iv_pct = indicators.iv_percentile or 50
        score = confidence.composite

        # ─── Earnings proximity override ──────────────────────────────────
        if days_to_earnings is not None and days_to_earnings <= 3:
            return self._earnings_play(direction, iv_rank, score)

        # ─── Day trade strategies ─────────────────────────────────────────
        if trade_type == TradeType.DAY_TRADE:
            return self._day_trade_strategy(direction, iv_rank, score, catalyst_risk)

        # ─── Swing trade strategies ───────────────────────────────────────
        return self._swing_strategy(direction, iv_rank, score, catalyst_risk)

    def _day_trade_strategy(
        self, direction: Direction, iv_rank: float,
        score: float, catalyst_risk: EventRisk
    ) -> OptionsRecommendation:
        """Day trades favor directional plays with leverage."""

        # High confidence → direct long options
        if score >= 70 and direction != Direction.NEUTRAL:
            strategy = OptionsStrategy.LONG_CALL if direction == Direction.BULLISH else OptionsStrategy.LONG_PUT
            return OptionsRecommendation(
                strategy=strategy,
                rationale=(
                    f"High confidence ({score:.0f}) day trade. Direct long options "
                    f"for leverage. IV rank {iv_rank:.0f} is acceptable for intraday hold."
                ),
                structure=f"Buy ATM or slightly OTM {'call' if direction == Direction.BULLISH else 'put'}, "
                          f"0-2 DTE for gamma. Target 50% profit, stop at 30%.",
            )

        # Moderate confidence → defined risk spread
        if score >= 50 and direction != Direction.NEUTRAL:
            if direction == Direction.BULLISH:
                strategy = OptionsStrategy.BULL_CALL_SPREAD
            else:
                strategy = OptionsStrategy.BEAR_PUT_SPREAD

            return OptionsRecommendation(
                strategy=strategy,
                rationale=(
                    f"Moderate confidence ({score:.0f}) day trade. Debit spread "
                    f"caps risk while maintaining directional exposure. "
                    f"Better risk/reward than naked long in uncertain conditions."
                ),
                structure=f"{'Bull call' if direction == Direction.BULLISH else 'Bear put'} spread, "
                          f"tight strikes ($1-2 wide), 0-5 DTE.",
            )

        # Low confidence → stock only or pass
        return OptionsRecommendation(
            strategy=OptionsStrategy.STOCK_ONLY,
            rationale=(
                f"Low confidence ({score:.0f}). Options leverage is inappropriate. "
                f"Trade stock for reduced risk, or wait for better setup."
            ),
            structure="Stock shares only. Smaller position size.",
        )

    def _swing_strategy(
        self, direction: Direction, iv_rank: float,
        score: float, catalyst_risk: EventRisk
    ) -> OptionsRecommendation:
        """Swing trades: IV environment drives premium buying vs selling."""

        # ─── High IV → Sell premium ───────────────────────────────────────
        if iv_rank >= 60:
            if direction == Direction.BULLISH and score >= 55:
                return OptionsRecommendation(
                    strategy=OptionsStrategy.BULL_PUT_SPREAD,
                    rationale=(
                        f"IV rank {iv_rank:.0f} is elevated — favor selling premium. "
                        f"Bull put spread collects credit with defined downside risk. "
                        f"Theta decay works in your favor."
                    ),
                    structure="Sell put spread below support. 30-45 DTE. "
                              "Short strike at or below key support level.",
                )
            elif direction == Direction.BEARISH and score >= 55:
                return OptionsRecommendation(
                    strategy=OptionsStrategy.BEAR_CALL_SPREAD,
                    rationale=(
                        f"IV rank {iv_rank:.0f} is elevated — favor selling premium. "
                        f"Bear call spread profits from theta + directional move down."
                    ),
                    structure="Sell call spread above resistance. 30-45 DTE. "
                              "Short strike at or above key resistance level.",
                )
            elif direction == Direction.NEUTRAL or score < 55:
                return OptionsRecommendation(
                    strategy=OptionsStrategy.IRON_CONDOR,
                    rationale=(
                        f"High IV ({iv_rank:.0f}) + neutral/low-conviction direction. "
                        f"Iron condor profits from range-bound action and IV crush."
                    ),
                    structure="Iron condor with wings outside expected move. 30-45 DTE. "
                              "Manage at 50% max profit or 2x credit received loss.",
                )

        # ─── Low IV → Buy premium ────────────────────────────────────────
        if iv_rank < 30:
            if score >= 65 and direction != Direction.NEUTRAL:
                strategy = OptionsStrategy.LONG_CALL if direction == Direction.BULLISH else OptionsStrategy.LONG_PUT
                return OptionsRecommendation(
                    strategy=strategy,
                    rationale=(
                        f"IV rank {iv_rank:.0f} is low — premium is cheap. "
                        f"High confidence ({score:.0f}) supports directional long options. "
                        f"Potential for IV expansion adds to profit."
                    ),
                    structure=f"Buy {'call' if direction == Direction.BULLISH else 'put'}, "
                              f"ATM or 1 strike OTM. 30-60 DTE for time. "
                              f"Look for potential IV expansion catalyst.",
                )

            # Lower confidence + low IV → debit spread for defined risk
            if direction != Direction.NEUTRAL:
                if direction == Direction.BULLISH:
                    strategy = OptionsStrategy.BULL_CALL_SPREAD
                else:
                    strategy = OptionsStrategy.BEAR_PUT_SPREAD

                return OptionsRecommendation(
                    strategy=strategy,
                    rationale=(
                        f"Low IV ({iv_rank:.0f}) + moderate confidence ({score:.0f}). "
                        f"Debit spread is cost-effective with defined max loss."
                    ),
                    structure=f"{'Bull call' if direction == Direction.BULLISH else 'Bear put'} spread, "
                              f"21-45 DTE. Strikes around key technical levels.",
                )

        # ─── Mid IV → Context-dependent ──────────────────────────────────
        if score >= 70 and direction != Direction.NEUTRAL:
            # High conviction in mid-IV → long options
            strategy = OptionsStrategy.LONG_CALL if direction == Direction.BULLISH else OptionsStrategy.LONG_PUT
            return OptionsRecommendation(
                strategy=strategy,
                rationale=(
                    f"Mid IV ({iv_rank:.0f}) + high confidence ({score:.0f}). "
                    f"Strong setup justifies long premium exposure."
                ),
                structure=f"Buy {'call' if direction == Direction.BULLISH else 'put'}, "
                          f"ATM to slightly OTM. 30-45 DTE.",
            )

        if direction != Direction.NEUTRAL:
            # Default swing: debit spread
            if direction == Direction.BULLISH:
                strategy = OptionsStrategy.BULL_CALL_SPREAD
            else:
                strategy = OptionsStrategy.BEAR_PUT_SPREAD

            return OptionsRecommendation(
                strategy=strategy,
                rationale=(
                    f"Mid IV ({iv_rank:.0f}) + moderate confidence ({score:.0f}). "
                    f"Debit spread balances directional exposure with defined risk."
                ),
                structure=f"{'Bull call' if direction == Direction.BULLISH else 'Bear put'} spread, "
                          f"21-45 DTE.",
            )

        # Neutral / no edge
        return OptionsRecommendation(
            strategy=OptionsStrategy.STOCK_ONLY,
            rationale=f"No clear directional edge (score: {score:.0f}). "
                      f"Avoid options. Trade stock or wait.",
            structure="Stock only or no trade.",
        )

    def _earnings_play(
        self, direction: Direction, iv_rank: float, score: float
    ) -> OptionsRecommendation:
        """Special handling for earnings proximity."""

        # Pre-earnings: IV is typically inflated
        if direction == Direction.NEUTRAL or score < 60:
            return OptionsRecommendation(
                strategy=OptionsStrategy.IRON_CONDOR,
                rationale=(
                    f"Earnings within 3 days. IV is elevated (rank: {iv_rank:.0f}). "
                    f"Iron condor profits from post-earnings IV crush "
                    f"if stock stays within expected move."
                ),
                structure="Iron condor with wings at expected move boundaries. "
                          "Expiry immediately after earnings.",
            )

        if score >= 70:
            # High conviction directional earnings play
            strategy = OptionsStrategy.LONG_CALL if direction == Direction.BULLISH else OptionsStrategy.LONG_PUT
            return OptionsRecommendation(
                strategy=strategy,
                rationale=(
                    f"High conviction ({score:.0f}) directional earnings play. "
                    f"WARNING: IV crush will erode premium post-earnings even if "
                    f"direction is correct. Stock must move beyond expected move to profit."
                ),
                structure=f"Buy {'call' if direction == Direction.BULLISH else 'put'}, "
                          f"slightly OTM past expected move. Use defined risk (debit spread) "
                          f"to reduce IV crush impact.",
            )

        # Moderate conviction → straddle/strangle for vol expansion
        return OptionsRecommendation(
            strategy=OptionsStrategy.STRANGLE,
            rationale=(
                f"Earnings play with directional lean but not enough conviction "
                f"for pure directional. Strangle profits from large move in either direction."
            ),
            structure="Buy strangle: OTM call + OTM put, expiry right after earnings. "
                      "Requires move beyond both breakevens.",
        )

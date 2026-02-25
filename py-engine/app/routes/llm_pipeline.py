"""
TradePilot LLM Pipeline
5-stage reasoning chain using Claude API (Opus).
Stages 1-2 run once per session (cached). Stages 3-5 run per ticker.
"""

import json
import anthropic
from datetime import datetime
from typing import Optional
from app.models.schemas import (
    IndicatorSnapshot, MarketRegime, CatalystContext,
    ConfidenceBreakdown, TradePlan, TradeType, Direction,
    SessionContext, OptionsRecommendation
)


class LLMPipeline:
    """
    Orchestrates the 5-stage LLM reasoning pipeline.
    
    Session-level (run once, cached):
        Stage 1: Catalyst & Macro Context (with web search for real-time data)
        Stage 2: Market Regime Analysis
    
    Per-ticker:
        Stage 3: Technical Analysis
        Stage 4: Risk Scenario Modeling
        Stage 5: Trade Plan Synthesis
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.session_context: Optional[SessionContext] = None

    def _call_claude(self, system: str, user: str, max_tokens: int = 4096) -> str:
        """Make a single Claude API call (no tools)."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    def _call_claude_with_search(self, system: str, user: str, max_tokens: int = 4096) -> str:
        """
        Make a Claude API call with web search enabled.
        Used for Stage 1 to pull real-time macro calendar, news, and geopolitical data.
        Claude will autonomously search when it needs current information.
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": user}],
        )
        # Extract all text blocks from the response (web search returns mixed content)
        text_parts = []
        for block in message.content:
            if hasattr(block, "text") and block.text is not None and isinstance(block.text, str):
                text_parts.append(block.text)
        return "\n".join(text_parts)

    # ─── Session-Level Stages ─────────────────────────────────────────────

    def run_session_stages(
        self,
        regime: MarketRegime,
        catalysts: CatalystContext,
        session_id: str = "default",
        cross_asset_data: dict = None,
    ) -> SessionContext:
        """
        Run Stages 1-2 once per session. Results are cached and reused
        for all ticker analyses in this session.
        """

        # Format cross-asset data for LLM consumption
        cross_asset_text = ""
        if cross_asset_data:
            from app.data.cross_asset import format_cross_asset_for_llm
            cross_asset_text = format_cross_asset_for_llm(cross_asset_data)

        # Stage 1: Catalyst & Macro Context (now with cross-asset data)
        stage1_output = self._stage1_catalyst_context(regime, catalysts, cross_asset_text)

        # Stage 2: Market Regime Deep Analysis (now with cross-asset data)
        stage2_output = self._stage2_regime_analysis(regime, stage1_output, cross_asset_text)

        self.session_context = SessionContext(
            session_id=session_id,
            regime=regime,
            catalysts=catalysts,
            cross_asset_data=cross_asset_data,
            stage1_output=stage1_output,
            stage2_output=stage2_output,
        )

        return self.session_context

    def _stage1_catalyst_context(
        self, regime: MarketRegime, catalysts: CatalystContext, cross_asset_text: str = ""
    ) -> str:
        """
        Stage 1: Analyze the catalyst environment for the week.
        Uses web search to pull real-time macro calendar, news, and geopolitical data.
        Now includes cross-asset market data (bonds, credit, commodities, dollar, breadth).
        """

        system = """You are a macro strategist at a professional trading desk. Your job is to 
assess the current catalyst environment and its impact on trading conditions.

You MUST use web search to find:
1. This week's economic calendar (CPI, PPI, FOMC, NFP, PCE, GDP, ISM, retail sales, etc.)
2. Any active geopolitical situations affecting markets (conflicts, trade disputes, sanctions, political crises)
3. Recent market-moving news from the past 48 hours

Search for these proactively — do not rely on memory for dates or current events.

You have been given real quantitative cross-asset data — USE IT to validate or contradict what
web search tells you. For example, if news says "risk-off" but HYG is rallying, note that divergence.
The numbers don't lie — prioritize quantitative data over narrative when they conflict.

You think in terms of risk events, historical analogs, and probability-weighted outcomes.
You never hedge with vague language — you state your assessment directly.

Output format: Structured analysis with clear sections. No fluff."""

        earnings_str = "\n".join([
            f"  - {e.ticker} on {e.date} {'(BELLWETHER — affects: ' + ', '.join(e.affected_tickers) + ')' if e.is_bellwether else ''}"
            for e in catalysts.earnings_this_week
        ]) or "  None in the next 14 days"

        user = f"""Analyze the catalyst environment for this week's trading.

CRITICAL: Use web search to find:
- This week's US economic calendar (search "economic calendar this week" or "US economic data releases this week")  
- Any active geopolitical risks (search "geopolitical risks markets today" or "market moving news today")
- Any major central bank decisions globally this week

CURRENT DATE: {datetime.now().strftime('%Y-%m-%d %A')}

MARKET SNAPSHOT (from quantitative engine — these are real numbers, not estimates):
- SPY Regime: {regime.spy_regime.value}
- QQQ Regime: {regime.qqq_regime.value}
- VIX: {regime.vix} (Percentile: {regime.vix_percentile}%)
- VIX Term Structure: {regime.vix_term_structure}
- Market Bias: {regime.bias.value}

EARNINGS UPCOMING (auto-detected from market data):
{earnings_str}

SECTOR LEADERSHIP:
- Leaders: {', '.join([f"{s.sector} ({s.etf}: {s.performance_1w:+.1f}%)" for s in regime.sector_leaders if s.performance_1w is not None]) or 'N/A'}
- Laggards: {', '.join([f"{s.sector} ({s.etf}: {s.performance_1w:+.1f}%)" for s in regime.sector_laggards if s.performance_1w is not None]) or 'N/A'}

{cross_asset_text}

After searching, provide:
1. THIS WEEK'S DOMINANT NARRATIVE — What is the market focused on?
2. SCHEDULED MACRO EVENTS — List every data release and Fed event this week with dates, expected impact (low/moderate/high/extreme), and historical context for how surprise outcomes typically move markets
3. GEOPOLITICAL ASSESSMENT — For any active situations, identify the closest historical analog and estimate impact magnitude/duration/sector effects. Include:
   - Classification (military conflict / trade war / banking crisis / political instability / sanctions)
   - Historical analog with specific market data (e.g., "Russia-Ukraine 2022: SPY -6.2%, recovery 28 days")
   - Which sectors are helped/hurt
4. POSITIONING BIAS — risk-on / risk-off / neutral / wait-for-catalyst, with reasoning
5. SECTORS TO FAVOR/AVOID — Based on the catalyst environment
6. HIDDEN CORRELATION RISKS — Bellwether earnings that could move seemingly unrelated positions"""

        return self._call_claude_with_search(system, user, max_tokens=4000)

    def _stage2_regime_analysis(self, regime: MarketRegime, stage1_output: str, cross_asset_text: str = "") -> str:
        """Stage 2: Deep market regime analysis informed by catalyst context and cross-asset data."""

        system = """You are a market structure analyst. You specialize in identifying market regimes,
trend health, and the interaction between technical conditions and macro catalysts.

You have been given real quantitative cross-asset data from bonds, credit, commodities, dollar,
and breadth instruments. USE THIS DATA to validate your regime assessment. Cross-asset confirmation
dramatically increases conviction. Cross-asset divergence is a warning signal.

Your analysis should be actionable — tell the trader what types of setups to favor
in this environment and what to avoid. Be specific about why."""

        user = f"""Given the catalyst context below and the current market data, provide a deep 
regime analysis.

CATALYST CONTEXT (from macro strategist):
{stage1_output}

MARKET DATA:
- SPY: {regime.spy_regime.value}, Direction: {regime.market_direction.value}
- SPY vs EMAs: {json.dumps(regime.spy_vs_emas)}
- QQQ: {regime.qqq_regime.value}
- VIX: {regime.vix} ({regime.volatility_regime})
- VIX Percentile: {regime.vix_percentile}%
- Term Structure: {regime.vix_term_structure}
- Overall Bias: {regime.bias.value}

{cross_asset_text}

Provide:
1. REGIME CLASSIFICATION — What type of market are we in? Use the cross-asset signals to confirm or challenge. If bonds say "risk-off" but equities say "range-bound", identify that divergence.
2. TREND HEALTH — Is the trend healthy or showing signs of exhaustion? What are the warning signs? Use breadth data (IWM, RSP) and credit (HYG) to assess participation.
3. SETUP PREFERENCES — Which setup types are highest probability in this regime?
   - Breakouts vs. mean reversion vs. momentum continuation
   - Day trade vs. swing suitability
4. RISK PARAMETERS — How should position sizing and stop placement adapt to this regime? Use ATR and VIX for sizing guidance.
5. KEY LEVELS — What SPY/QQQ levels would change the regime if broken? Include cross-asset trigger levels (e.g., "if TLT breaks above X, recession trade accelerates").
6. WHAT WOULD CHANGE YOUR MIND — What development would shift the regime? Include cross-asset triggers."""

        return self._call_claude(system, user, max_tokens=2500)

    # ─── Per-Ticker Stages ────────────────────────────────────────────────

    def analyze_ticker(
        self,
        indicators: IndicatorSnapshot,
        confidence: ConfidenceBreakdown,
        options_rec: Optional[OptionsRecommendation],
        trade_type: TradeType,
        direction: Direction,
        prior_trades: list[dict] = None,
        correlated_bellwethers: list[str] = None,
    ) -> TradePlan:
        """
        Run Stages 3-5 for a specific ticker.
        Requires session_context to be populated (Stages 1-2).
        """
        if not self.session_context:
            raise RuntimeError("Session context not initialized. Run run_session_stages() first.")

        # Stage 3: Technical Analysis
        stage3 = self._stage3_technical(indicators, direction, trade_type)

        # Stage 4: Risk Scenario Modeling
        stage4 = self._stage4_risk_scenarios(
            indicators, stage3, confidence, direction, correlated_bellwethers or []
        )

        # Stage 5: Trade Plan Synthesis
        plan = self._stage5_synthesis(
            indicators, stage3, stage4, confidence,
            options_rec, trade_type, direction,
            prior_trades or [], correlated_bellwethers or []
        )

        return plan

    def _stage3_technical(
        self, indicators: IndicatorSnapshot, direction: Direction, trade_type: TradeType
    ) -> str:
        """Stage 3: Technical analysis of a specific ticker."""

        system = """You are a technical analyst at a professional trading desk. You analyze 
price action, indicators, and patterns with precision. You identify key levels,
confluences, and potential setups.

You are direct and specific. When you identify a level, you state the price.
When you see a pattern, you name it and explain the implications."""

        ind_json = indicators.model_dump_json(indent=2)

        user = f"""Analyze the following ticker technically.

MARKET CONTEXT (from session analysis):
{self.session_context.stage2_output[:1500]}

PROPOSED DIRECTION: {direction.value}
TRADE TYPE: {trade_type.value}

INDICATOR DATA:
{ind_json}

DETECTED PATTERNS: {', '.join(indicators.patterns) if indicators.patterns else 'None detected'}

Provide:
1. TECHNICAL ASSESSMENT — What is the chart telling us? Trend, momentum, volume confirmation.
2. KEY LEVELS — Support and resistance levels with the indicator/method that defines them.
3. PATTERN ANALYSIS — Any actionable patterns? Quality of the setup?
4. CONFLUENCE ZONES — Where do multiple indicators agree? These are highest probability levels.
5. DIRECTIONAL BIAS — Does the technical picture support the proposed {direction.value} direction?
6. CONCERNS — What technical red flags exist? Divergences, weak volume, overhead resistance?
7. OPTIMAL ENTRY — Where would you enter, and what confirmation would you wait for?"""

        return self._call_claude(system, user, max_tokens=2500)

    def _stage4_risk_scenarios(
        self, indicators: IndicatorSnapshot, stage3_output: str,
        confidence: ConfidenceBreakdown, direction: Direction,
        correlated_bellwethers: list[str]
    ) -> str:
        """Stage 4: Model best/base/worst case scenarios."""

        system = """You are a risk manager at a professional trading desk. You think in scenarios 
and probabilities. Your job is to identify what could go right, what could go wrong,
and what would invalidate the thesis entirely.

You are the voice of caution. You identify risks others miss."""

        bellwether_str = (
            f"\nCORRELATED BELLWETHERS REPORTING SOON: {', '.join(correlated_bellwethers)}"
            if correlated_bellwethers else ""
        )

        user = f"""Model risk scenarios for this trade.

TICKER: {indicators.ticker} @ ${indicators.price}
DIRECTION: {direction.value}
ATR: ${indicators.atr_14} ({indicators.atr_percent}% of price)

CONFIDENCE BREAKDOWN:
- Trend: {confidence.trend_alignment:.0f}/100
- Momentum: {confidence.momentum_confirmation:.0f}/100
- Volume: {confidence.volume_confirmation:.0f}/100
- Regime: {confidence.regime_alignment:.0f}/100
- Catalyst: {confidence.catalyst_alignment:.0f}/100
- Composite: {confidence.composite:.0f}/100 — {confidence.rating}

TECHNICAL ANALYSIS (from chartist):
{stage3_output[:1500]}

CATALYST CONTEXT:
{self.session_context.stage1_output[:1000]}
{bellwether_str}

Provide:
1. BEST CASE SCENARIO — What happens if everything goes right? Target levels and probability.
2. BASE CASE SCENARIO — Most likely outcome. Expected move and probability.
3. WORST CASE SCENARIO — What happens if it goes wrong? Where does it stop? Probability.
4. BLACK SWAN SCENARIO — Low probability but high impact. What would cause a catastrophic move?
5. THESIS INVALIDATION — What specific condition (not just a price) would kill this trade?
   Example: "If price closes back inside the range on volume > 2x average, the breakout thesis is dead."
6. CATALYST RISK — How do upcoming events specifically threaten this position?
7. CORRELATION WARNING — {f"This ticker is correlated with {', '.join(correlated_bellwethers)} which report soon. Assess the hidden exposure." if correlated_bellwethers else "No direct bellwether correlation detected."}"""

        return self._call_claude(system, user, max_tokens=2500)

    def _stage5_synthesis(
        self, indicators: IndicatorSnapshot, stage3: str, stage4: str,
        confidence: ConfidenceBreakdown, options_rec: Optional[OptionsRecommendation],
        trade_type: TradeType, direction: Direction,
        prior_trades: list[dict], correlated_bellwethers: list[str]
    ) -> TradePlan:
        """Stage 5: Synthesize everything into a final trade plan."""

        system = """You are the portfolio manager synthesizing all analysis into a final trade plan.
You have received input from the macro strategist (Stage 1), market structure analyst (Stage 2),
technical analyst (Stage 3), and risk manager (Stage 4).

Your job is to make the final call. You produce a specific, actionable trade plan with
exact levels, exact stops, exact targets, and a clear thesis.

RESPOND IN VALID JSON matching this structure exactly:
{
    "thesis": "Clear, specific thesis in 2-3 sentences",
    "setup_type": "bull_flag|breakout|mean_reversion|trend_continuation|gap_fill|etc",
    "entry_zone": "Specific price or condition, e.g. 'Break above $185 with volume > 1.5x avg'",
    "stop_loss": 175.50,
    "stop_loss_rationale": "Below the 20 EMA and prior swing low",
    "targets": [
        {"price": 190.00, "pct_exit": 50, "rationale": "Prior resistance"},
        {"price": 195.00, "pct_exit": 100, "rationale": "Measured move target"}
    ],
    "risk_reward_ratio": 2.5,
    "thesis_invalidation": "Specific non-price condition that kills the trade",
    "catalyst_awareness": "How upcoming events affect this trade",
    "correlation_warnings": ["warning 1", "warning 2"],
    "market_regime_summary": "One sentence regime context",
    "historical_analog_score": 65
}"""

        prior_trades_str = ""
        if prior_trades:
            recent = prior_trades[:5]
            prior_trades_str = f"""

PRE-TRADE COMPARISON — YOUR HISTORY WITH THIS TYPE OF SETUP:
{json.dumps(recent, indent=2, default=str)}
Consider: What worked and what didn't in your past trades on similar setups?"""

        options_str = ""
        if options_rec:
            options_str = f"""

OPTIONS RECOMMENDATION (from quant engine):
Strategy: {options_rec.strategy.value}
Rationale: {options_rec.rationale}
Structure: {options_rec.structure}"""

        user = f"""Synthesize the following analysis into a final trade plan.

TICKER: {indicators.ticker} @ ${indicators.price}
DIRECTION: {direction.value}
TRADE TYPE: {trade_type.value}
CONFIDENCE: {confidence.composite:.0f}/100 — {confidence.rating}

SESSION CONTEXT:
{self.session_context.stage1_output[:800]}
{self.session_context.stage2_output[:800]}

TECHNICAL ANALYSIS (Stage 3):
{stage3[:1200]}

RISK SCENARIOS (Stage 4):
{stage4[:1200]}
{options_str}
{prior_trades_str}

Key indicators:
- Price: ${indicators.price} | EMA9: ${indicators.ema_9} | EMA20: ${indicators.ema_20} | EMA200: ${indicators.ema_200}
- RSI: {indicators.rsi_14} | MACD Hist: {indicators.macd.histogram if indicators.macd else 'N/A'}
- RVOL: {indicators.rvol} | ATR: ${indicators.atr_14} ({indicators.atr_percent}%)
- Patterns: {', '.join(indicators.patterns) if indicators.patterns else 'None'}

Produce the final trade plan as JSON. Be extremely specific with price levels."""

        raw = self._call_claude(system, user, max_tokens=2000)

        # Parse the JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0]

            plan_data = json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            # Fallback: create plan from raw text
            plan_data = {
                "thesis": raw[:500],
                "setup_type": "manual_review",
                "entry_zone": "See analysis",
                "stop_loss": indicators.price * 0.95,
                "stop_loss_rationale": "Default 5% stop — manual review required",
                "targets": [{"price": indicators.price * 1.10, "pct_exit": 100, "rationale": "Default target"}],
                "risk_reward_ratio": 2.0,
                "thesis_invalidation": "Review Stage 4 risk scenarios",
                "catalyst_awareness": "Review Stage 1 catalyst context",
                "correlation_warnings": [],
                "market_regime_summary": "Review Stage 2",
                "historical_analog_score": 50,
            }

        # Update historical analog score in confidence
        analog_score = plan_data.get("historical_analog_score", 50)
        confidence.historical_analog = min(100, max(0, analog_score))

        return TradePlan(
            ticker=indicators.ticker,
            trade_type=trade_type,
            direction=direction,
            thesis=plan_data.get("thesis", ""),
            setup_type=plan_data.get("setup_type", "unknown"),
            entry_zone=plan_data.get("entry_zone", ""),
            stop_loss=float(plan_data.get("stop_loss", indicators.price * 0.95)),
            stop_loss_rationale=plan_data.get("stop_loss_rationale", ""),
            targets=plan_data.get("targets", []),
            risk_reward_ratio=float(plan_data.get("risk_reward_ratio", 0)),
            thesis_invalidation=plan_data.get("thesis_invalidation", ""),
            options_rec=options_rec,
            confidence=confidence,
            catalyst_awareness=plan_data.get("catalyst_awareness", ""),
            correlation_warnings=plan_data.get("correlation_warnings", []),
            market_regime_summary=plan_data.get("market_regime_summary", ""),
            indicators_used=indicators,
        )

    # ─── Feedback: Post-Trade Debrief ─────────────────────────────────────

    def generate_debrief(self, trade_plan: TradePlan, journal_entry: dict) -> str:
        """Generate an immediate post-trade debrief from the LLM."""

        system = """You are a trading coach reviewing a completed trade. Your job is to identify
what worked, what didn't, and extract a specific, actionable lesson.

Be direct. Don't sugarcoat losses or inflate wins. Focus on process, not outcomes."""

        user = f"""Review this completed trade:

ORIGINAL PLAN:
- Ticker: {trade_plan.ticker} | Direction: {trade_plan.direction.value}
- Thesis: {trade_plan.thesis}
- Entry Zone: {trade_plan.entry_zone}
- Stop: ${trade_plan.stop_loss} | Targets: {json.dumps(trade_plan.targets)}
- Confidence: {trade_plan.confidence.composite:.0f}/100

ACTUAL EXECUTION:
- Entry: ${journal_entry.get('actual_entry')}
- Exit: ${journal_entry.get('actual_exit')}
- P/L: {journal_entry.get('pnl_percent', 0):.1f}%
- Followed plan: {journal_entry.get('followed_plan', 'unknown')}
- Notes: {journal_entry.get('notes', 'None')}

Provide:
1. WHAT WORKED — Specific aspects of the trade that were correct
2. WHAT FAILED — Specific aspects that were wrong and why
3. PROCESS GRADE — Did you follow the plan? A+ to F.
4. KEY LESSON — One specific, actionable takeaway for future trades
5. PATTERN NOTE — Anything about this trade type/setup to remember"""

        return self._call_claude(system, user, max_tokens=1500)

    # ─── Feedback: Weekly Digest ──────────────────────────────────────────

    def generate_weekly_digest(self, trades: list[dict]) -> str:
        """Generate a weekly performance review from trade history."""

        system = """You are a head of trading reviewing your desk's weekly performance.
Identify systematic patterns, biases, and areas for improvement.
Be analytical and data-driven. Reference specific numbers."""

        trades_str = json.dumps(trades[:20], indent=2, default=str)  # cap at 20 trades

        user = f"""Review this week's trading performance:

TRADES:
{trades_str}

Analyze:
1. WIN RATE — Overall and by setup type
2. BEST SETUP — Which setup type had the highest win rate and average P/L?
3. WORST SETUP — Which should be avoided or improved?
4. DISCIPLINE — How often was the plan followed? What happened when it wasn't?
5. TIMING — Any patterns in when trades work best (day of week, time of day)?
6. RISK MANAGEMENT — Were stops honored? Were profits taken at targets?
7. BIAS CHECK — Any systematic biases? (always bullish, oversizing, revenge trading)
8. TOP 3 IMPROVEMENTS — Specific, actionable changes for next week"""

        return self._call_claude(system, user, max_tokens=2500)

    # ─── Interactive Chat ─────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        trade_plans: list[dict] = None,
        performance_stats: dict = None,
    ) -> str:
        """
        Interactive chat with full session context.
        The user can ask follow-up questions about the week's analysis,
        specific trade plans, market conditions, or strategy.
        """
        if not self.session_context:
            raise RuntimeError("No active session. Initialize session first.")

        # Build the context block that gives the LLM full awareness
        context_parts = []

        context_parts.append(f"""=== STAGE 1: CATALYST & MACRO CONTEXT ===
{self.session_context.stage1_output}""")

        context_parts.append(f"""=== STAGE 2: MARKET REGIME ANALYSIS ===
{self.session_context.stage2_output}""")

        regime = self.session_context.regime
        context_parts.append(f"""=== CURRENT MARKET DATA ===
SPY Regime: {regime.spy_regime.value}
QQQ Regime: {regime.qqq_regime.value}
VIX: {regime.vix} (Percentile: {regime.vix_percentile}%, Regime: {regime.volatility_regime})
Term Structure: {regime.vix_term_structure}
Market Bias: {regime.bias.value}
Sector Leaders: {', '.join(f"{s.sector} ({s.etf}: {s.performance_1w:+.1f}%)" for s in regime.sector_leaders if s.performance_1w is not None) or 'N/A'}
Sector Laggards: {', '.join(f"{s.sector} ({s.etf}: {s.performance_1w:+.1f}%)" for s in regime.sector_laggards if s.performance_1w is not None) or 'N/A'}""")

        # Add cross-asset data to chat context
        if self.session_context.cross_asset_data:
            from app.data.cross_asset import format_cross_asset_for_llm
            cross_asset_text = format_cross_asset_for_llm(self.session_context.cross_asset_data)
            context_parts.append(cross_asset_text)

        catalysts = self.session_context.catalysts
        earnings_str = ", ".join(
            f"{e.ticker} ({e.date}{'*' if e.is_bellwether else ''})"
            for e in catalysts.earnings_this_week
        ) or "None"
        context_parts.append(f"""=== CATALYST ENVIRONMENT ===
Event Risk: {catalysts.overall_event_risk.value}
Earnings This Week: {earnings_str}
(* = bellwether)""")

        if trade_plans:
            plans_summary = []
            for p in trade_plans[:10]:
                conf = p.get('confidence', {})
                comp = conf.get('composite', '?') if isinstance(conf, dict) else '?'
                plans_summary.append(
                    f"- {p.get('ticker', '?')} | {p.get('direction', '?')} {p.get('trade_type', '?')} | "
                    f"Entry: {p.get('entry_zone', '?')} | Stop: ${p.get('stop_loss', '?')} | "
                    f"R:R {p.get('risk_reward_ratio', '?')}:1 | "
                    f"Confidence: {comp} | "
                    f"Thesis: {str(p.get('thesis', '?'))[:120]}"
                )
            context_parts.append(f"""=== TRADE PLANS THIS SESSION ===
{chr(10).join(plans_summary)}""")

        if performance_stats and performance_stats.get("total_trades", 0) > 0:
            context_parts.append(f"""=== YOUR PERFORMANCE (last {performance_stats.get('period_days', 30)} days) ===
Total Trades: {performance_stats.get('total_trades')}
Win Rate: {performance_stats.get('win_rate')}%
Avg Win: +{performance_stats.get('avg_win')}% | Avg Loss: {performance_stats.get('avg_loss')}%
Profit Factor: {performance_stats.get('profit_factor')}
Total P/L: {performance_stats.get('total_pnl_pct')}%""")

        full_context = "\n\n".join(context_parts)

        system = f"""You are a senior trading strategist having an interactive conversation with a trader.
You have complete access to today's session analysis, market data, cross-asset data (bonds, credit,
commodities, dollar, breadth), and the trader's plans and performance.

YOUR CONTEXT (reference this to answer questions):
{full_context}

RULES:
- Be direct and specific. When you reference a level, state the price. When you cite data, use the numbers.
- When discussing intermarket relationships, reference the actual cross-asset data you have (e.g., "TLT is +1.2% this week confirming the flight to safety thesis").
- If asked about a specific trade plan, reference the actual thesis, levels, and confidence scores.
- If asked "what if" scenarios, reason through them using the indicator and regime data you have.
- If asked about risk, quantify it using ATR, VIX, and historical analogs from the catalyst analysis.
- If the trader asks about adjusting a plan (moving stops, changing targets), evaluate whether the
  adjustment makes sense given the technical and catalyst context.
- If you don't have enough data to answer, say so clearly rather than guessing.
- Keep responses focused and actionable. You're at a trading desk, not writing an essay."""

        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system,
            messages=api_messages,
        )

        return response.content[0].text
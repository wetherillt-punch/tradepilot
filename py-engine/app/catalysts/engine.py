"""
TradePilot Catalyst Engine
Identifies, categorizes, and historically contextualizes market catalysts.
Three components: Macro Calendar, Earnings Tracker, Geopolitical Monitor.
"""

from datetime import datetime, date, timedelta
from typing import Optional
from app.models.schemas import (
    CatalystContext, ScheduledEvent, EarningsEvent, GeopoliticalEvent,
    CatalystType, EventRisk
)


# ─── Major Bellwether Tickers ─────────────────────────────────────────────────

BELLWETHERS = {
    "AAPL": {"sector": "Technology", "affects": ["MSFT", "GOOGL", "META", "QQQ"]},
    "MSFT": {"sector": "Technology", "affects": ["AAPL", "GOOGL", "CRM", "QQQ"]},
    "NVDA": {"sector": "Semiconductors", "affects": ["AMD", "SMCI", "AVGO", "MU", "TSM", "SOXX"]},
    "AMZN": {"sector": "Consumer/Cloud", "affects": ["SHOP", "GOOGL", "MSFT", "XLY"]},
    "GOOGL": {"sector": "Technology", "affects": ["META", "SNAP", "PINS", "TTD"]},
    "META": {"sector": "Social/Ads", "affects": ["GOOGL", "SNAP", "PINS", "TTD"]},
    "TSLA": {"sector": "EV/Auto", "affects": ["RIVN", "LCID", "NIO", "F", "GM"]},
    "JPM": {"sector": "Financials", "affects": ["BAC", "GS", "MS", "WFC", "XLF"]},
    "GS": {"sector": "Financials", "affects": ["JPM", "MS", "BAC", "XLF"]},
    "WMT": {"sector": "Consumer Staples", "affects": ["TGT", "COST", "KR", "XLP"]},
    "UNH": {"sector": "Healthcare", "affects": ["HUM", "CI", "ELV", "XLV"]},
    "CAT": {"sector": "Industrials", "affects": ["DE", "URI", "XLI"]},
    "XOM": {"sector": "Energy", "affects": ["CVX", "COP", "SLB", "XLE"]},
}


# ─── Historical Macro Event Impact Data ───────────────────────────────────────

MACRO_EVENT_PROFILES = {
    "CPI": {
        "frequency": "monthly",
        "typical_impact": EventRisk.HIGH,
        "avg_spy_move": 0.9,
        "notes": "Hot CPI → yields spike → tech sells, financials rally. Cool CPI → opposite.",
        "affected_sectors": {"XLK": "negative_if_hot", "XLF": "positive_if_hot", "TLT": "negative_if_hot"},
    },
    "PPI": {
        "frequency": "monthly",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.5,
        "notes": "Leading indicator for CPI. Less market-moving alone.",
    },
    "FOMC_DECISION": {
        "frequency": "8x/year",
        "typical_impact": EventRisk.EXTREME,
        "avg_spy_move": 1.2,
        "notes": "Single most important macro event. Pre-FOMC drift tendency. Post-decision vol expansion.",
    },
    "FOMC_MINUTES": {
        "frequency": "8x/year",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.5,
        "notes": "Forward guidance nuance. Can shift rate expectations.",
    },
    "PCE": {
        "frequency": "monthly",
        "typical_impact": EventRisk.HIGH,
        "avg_spy_move": 0.7,
        "notes": "Fed's preferred inflation gauge. Often more market-moving than CPI for rate-sensitive trades.",
    },
    "NFP": {
        "frequency": "monthly",
        "typical_impact": EventRisk.HIGH,
        "avg_spy_move": 0.8,
        "notes": "Strong jobs = hawkish Fed fear. Weak jobs = recession fear. Market wants goldilocks.",
    },
    "JOBLESS_CLAIMS": {
        "frequency": "weekly",
        "typical_impact": EventRisk.LOW,
        "avg_spy_move": 0.2,
        "notes": "Usually only moves markets at extremes (>300k claims).",
    },
    "GDP": {
        "frequency": "quarterly",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.5,
        "notes": "Rarely surprises but revisions matter.",
    },
    "ISM_MANUFACTURING": {
        "frequency": "monthly",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.5,
        "notes": "Below 50 = contraction signal. Leading indicator.",
    },
    "ISM_SERVICES": {
        "frequency": "monthly",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.5,
        "notes": "Services sector is larger portion of economy.",
    },
    "RETAIL_SALES": {
        "frequency": "monthly",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.4,
        "notes": "Consumer spending health. Impacts consumer discretionary sector.",
    },
    "MICHIGAN_SENTIMENT": {
        "frequency": "monthly",
        "typical_impact": EventRisk.LOW,
        "avg_spy_move": 0.3,
        "notes": "Inflation expectations component is what the Fed watches.",
    },
    "TREASURY_AUCTION": {
        "frequency": "regular",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.3,
        "notes": "Weak auctions → yield spikes → equity pressure. 10Y and 30Y most watched.",
    },
    "OPEX": {
        "frequency": "monthly",
        "typical_impact": EventRisk.MODERATE,
        "avg_spy_move": 0.6,
        "notes": "Gamma exposure unwinds, pin risk, increased volatility. Quad witching quarterly.",
    },
}


# ─── Geopolitical Event Templates ─────────────────────────────────────────────

GEOPOLITICAL_TEMPLATES = {
    "military_conflict": {
        "historical_examples": [
            {"name": "Russia-Ukraine 2022", "spy_drawdown": -6.2, "recovery_days": 28, "vix_peak": 36.5},
            {"name": "Gulf War 1990", "spy_drawdown": -19.9, "recovery_days": 189},
            {"name": "Iraq Invasion 2003", "spy_drawdown": -3.1, "recovery_days": 14},
        ],
        "typical_behavior": "Initial sharp selloff (2-5%), flight to safety (bonds, gold, USD), energy spike.",
        "duration": "1-4 weeks for initial shock, months for sector rotation",
        "safe_havens": ["GLD", "TLT", "UUP"],
        "sector_impacts": {"XLE": "positive", "ITA": "positive", "XLK": "negative"},
    },
    "trade_war": {
        "historical_examples": [
            {"name": "US-China 2018-2019", "spy_drawdown": -19.8, "recovery_days": 120},
            {"name": "Trump Tariffs 2025", "spy_drawdown": -15.0, "recovery_days": None},
        ],
        "typical_behavior": "Sector-specific damage (industrials, semis, agriculture), broad uncertainty.",
        "duration": "Months to years — slow burn, not a spike",
        "sector_impacts": {"XLI": "negative", "SOXX": "negative", "XLP": "defensive"},
    },
    "banking_crisis": {
        "historical_examples": [
            {"name": "SVB 2023", "spy_drawdown": -5.0, "recovery_days": 21},
            {"name": "Lehman 2008", "spy_drawdown": -54.0, "recovery_days": 900},
            {"name": "Greece 2011", "spy_drawdown": -19.0, "recovery_days": 150},
        ],
        "typical_behavior": "Contagion fear → financials crash → credit tightens → broad selloff.",
        "duration": "Weeks to years depending on systemic interconnection",
        "sector_impacts": {"XLF": "strongly_negative", "GLD": "positive"},
    },
    "pandemic": {
        "historical_examples": [
            {"name": "COVID 2020", "spy_drawdown": -34.0, "recovery_days": 148},
            {"name": "SARS 2003", "spy_drawdown": -3.0, "recovery_days": 30},
        ],
        "typical_behavior": "Extreme volatility. Travel, hospitality destroyed. Tech, healthcare rally.",
        "duration": "Months",
        "sector_impacts": {"XLK": "positive", "XLV": "positive", "JETS": "strongly_negative"},
    },
    "political_instability": {
        "historical_examples": [
            {"name": "Debt Ceiling 2023", "spy_drawdown": -2.0, "recovery_days": 7},
            {"name": "Debt Ceiling 2011", "spy_drawdown": -19.0, "recovery_days": 150},
            {"name": "Government Shutdown 2018-19", "spy_drawdown": -2.0, "recovery_days": 14},
        ],
        "typical_behavior": "VIX spikes, but historically resolves. Markets recover quickly.",
        "duration": "Days to weeks",
    },
    "sanctions": {
        "historical_examples": [
            {"name": "Russia Sanctions 2022", "spy_drawdown": -3.0, "recovery_days": 21},
        ],
        "typical_behavior": "Commodity spikes (oil, gas, metals), supply chain disruption.",
        "duration": "Months",
        "sector_impacts": {"XLE": "positive", "XLB": "positive"},
    },
}


class CatalystEngine:
    """
    Assembles the complete catalyst context for the current session.
    Combines auto-pulled data with historical profiles.
    """

    def analyze(self, watchlist: list[str] = None) -> CatalystContext:
        """
        Build the full catalyst context.
        Macro calendar and geopolitical events are enriched by LLM Stage 1.
        """
        watchlist = watchlist or []

        # Get earnings data — gracefully handles failures
        earnings = self._get_upcoming_earnings(watchlist)

        context = CatalystContext(
            timestamp=datetime.utcnow(),
            macro_events_this_week=[],
            earnings_this_week=earnings,
            active_geopolitical=[],
            overall_event_risk=self._assess_base_risk(earnings),
        )

        return context

    def _get_upcoming_earnings(self, watchlist: list[str]) -> list[EarningsEvent]:
        """Fetch upcoming earnings for watchlist tickers + bellwethers."""
        earnings = []
        all_tickers = list(set(watchlist + list(BELLWETHERS.keys())))

        for ticker in all_tickers:
            try:
                # Use curl_cffi session to bypass cloud IP blocking
                import yfinance as yf
                try:
                    from curl_cffi import requests as curl_requests
                    session = curl_requests.Session(impersonate="chrome")
                    tk = yf.Ticker(ticker, session=session)
                except (ImportError, Exception):
                    tk = yf.Ticker(ticker)

                cal = tk.calendar

                if cal is None:
                    continue

                # Handle empty check for both dict and DataFrame
                if isinstance(cal, dict):
                    if not cal:
                        continue
                elif hasattr(cal, "empty") and cal.empty:
                    continue

                # yfinance calendar format varies - handle both dict and DataFrame
                if isinstance(cal, dict):
                    earnings_date = cal.get("Earnings Date")
                    if earnings_date and len(earnings_date) > 0:
                        ed = earnings_date[0]
                        if isinstance(ed, str):
                            ed = datetime.strptime(ed, "%Y-%m-%d").date()
                        elif hasattr(ed, "date"):
                            ed = ed.date()
                    else:
                        continue
                else:
                    # DataFrame format
                    if "Earnings Date" in cal.columns:
                        ed_val = cal["Earnings Date"].iloc[0]
                        if hasattr(ed_val, "date"):
                            ed = ed_val.date()
                        else:
                            continue
                    else:
                        continue

                # Only include if within next 14 days
                today = date.today()
                if ed < today or ed > today + timedelta(days=14):
                    continue

                is_bell = ticker in BELLWETHERS
                affected = BELLWETHERS.get(ticker, {}).get("affects", [])

                earnings.append(EarningsEvent(
                    ticker=ticker,
                    date=ed,
                    is_bellwether=is_bell,
                    affected_tickers=affected,
                ))

            except Exception as e:
                print(f"[Catalyst] {ticker} earnings lookup failed: {e}")
                continue

        return sorted(earnings, key=lambda e: e.date)

    def _assess_base_risk(self, earnings: list[EarningsEvent]) -> EventRisk:
        """Assess base risk level from earnings calendar alone."""
        bellwether_count = sum(1 for e in earnings if e.is_bellwether)

        if bellwether_count >= 3:
            return EventRisk.HIGH
        elif bellwether_count >= 1:
            return EventRisk.MODERATE
        return EventRisk.LOW

    @staticmethod
    def get_macro_profile(event_name: str) -> dict:
        """Get historical profile for a macro event type."""
        return MACRO_EVENT_PROFILES.get(event_name, {})

    @staticmethod
    def get_geopolitical_template(event_type: str) -> dict:
        """Get historical template for a geopolitical event type."""
        return GEOPOLITICAL_TEMPLATES.get(event_type, {})

    @staticmethod
    def get_bellwether_info(ticker: str) -> dict:
        """Get bellwether data for correlation warnings."""
        return BELLWETHERS.get(ticker, {})

    @staticmethod
    def find_correlated_bellwethers(ticker: str) -> list[str]:
        """Find which bellwethers affect a given ticker."""
        affected_by = []
        for bell, info in BELLWETHERS.items():
            if ticker in info.get("affects", []):
                affected_by.append(bell)
        return affected_by

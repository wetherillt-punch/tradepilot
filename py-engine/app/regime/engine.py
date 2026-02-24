"""
TradePilot Market Regime Engine
Classifies the current market environment using SPY, QQQ, VIX, and sector data.
Runs once per session and is cached.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from app.models.schemas import (
    MarketRegime, RegimeType, Direction, SectorRotation
)
from app.indicators.engine import IndicatorEngine
from app.data.yahoo_fetcher import fetch_ticker_data


# Sector ETFs for rotation analysis
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Consumer Disc.": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication": "XLC",
}


class RegimeEngine:
    """
    Analyzes broad market conditions to classify the current regime.
    Uses SPY, QQQ, VIX, and sector ETFs.
    """

    def __init__(self):
        self.spy_data: Optional[pd.DataFrame] = None
        self.qqq_data: Optional[pd.DataFrame] = None
        self.vix_data: Optional[pd.DataFrame] = None

    def analyze(self) -> MarketRegime:
        """Run full regime analysis. Returns cached-ready MarketRegime."""

        # Fetch broad market data using direct Yahoo API
        spy = self._fetch("SPY", period="1y")
        qqq = self._fetch("QQQ", period="1y")
        vix = self._fetch("^VIX", period="1y")

        self.spy_data = spy
        self.qqq_data = qqq
        self.vix_data = vix

        # Classify SPY and QQQ regimes
        spy_regime = self._classify_regime(spy)
        qqq_regime = self._classify_regime(qqq)

        # SPY vs EMAs
        spy_latest = spy.iloc[-1] if len(spy) > 0 else pd.Series()
        spy_vs_emas = {}
        for ema_col in ["ema_9", "ema_20", "ema_50", "ema_200"]:
            if ema_col in spy_latest.index and pd.notna(spy_latest.get(ema_col)):
                spy_vs_emas[ema_col] = "above" if spy_latest["close"] > spy_latest[ema_col] else "below"

        # Market direction
        if spy_regime in [RegimeType.STRONG_UPTREND, RegimeType.UPTREND]:
            market_dir = Direction.BULLISH
        elif spy_regime in [RegimeType.STRONG_DOWNTREND, RegimeType.DOWNTREND]:
            market_dir = Direction.BEARISH
        else:
            market_dir = Direction.NEUTRAL

        # VIX analysis
        vix_current = vix["close"].iloc[-1] if len(vix) > 0 else 20.0
        vix_1yr = vix["close"].tail(252) if len(vix) >= 252 else vix["close"]
        vix_percentile = float(
            (vix_1yr < vix_current).sum() / len(vix_1yr) * 100
        ) if len(vix_1yr) > 0 else 50.0

        # VIX term structure approximation (using recent VIX trend)
        if len(vix) >= 5:
            vix_5d_ago = vix["close"].iloc[-5]
            vix_term = "contango" if vix_current < vix_5d_ago else "backwardation"
        else:
            vix_term = "contango"

        # Volatility regime
        if vix_current < 15:
            vol_regime = "low"
        elif vix_current < 20:
            vol_regime = "normal"
        elif vix_current < 30:
            vol_regime = "elevated"
        else:
            vol_regime = "extreme"

        # Sector rotation
        sectors = self._analyze_sectors()
        leaders = sorted(sectors, key=lambda s: s.performance_1w or 0, reverse=True)[:3]
        laggards = sorted(sectors, key=lambda s: s.performance_1w or 0)[:3]

        # Overall bias
        bullish_signals = 0
        bearish_signals = 0

        if spy_regime in [RegimeType.STRONG_UPTREND, RegimeType.UPTREND]:
            bullish_signals += 2
        elif spy_regime in [RegimeType.STRONG_DOWNTREND, RegimeType.DOWNTREND]:
            bearish_signals += 2

        if vix_current < 18:
            bullish_signals += 1
        elif vix_current > 25:
            bearish_signals += 1

        if vix_term == "contango":
            bullish_signals += 1
        else:
            bearish_signals += 1

        if bullish_signals > bearish_signals + 1:
            bias = Direction.BULLISH
        elif bearish_signals > bullish_signals + 1:
            bias = Direction.BEARISH
        else:
            bias = Direction.NEUTRAL

        return MarketRegime(
            timestamp=datetime.utcnow(),
            spy_regime=spy_regime,
            qqq_regime=qqq_regime,
            spy_vs_emas=spy_vs_emas,
            market_direction=market_dir,
            vix=round(float(vix_current), 2),
            vix_percentile=round(vix_percentile, 1),
            vix_term_structure=vix_term,
            volatility_regime=vol_regime,
            sector_leaders=leaders,
            sector_laggards=laggards,
            bias=bias,
        )

    def _fetch(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Fetch data and compute EMAs for regime classification."""
        df = fetch_ticker_data(ticker, period=period, interval="1d")

        if df.empty:
            return pd.DataFrame()

        # Compute EMAs
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["rsi_14"] = IndicatorEngine._compute_rsi(df["close"], 14)
        df["atr_14"] = IndicatorEngine._compute_atr(df, 14)

        return df

    def _classify_regime(self, df: pd.DataFrame) -> RegimeType:
        """Classify trend regime from price data with EMAs and ADX-like logic."""
        if df.empty or len(df) < 50:
            return RegimeType.RANGE_BOUND

        latest = df.iloc[-1]
        price = latest["close"]

        # EMA positioning
        above_9 = price > latest.get("ema_9", price)
        above_20 = price > latest.get("ema_20", price)
        above_50 = price > latest.get("ema_50", price)
        above_200 = price > latest.get("ema_200", price)

        above_count = sum([above_9, above_20, above_50, above_200])

        # Trend slope (20-day EMA slope)
        if len(df) >= 25:
            ema20_now = latest.get("ema_20", price)
            ema20_5d_ago = df.iloc[-6].get("ema_20", price)
            slope = (ema20_now - ema20_5d_ago) / ema20_5d_ago * 100 if ema20_5d_ago > 0 else 0
        else:
            slope = 0

        # ATR-based volatility check
        atr_pct = (latest.get("atr_14", 0) / price * 100) if price > 0 else 0

        # High volatility override
        if atr_pct > 4:
            return RegimeType.HIGH_VOLATILITY

        # Trend classification
        if above_count == 4 and slope > 0.5:
            return RegimeType.STRONG_UPTREND
        elif above_count >= 3 and slope > 0:
            return RegimeType.UPTREND
        elif above_count <= 1 and slope < -0.5:
            return RegimeType.STRONG_DOWNTREND
        elif above_count <= 1 and slope < 0:
            return RegimeType.DOWNTREND
        else:
            return RegimeType.RANGE_BOUND

    def _analyze_sectors(self) -> list[SectorRotation]:
        """Analyze sector ETF performance for rotation signals."""
        sectors = []

        for name, etf in SECTOR_ETFS.items():
            try:
                hist = fetch_ticker_data(etf, period="1mo", interval="1d")
                if hist.empty or len(hist) < 5:
                    continue

                close = hist["close"]

                perf_1w = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100 if len(close) >= 5 else None
                perf_1m = ((close.iloc[-1] / close.iloc[0]) - 1) * 100

                # Relative strength vs SPY
                rel_str = None
                if self.spy_data is not None and len(self.spy_data) >= 5:
                    spy_perf = ((self.spy_data["close"].iloc[-1] / self.spy_data["close"].iloc[-5]) - 1) * 100
                    rel_str = round(perf_1w - spy_perf, 2) if perf_1w else None

                sectors.append(SectorRotation(
                    sector=name,
                    etf=etf,
                    performance_1w=round(perf_1w, 2) if perf_1w else None,
                    performance_1m=round(perf_1m, 2),
                    relative_strength=rel_str,
                ))
            except Exception:
                continue

        return sectors

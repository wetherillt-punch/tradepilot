"""
TradePilot Indicator Engine
Pure deterministic computation — no LLM, no guessing.
Every number the LLM sees is computed here.
"""

import pandas as pd
import numpy as np
from typing import Optional
from app.models.schemas import (
    TickerData, IndicatorSnapshot, MACDValues, BollingerValues,
    StochRSIValues, Direction, Timeframe
)


class IndicatorEngine:
    """
    Computes all technical indicators from OHLCV data.
    Returns a structured IndicatorSnapshot for the most recent bar,
    plus full series for charting.
    """

    def __init__(self, ticker_data: TickerData):
        self.ticker = ticker_data.ticker
        self.timeframe = ticker_data.timeframe
        self.df = self._to_dataframe(ticker_data)
        self._compute_all()

    def _to_dataframe(self, td: TickerData) -> pd.DataFrame:
        df = pd.DataFrame([b.model_dump() for b in td.bars])
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    # ─── Master Computation ───────────────────────────────────────────────

    def _compute_all(self):
        """Run all indicator computations."""
        df = self.df

        # EMAs
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

        # RSI
        df["rsi_14"] = self._compute_rsi(df["close"], 14)

        # MACD
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd_line"] = ema_12 - ema_26
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd_line"] - df["macd_signal"]

        # VWAP (intraday only — for daily, use rolling anchored VWAP)
        df["vwap"] = self._compute_vwap(df)

        # Volume & Relative Volume
        df["vol_sma_20"] = df["volume"].rolling(20).mean()
        df["rvol"] = np.where(
            df["vol_sma_20"] > 0,
            df["volume"] / df["vol_sma_20"],
            1.0
        )

        # ATR
        df["atr_14"] = self._compute_atr(df, 14)
        df["atr_percent"] = np.where(
            df["close"] > 0,
            (df["atr_14"] / df["close"]) * 100,
            0
        )

        # Bollinger Bands
        df["bb_middle"] = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_middle"] + (bb_std * 2)
        df["bb_lower"] = df["bb_middle"] - (bb_std * 2)
        df["bb_bandwidth"] = np.where(
            df["bb_middle"] > 0,
            ((df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]) * 100,
            0
        )
        # Squeeze: bandwidth at 20-period low
        df["bb_squeeze"] = df["bb_bandwidth"] <= df["bb_bandwidth"].rolling(20).min()

        # ADX
        df["adx_14"] = self._compute_adx(df, 14)

        # OBV
        df["obv"] = self._compute_obv(df)
        df["obv_ema_20"] = df["obv"].ewm(span=20, adjust=False).mean()

        # Stochastic RSI
        df["stoch_rsi_k"], df["stoch_rsi_d"] = self._compute_stoch_rsi(df["close"], 14, 14, 3, 3)

        # RSI Divergence Detection
        df["rsi_divergence"] = self._detect_rsi_divergence(df)

        self.df = df

    # ─── Get Snapshot ─────────────────────────────────────────────────────

    def get_snapshot(self) -> IndicatorSnapshot:
        """Return the most recent indicator values as a structured snapshot."""
        df = self.df
        latest = df.iloc[-1]

        # EMA stack direction
        ema_stack = self._classify_ema_stack(latest)

        # ADX trend classification
        adx_val = latest.get("adx_14")
        adx_trend = None
        if pd.notna(adx_val):
            if adx_val >= 40:
                adx_trend = "strong"
            elif adx_val >= 25:
                adx_trend = "moderate"
            elif adx_val >= 15:
                adx_trend = "weak"
            else:
                adx_trend = "no_trend"

        # OBV trend
        obv_trend = None
        if pd.notna(latest.get("obv")) and pd.notna(latest.get("obv_ema_20")):
            obv_trend = Direction.BULLISH if latest["obv"] > latest["obv_ema_20"] else Direction.BEARISH

        # Price vs VWAP
        price_vs_vwap = None
        if pd.notna(latest.get("vwap")) and latest["vwap"] > 0:
            diff_pct = abs(latest["close"] - latest["vwap"]) / latest["vwap"] * 100
            if diff_pct < 0.1:
                price_vs_vwap = "at"
            elif latest["close"] > latest["vwap"]:
                price_vs_vwap = "above"
            else:
                price_vs_vwap = "below"

        # Pattern detection
        patterns = self._detect_patterns(df)

        return IndicatorSnapshot(
            ticker=self.ticker,
            timestamp=latest["timestamp"],
            timeframe=self.timeframe,
            price=round(latest["close"], 2),
            ema_9=self._safe_round(latest.get("ema_9")),
            ema_20=self._safe_round(latest.get("ema_20")),
            ema_50=self._safe_round(latest.get("ema_50")),
            ema_200=self._safe_round(latest.get("ema_200")),
            ema_stack=ema_stack,
            rsi_14=self._safe_round(latest.get("rsi_14"), 1),
            rsi_divergence=latest.get("rsi_divergence"),
            macd=MACDValues(
                line=self._safe_round(latest.get("macd_line"), 3) or 0,
                signal=self._safe_round(latest.get("macd_signal"), 3) or 0,
                histogram=self._safe_round(latest.get("macd_histogram"), 3) or 0,
            ) if pd.notna(latest.get("macd_line")) else None,
            stoch_rsi=StochRSIValues(
                k=self._safe_round(latest.get("stoch_rsi_k"), 1) or 0,
                d=self._safe_round(latest.get("stoch_rsi_d"), 1) or 0,
            ) if pd.notna(latest.get("stoch_rsi_k")) else None,
            volume=latest.get("volume"),
            rvol=self._safe_round(latest.get("rvol"), 2),
            obv_trend=obv_trend,
            vwap=self._safe_round(latest.get("vwap")),
            price_vs_vwap=price_vs_vwap,
            atr_14=self._safe_round(latest.get("atr_14")),
            atr_percent=self._safe_round(latest.get("atr_percent"), 2),
            bollinger=BollingerValues(
                upper=self._safe_round(latest.get("bb_upper")) or 0,
                middle=self._safe_round(latest.get("bb_middle")) or 0,
                lower=self._safe_round(latest.get("bb_lower")) or 0,
                bandwidth=self._safe_round(latest.get("bb_bandwidth"), 2) or 0,
                squeeze=bool(latest.get("bb_squeeze", False)),
            ) if pd.notna(latest.get("bb_middle")) else None,
            adx_14=self._safe_round(latest.get("adx_14"), 1),
            adx_trend=adx_trend,
            patterns=patterns,
        )

    def get_series(self) -> pd.DataFrame:
        """Return the full computed DataFrame for charting."""
        return self.df.copy()

    # ─── Indicator Computations ───────────────────────────────────────────

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _compute_vwap(df: pd.DataFrame) -> pd.Series:
        """
        Compute VWAP. For daily data, use rolling 20-day anchored VWAP.
        For intraday, this would reset daily.
        """
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        cum_tp_vol = (typical_price * df["volume"]).rolling(20).sum()
        cum_vol = df["volume"].rolling(20).sum()
        return np.where(cum_vol > 0, cum_tp_vol / cum_vol, typical_price)

    @staticmethod
    def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()

        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

        atr = IndicatorEngine._compute_atr(df, period)

        plus_di = 100 * pd.Series(plus_dm).ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).ewm(span=period, adjust=False).mean() / atr

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(span=period, adjust=False).mean()
        return adx

    @staticmethod
    def _compute_obv(df: pd.DataFrame) -> pd.Series:
        obv = [0]
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i - 1]:
                obv.append(obv[-1] + df["volume"].iloc[i])
            elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
                obv.append(obv[-1] - df["volume"].iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=df.index)

    @staticmethod
    def _compute_stoch_rsi(
        close: pd.Series,
        rsi_period: int = 14,
        stoch_period: int = 14,
        k_smooth: int = 3,
        d_smooth: int = 3
    ) -> tuple[pd.Series, pd.Series]:
        rsi = IndicatorEngine._compute_rsi(close, rsi_period)
        rsi_min = rsi.rolling(stoch_period).min()
        rsi_max = rsi.rolling(stoch_period).max()
        stoch_rsi = np.where(
            (rsi_max - rsi_min) > 0,
            (rsi - rsi_min) / (rsi_max - rsi_min) * 100,
            50  # neutral when no range
        )
        k = pd.Series(stoch_rsi, index=close.index).rolling(k_smooth).mean()
        d = k.rolling(d_smooth).mean()
        return k, d

    # ─── Pattern Detection ────────────────────────────────────────────────

    def _detect_patterns(self, df: pd.DataFrame) -> list[str]:
        """Detect technical patterns from the data."""
        patterns = []
        if len(df) < 20:
            return patterns

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # EMA Stack Bullish/Bearish
        if self._all_notna(latest, ["ema_9", "ema_20", "ema_50", "ema_200"]):
            if latest["ema_9"] > latest["ema_20"] > latest["ema_50"] > latest["ema_200"]:
                patterns.append("ema_stack_bullish")
            elif latest["ema_9"] < latest["ema_20"] < latest["ema_50"] < latest["ema_200"]:
                patterns.append("ema_stack_bearish")

        # Golden Cross / Death Cross (50/200)
        if self._all_notna(latest, ["ema_50", "ema_200"]) and self._all_notna(prev, ["ema_50", "ema_200"]):
            if prev["ema_50"] <= prev["ema_200"] and latest["ema_50"] > latest["ema_200"]:
                patterns.append("golden_cross")
            elif prev["ema_50"] >= prev["ema_200"] and latest["ema_50"] < latest["ema_200"]:
                patterns.append("death_cross")

        # MACD Crossover
        if self._all_notna(latest, ["macd_line", "macd_signal"]) and self._all_notna(prev, ["macd_line", "macd_signal"]):
            if prev["macd_line"] <= prev["macd_signal"] and latest["macd_line"] > latest["macd_signal"]:
                patterns.append("macd_bullish_crossover")
            elif prev["macd_line"] >= prev["macd_signal"] and latest["macd_line"] < latest["macd_signal"]:
                patterns.append("macd_bearish_crossover")

        # RSI Extremes
        if pd.notna(latest.get("rsi_14")):
            if latest["rsi_14"] > 70:
                patterns.append("rsi_overbought")
            elif latest["rsi_14"] < 30:
                patterns.append("rsi_oversold")

        # Bollinger Squeeze
        if latest.get("bb_squeeze"):
            patterns.append("bollinger_squeeze")

        # Volume Breakout (RVOL > 2.0)
        if pd.notna(latest.get("rvol")) and latest["rvol"] >= 2.0:
            patterns.append("volume_breakout")

        # High RVOL (1.5-2.0)
        elif pd.notna(latest.get("rvol")) and latest["rvol"] >= 1.5:
            patterns.append("elevated_volume")

        # VWAP Reclaim / Rejection
        if pd.notna(latest.get("vwap")) and pd.notna(prev.get("vwap")):
            if prev["close"] < prev["vwap"] and latest["close"] > latest["vwap"]:
                patterns.append("vwap_reclaim")
            elif prev["close"] > prev["vwap"] and latest["close"] < latest["vwap"]:
                patterns.append("vwap_rejection")

        # Strong Trend (ADX > 25 + directional)
        if pd.notna(latest.get("adx_14")) and latest["adx_14"] > 25:
            if pd.notna(latest.get("ema_9")) and pd.notna(latest.get("ema_20")):
                if latest["ema_9"] > latest["ema_20"]:
                    patterns.append("strong_uptrend")
                elif latest["ema_9"] < latest["ema_20"]:
                    patterns.append("strong_downtrend")

        # RSI Divergence
        if latest.get("rsi_divergence") and latest["rsi_divergence"] != "none":
            patterns.append(latest["rsi_divergence"])

        return patterns

    def _detect_rsi_divergence(self, df: pd.DataFrame) -> pd.Series:
        """
        Detect bullish/bearish RSI divergence.
        Bullish: price makes lower low but RSI makes higher low
        Bearish: price makes higher high but RSI makes lower high
        """
        result = pd.Series("none", index=df.index)
        lookback = 14

        if len(df) < lookback + 5:
            return result

        for i in range(lookback + 4, len(df)):
            window = df.iloc[i - lookback:i + 1]

            # Bullish divergence
            price_low_curr = window["low"].iloc[-5:].min()
            price_low_prev = window["low"].iloc[:lookback - 4].min()
            rsi_low_curr = window["rsi_14"].iloc[-5:].min() if pd.notna(window["rsi_14"].iloc[-1]) else None
            rsi_low_prev = window["rsi_14"].iloc[:lookback - 4].min() if pd.notna(window["rsi_14"].iloc[0]) else None

            if rsi_low_curr is not None and rsi_low_prev is not None:
                if price_low_curr < price_low_prev and rsi_low_curr > rsi_low_prev:
                    result.iloc[i] = "bullish_divergence"

            # Bearish divergence
            price_high_curr = window["high"].iloc[-5:].max()
            price_high_prev = window["high"].iloc[:lookback - 4].max()
            rsi_high_curr = window["rsi_14"].iloc[-5:].max() if pd.notna(window["rsi_14"].iloc[-1]) else None
            rsi_high_prev = window["rsi_14"].iloc[:lookback - 4].max() if pd.notna(window["rsi_14"].iloc[0]) else None

            if rsi_high_curr is not None and rsi_high_prev is not None:
                if price_high_curr > price_high_prev and rsi_high_curr < rsi_high_prev:
                    result.iloc[i] = "bearish_divergence"

        return result

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _classify_ema_stack(row) -> Optional[Direction]:
        vals = [row.get("ema_9"), row.get("ema_20"), row.get("ema_50"), row.get("ema_200")]
        if any(pd.isna(v) for v in vals):
            return None
        if vals[0] > vals[1] > vals[2] > vals[3]:
            return Direction.BULLISH
        elif vals[0] < vals[1] < vals[2] < vals[3]:
            return Direction.BEARISH
        return Direction.NEUTRAL

    @staticmethod
    def _safe_round(val, decimals: int = 2) -> Optional[float]:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return round(float(val), decimals)

    @staticmethod
    def _all_notna(row, cols: list[str]) -> bool:
        return all(pd.notna(row.get(c)) for c in cols)

"""
TradePilot CSV Parsers
Normalize ThinkorSwim and TradingView exports into unified TickerData format.
"""

import pandas as pd
import numpy as np
from io import StringIO, BytesIO
from datetime import datetime
from typing import Optional
from app.models.schemas import OHLCVBar, TickerData, Timeframe


# ─── ThinkorSwim Parser ──────────────────────────────────────────────────────

def parse_thinkorswim(
    file_content: bytes | str,
    ticker: str,
    timeframe: Timeframe = Timeframe.DAILY
) -> TickerData:
    """
    Parse ThinkorSwim chart data export.
    
    TOS export format varies but typically:
    - Tab or comma separated
    - Columns: Date, Open, High, Low, Close, Volume
    - Date format: MM/DD/YYYY or YYYY-MM-DD
    - May have header rows with metadata before the actual data
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8")

    # TOS sometimes has metadata lines at the top — skip until we find headers
    lines = file_content.strip().split("\n")
    header_idx = _find_header_row(lines)

    if header_idx is None:
        raise ValueError(
            "Could not detect OHLCV headers in ThinkorSwim export. "
            "Expected columns containing: Date/Time, Open, High, Low, Close, Volume"
        )

    # Parse from the header row onward
    data_str = "\n".join(lines[header_idx:])

    # Detect delimiter
    delimiter = "\t" if "\t" in lines[header_idx] else ","
    df = pd.read_csv(StringIO(data_str), delimiter=delimiter)

    # Normalize column names
    df.columns = _normalize_columns(df.columns)

    # Parse timestamps
    df["timestamp"] = pd.to_datetime(df["date"], format="mixed", dayfirst=False)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Clean numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

    # Fill missing volume with 0
    if "volume" not in df.columns:
        df["volume"] = 0
    df["volume"] = df["volume"].fillna(0)

    # Drop rows with NaN in OHLC
    df = df.dropna(subset=["open", "high", "low", "close"])

    bars = [
        OHLCVBar(
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"]
        )
        for _, row in df.iterrows()
    ]

    return TickerData(
        ticker=ticker.upper(),
        timeframe=timeframe,
        bars=bars,
        source="thinkorswim"
    )


# ─── TradingView Parser ──────────────────────────────────────────────────────

def parse_tradingview(
    file_content: bytes | str,
    ticker: str,
    timeframe: Timeframe = Timeframe.DAILY
) -> TickerData:
    """
    Parse TradingView chart data export.
    
    TV export format:
    - Comma separated
    - Columns: time, open, high, low, close, Volume (or volume)
    - Time is Unix timestamp or ISO date string
    - Clean, consistent format
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8")

    df = pd.read_csv(StringIO(file_content))

    # Normalize column names
    df.columns = _normalize_columns(df.columns)

    # TradingView uses 'time' instead of 'date' sometimes
    time_col = "time" if "time" in df.columns else "date"

    # Handle unix timestamps vs string dates
    sample = str(df[time_col].iloc[0])
    if sample.isdigit() and len(sample) >= 10:
        # Unix timestamp
        df["timestamp"] = pd.to_datetime(df[time_col], unit="s")
    else:
        df["timestamp"] = pd.to_datetime(df[time_col], format="mixed")

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Clean numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" not in df.columns:
        df["volume"] = 0
    df["volume"] = df["volume"].fillna(0)

    df = df.dropna(subset=["open", "high", "low", "close"])

    bars = [
        OHLCVBar(
            timestamp=row["timestamp"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"]
        )
        for _, row in df.iterrows()
    ]

    return TickerData(
        ticker=ticker.upper(),
        timeframe=timeframe,
        bars=bars,
        source="tradingview"
    )


# ─── Auto-Detect Parser ──────────────────────────────────────────────────────

def parse_csv_auto(
    file_content: bytes | str,
    ticker: str,
    timeframe: Timeframe = Timeframe.DAILY,
    source: Optional[str] = None
) -> TickerData:
    """
    Auto-detect source format and parse accordingly.
    If source is specified, use that parser directly.
    """
    if source == "thinkorswim":
        return parse_thinkorswim(file_content, ticker, timeframe)
    elif source == "tradingview":
        return parse_tradingview(file_content, ticker, timeframe)

    # Auto-detect
    if isinstance(file_content, bytes):
        content_str = file_content.decode("utf-8")
    else:
        content_str = file_content

    # TOS files often have tab-delimited data or metadata rows
    if "\t" in content_str.split("\n")[0]:
        return parse_thinkorswim(file_content, ticker, timeframe)

    # Check for TradingView's typical 'time' column header
    first_line = content_str.split("\n")[0].lower()
    if "time" in first_line and "open" in first_line:
        return parse_tradingview(file_content, ticker, timeframe)

    # Default: try TOS first, fall back to TV
    try:
        return parse_thinkorswim(file_content, ticker, timeframe)
    except (ValueError, KeyError):
        return parse_tradingview(file_content, ticker, timeframe)


# ─── yfinance Fetcher ─────────────────────────────────────────────────────────

def fetch_yfinance(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d"
) -> TickerData:
    """
    Fetch OHLCV data from Yahoo Finance.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL")
        period: Data period - 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
        interval: Bar interval - 1m, 5m, 15m, 30m, 1h, 1d, 1wk
    """
    import yfinance as yf

    df = yf.download(ticker, period=period, interval=interval, progress=False, timeout=10)

    if df.empty:
        raise ValueError(f"No data returned from yfinance for {ticker}")

    # Handle multi-level columns from yf.download
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    # Map interval string to Timeframe enum
    interval_map = {
        "1m": Timeframe.M1, "5m": Timeframe.M5, "15m": Timeframe.M15,
        "30m": Timeframe.M30, "1h": Timeframe.H1, "1d": Timeframe.DAILY,
        "1wk": Timeframe.WEEKLY
    }
    tf = interval_map.get(interval, Timeframe.DAILY)

    bars = [
        OHLCVBar(
            timestamp=idx.to_pydatetime(),
            open=row["Open"],
            high=row["High"],
            low=row["Low"],
            close=row["Close"],
            volume=row["Volume"]
        )
        for idx, row in df.iterrows()
    ]

    return TickerData(
        ticker=ticker.upper(),
        timeframe=tf,
        bars=bars,
        source="yfinance"
    )


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _find_header_row(lines: list[str]) -> Optional[int]:
    """Find the row index that contains OHLCV headers."""
    target_cols = {"open", "high", "low", "close"}

    for i, line in enumerate(lines[:20]):  # check first 20 lines
        lower = line.lower()
        matches = sum(1 for col in target_cols if col in lower)
        if matches >= 3:  # at least 3 of 4 OHLC columns found
            return i
    return None


def _normalize_columns(columns: pd.Index) -> pd.Index:
    """Normalize column names to lowercase standard format."""
    mapping = {}
    for col in columns:
        lower = col.strip().lower().replace(" ", "_")

        if any(d in lower for d in ["date", "time", "datetime", "timestamp"]):
            if "date" in lower and "time" not in lower:
                mapping[col] = "date"
            elif "time" in lower and "date" not in lower:
                mapping[col] = "time"
            else:
                mapping[col] = "date"
        elif lower in ["open", "o"]:
            mapping[col] = "open"
        elif lower in ["high", "h"]:
            mapping[col] = "high"
        elif lower in ["low", "l"]:
            mapping[col] = "low"
        elif lower in ["close", "c", "last", "adj_close", "adj close"]:
            mapping[col] = "close"
        elif lower in ["volume", "vol", "v"]:
            mapping[col] = "volume"
        else:
            mapping[col] = lower

    return pd.Index([mapping.get(c, c.strip().lower()) for c in columns])

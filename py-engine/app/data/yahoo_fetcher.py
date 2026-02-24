"""
TradePilot Yahoo Finance Data Fetcher
Direct HTTP requests to Yahoo Finance API — bypasses yfinance entirely.
Uses curl_cffi for Chrome impersonation to avoid cloud IP blocking.
"""

import pandas as pd
import time


def _get_session():
    """Create a session that impersonates Chrome."""
    try:
        from curl_cffi import requests as curl_requests
        return curl_requests.Session(impersonate="chrome")
    except ImportError:
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        return session


def _period_to_timestamps(period: str) -> tuple[int, int]:
    """Convert period string to Unix timestamps."""
    now = int(time.time())
    period_map = {
        "1d": 86400, "5d": 5 * 86400, "1mo": 30 * 86400,
        "3mo": 90 * 86400, "6mo": 180 * 86400, "1y": 365 * 86400,
        "2y": 730 * 86400, "5y": 1825 * 86400, "max": 50 * 365 * 86400,
    }
    seconds = period_map.get(period, 365 * 86400)
    return now - seconds, now


def fetch_ticker_data(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data from Yahoo Finance via direct API call.
    Returns DataFrame with lowercase columns: open, high, low, close, volume.
    Returns empty DataFrame on failure (never raises).
    """
    session = _get_session()
    period1, period2 = _period_to_timestamps(period)

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={period1}&period2={period2}&interval={interval}"
        f"&includePrePost=false&events=div%2Csplit"
    )

    try:
        response = session.get(url, timeout=15)

        if response.status_code != 200:
            print(f"[YF] {ticker}: HTTP {response.status_code}")
            return pd.DataFrame()

        data = response.json()
        chart = data.get("chart", {})
        result = chart.get("result")

        if not result or len(result) == 0:
            error = chart.get("error", {})
            print(f"[YF] {ticker}: {error.get('description', 'No data')}")
            return pd.DataFrame()

        result = result[0]
        timestamps = result.get("timestamp")

        if not timestamps:
            print(f"[YF] {ticker}: No timestamps")
            return pd.DataFrame()

        quote = result.get("indicators", {}).get("quote", [{}])[0]

        df = pd.DataFrame({
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", []),
        }, index=pd.to_datetime(timestamps, unit="s", utc=True))

        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
        df.index.name = "date"
        df = df.dropna(subset=["open", "high", "low", "close"])

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = df["volume"].fillna(0)

        print(f"[YF] {ticker}: OK - {len(df)} bars")
        return df

    except Exception as e:
        print(f"[YF] {ticker}: Exception - {e}")
        return pd.DataFrame()

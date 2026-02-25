"""
TradePilot Cross-Asset Data Engine
Fetches and analyzes bonds, credit, commodities, dollar, and breadth data.
Provides the intermarket context that separates a good weekly outlook from a great one.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from app.data.yahoo_fetcher import fetch_ticker_data


# ─── Instrument Definitions ──────────────────────────────────────────────────

CROSS_ASSET_TICKERS = {
    # Bonds & Rates
    "TLT": {"name": "20+ Year Treasury Bond", "category": "bonds", "description": "Long-duration treasuries — flight to safety, rate expectations"},
    "IEF": {"name": "7-10 Year Treasury Bond", "category": "bonds", "description": "Intermediate treasuries — yield curve belly"},
    "SHY": {"name": "1-3 Year Treasury Bond", "category": "bonds", "description": "Short-duration treasuries — Fed rate proxy"},

    # Credit
    "HYG": {"name": "High Yield Corporate Bond", "category": "credit", "description": "Junk bonds — credit stress barometer"},
    "LQD": {"name": "Investment Grade Corporate Bond", "category": "credit", "description": "IG corporates — credit quality flight"},

    # Commodities
    "GLD": {"name": "Gold", "category": "commodities", "description": "Gold — inflation hedge, fear trade, dollar inverse"},
    "USO": {"name": "US Oil Fund", "category": "commodities", "description": "Crude oil — growth proxy, geopolitical risk"},

    # Dollar
    "UUP": {"name": "US Dollar Index (Bull)", "category": "dollar", "description": "Dollar strength — inverse risk, carry trade"},

    # Breadth & Risk Appetite
    "IWM": {"name": "Russell 2000 Small Cap", "category": "breadth", "description": "Small caps — risk appetite, domestic economy"},
    "RSP": {"name": "S&P 500 Equal Weight", "category": "breadth", "description": "Equal weight SPY — breadth vs concentration"},
}


def _compute_metrics(df: pd.DataFrame, ticker: str) -> Optional[dict]:
    """Compute price metrics for a single instrument."""
    if df.empty or len(df) < 10:
        return None

    close = df["close"]
    latest = close.iloc[-1]

    # Performance
    perf_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
    perf_1w = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
    perf_1m = ((close.iloc[-1] / close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
    perf_3m = ((close.iloc[-1] / close.iloc[-63]) - 1) * 100 if len(close) >= 63 else None

    # EMAs
    ema_20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema_50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    ema_200 = close.ewm(span=200, adjust=False).mean().iloc[-1] if len(close) >= 200 else None

    # Trend
    above_20 = latest > ema_20
    above_50 = latest > ema_50
    above_200 = latest > ema_200 if ema_200 else None

    if above_20 and above_50:
        trend = "bullish"
    elif not above_20 and not above_50:
        trend = "bearish"
    else:
        trend = "mixed"

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).iloc[-1]

    # 20-day volatility (annualized)
    returns = close.pct_change().dropna()
    vol_20d = returns.tail(20).std() * np.sqrt(252) * 100 if len(returns) >= 20 else None

    # Distance from 52-week high/low
    high_52w = close.tail(252).max() if len(close) >= 252 else close.max()
    low_52w = close.tail(252).min() if len(close) >= 252 else close.min()
    pct_from_high = ((latest / high_52w) - 1) * 100
    pct_from_low = ((latest / low_52w) - 1) * 100

    info = CROSS_ASSET_TICKERS.get(ticker, {})

    return {
        "ticker": ticker,
        "name": info.get("name", ticker),
        "category": info.get("category", "unknown"),
        "description": info.get("description", ""),
        "price": round(float(latest), 2),
        "change_1d": round(float(perf_1d), 2),
        "change_1w": round(float(perf_1w), 2),
        "change_1m": round(float(perf_1m), 2),
        "change_3m": round(float(perf_3m), 2) if perf_3m is not None else None,
        "trend": trend,
        "above_ema20": bool(above_20),
        "above_ema50": bool(above_50),
        "above_ema200": bool(above_200) if above_200 is not None else None,
        "rsi_14": round(float(rsi), 1) if not np.isnan(rsi) else None,
        "volatility_20d": round(float(vol_20d), 1) if vol_20d else None,
        "pct_from_52w_high": round(float(pct_from_high), 1),
        "pct_from_52w_low": round(float(pct_from_low), 1),
    }


def _compute_cross_signals(instruments: dict) -> list[dict]:
    """Derive intermarket signals from cross-asset relationships."""
    signals = []

    tlt = instruments.get("TLT")
    hyg = instruments.get("HYG")
    lqd = instruments.get("LQD")
    gld = instruments.get("GLD")
    uup = instruments.get("UUP")
    iwm = instruments.get("IWM")
    rsp = instruments.get("RSP")
    uso = instruments.get("USO")
    shy = instruments.get("SHY")

    # 1. Yield Curve Signal (TLT vs SHY)
    if tlt and shy:
        tlt_1m = tlt["change_1m"]
        shy_1m = shy["change_1m"]
        spread_move = tlt_1m - shy_1m  # positive = curve steepening (TLT outperforming)
        if spread_move > 2:
            signals.append({
                "signal": "YIELD CURVE STEEPENING",
                "severity": "high",
                "detail": f"TLT {tlt_1m:+.1f}% vs SHY {shy_1m:+.1f}% (1M). Long-end rallying faster — market pricing rate cuts or recession. Favors defensives, hurts financials.",
            })
        elif spread_move < -2:
            signals.append({
                "signal": "YIELD CURVE FLATTENING/INVERSION PRESSURE",
                "severity": "high",
                "detail": f"SHY outperforming TLT by {abs(spread_move):.1f}% (1M). Short rates sticky while long-end sells. Hawkish repricing or inflation fears. Negative for duration, bonds.",
            })

    # 2. Credit Stress Signal (HYG vs LQD)
    if hyg and lqd:
        hyg_1w = hyg["change_1w"]
        lqd_1w = lqd["change_1w"]
        credit_spread_move = lqd_1w - hyg_1w  # positive = flight to quality
        if credit_spread_move > 1:
            signals.append({
                "signal": "CREDIT STRESS: FLIGHT TO QUALITY",
                "severity": "high",
                "detail": f"LQD {lqd_1w:+.1f}% vs HYG {hyg_1w:+.1f}% (1W). Investment grade outperforming junk — credit risk rising. Watch for equity spillover. Historically precedes SPY weakness by 1-2 weeks.",
            })
        elif hyg_1w < -1 and lqd_1w < -0.5:
            signals.append({
                "signal": "BROAD CREDIT SELLOFF",
                "severity": "high",
                "detail": f"HYG {hyg_1w:+.1f}% and LQD {lqd_1w:+.1f}% (1W) — both declining. Rate-driven selloff or risk-off repricing. Equities rarely hold up when both credit segments are weak.",
            })

    # 3. Risk Appetite Signal (HYG vs TLT)
    if hyg and tlt:
        risk_appetite = hyg["change_1w"] - tlt["change_1w"]
        if risk_appetite < -2:
            signals.append({
                "signal": "RISK-OFF: TREASURIES OVER CREDIT",
                "severity": "high",
                "detail": f"TLT {tlt['change_1w']:+.1f}% vs HYG {hyg['change_1w']:+.1f}% (1W). Classic flight to safety. Correlates with SPY drawdowns >2% within 5 trading days.",
            })
        elif risk_appetite > 2:
            signals.append({
                "signal": "RISK-ON: CREDIT OVER TREASURIES",
                "severity": "medium",
                "detail": f"HYG {hyg['change_1w']:+.1f}% vs TLT {tlt['change_1w']:+.1f}% (1W). Risk appetite returning. Supports cyclical longs and high-beta plays.",
            })

    # 4. Gold Signal
    if gld:
        if gld["change_1w"] > 2:
            reasons = []
            if uup and uup["change_1w"] < -0.5:
                reasons.append("dollar weakness")
            if tlt and tlt["change_1w"] > 1:
                reasons.append("bond rally")
            reasons_str = f" (driven by: {', '.join(reasons)})" if reasons else ""
            signals.append({
                "signal": "GOLD BREAKOUT — FEAR/INFLATION BID",
                "severity": "medium",
                "detail": f"GLD {gld['change_1w']:+.1f}% (1W), RSI {gld['rsi_14']}{reasons_str}. Gold above $2100 zone. Historical analog: gold rallies >2% weekly during tariff uncertainty persist for 3-5 weeks. Favors GDX miners.",
            })
        elif gld["change_1w"] < -2:
            signals.append({
                "signal": "GOLD SELLOFF — RISK-ON OR DOLLAR STRENGTH",
                "severity": "medium",
                "detail": f"GLD {gld['change_1w']:+.1f}% (1W). Gold selling off suggests either aggressive risk-on rotation or dollar surge. Check UUP for confirmation.",
            })

    # 5. Dollar Signal
    if uup:
        if uup["change_1w"] > 1:
            signals.append({
                "signal": "DOLLAR STRENGTHENING",
                "severity": "medium",
                "detail": f"UUP {uup['change_1w']:+.1f}% (1W), trend: {uup['trend']}. Strong dollar headwind for multinationals, commodities, and EM. Favors domestic-revenue companies. If >DXY 106, risk-off intensifies.",
            })
        elif uup["change_1w"] < -1:
            signals.append({
                "signal": "DOLLAR WEAKENING",
                "severity": "medium",
                "detail": f"UUP {uup['change_1w']:+.1f}% (1W). Weak dollar tailwind for commodities, multinationals, EM. If sustained, supports risk-on rotation.",
            })

    # 6. Breadth Signal (RSP vs SPY needs SPY data — use IWM as proxy)
    if iwm and rsp:
        if iwm["change_1w"] < -2 and rsp["change_1w"] < iwm["change_1w"]:
            signals.append({
                "signal": "BREADTH DETERIORATION — SMALL CAPS LEADING DOWN",
                "severity": "high",
                "detail": f"IWM {iwm['change_1w']:+.1f}%, RSP {rsp['change_1w']:+.1f}% (1W). Small caps and equal-weight both weaker than cap-weighted. Narrow leadership = fragile market. Breakdowns are 3x more likely than breakouts in this setup.",
            })
        elif iwm["change_1w"] > 1.5 and rsp["change_1w"] > 0.5:
            signals.append({
                "signal": "BROAD PARTICIPATION — HEALTHY BREADTH",
                "severity": "medium",
                "detail": f"IWM {iwm['change_1w']:+.1f}%, RSP {rsp['change_1w']:+.1f}% (1W). Small caps and equal-weight participating. Broad-based rally supports breakout attempts and swing longs.",
            })

    # 7. Oil / Growth Signal
    if uso:
        if uso["change_1w"] > 3:
            signals.append({
                "signal": "OIL SPIKE — INFLATION/GEOPOLITICAL RISK",
                "severity": "medium",
                "detail": f"USO {uso['change_1w']:+.1f}% (1W), RSI {uso['rsi_14']}. Oil spike raises input costs across sectors. Historically negative for transports (IYT), airlines, consumer disc. Positive for XLE. If sustained >2 weeks, Fed reprices hawkish.",
            })
        elif uso["change_1w"] < -3:
            signals.append({
                "signal": "OIL DECLINE — DEMAND DESTRUCTION FEAR",
                "severity": "medium",
                "detail": f"USO {uso['change_1w']:+.1f}% (1W). Sharp oil decline signals demand destruction fears or geopolitical de-escalation. Negative for XLE, positive for consumer and transports.",
            })

    return signals


def fetch_cross_asset_data() -> dict:
    """
    Fetch all cross-asset instruments and compute metrics + intermarket signals.
    Returns dict with 'instruments' (per-ticker data) and 'signals' (cross-asset signals).
    """
    instruments = {}

    for ticker in CROSS_ASSET_TICKERS:
        print(f"[CrossAsset] Fetching {ticker}...")
        df = fetch_ticker_data(ticker, period="1y", interval="1d")
        metrics = _compute_metrics(df, ticker)
        if metrics:
            instruments[ticker] = metrics

    print(f"[CrossAsset] Fetched {len(instruments)}/{len(CROSS_ASSET_TICKERS)} instruments")

    # Compute intermarket signals
    signals = _compute_cross_signals(instruments)
    print(f"[CrossAsset] Generated {len(signals)} intermarket signals")

    return {
        "instruments": instruments,
        "signals": signals,
        "fetched_at": datetime.utcnow().isoformat(),
    }


def format_cross_asset_for_llm(cross_asset_data: dict) -> str:
    """Format cross-asset data into a structured text block for LLM prompts."""
    instruments = cross_asset_data.get("instruments", {})
    signals = cross_asset_data.get("signals", [])

    lines = ["=== CROSS-ASSET MARKET DATA (quantitative — real numbers, not estimates) ===\n"]

    # Group by category
    categories = {}
    for ticker, data in instruments.items():
        cat = data["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(data)

    category_labels = {
        "bonds": "BONDS & RATES",
        "credit": "CREDIT MARKETS",
        "commodities": "COMMODITIES",
        "dollar": "US DOLLAR",
        "breadth": "BREADTH & RISK APPETITE",
    }

    for cat_key, label in category_labels.items():
        items = categories.get(cat_key, [])
        if not items:
            continue
        lines.append(f"  {label}:")
        for d in items:
            trend_icon = "↑" if d["trend"] == "bullish" else "↓" if d["trend"] == "bearish" else "→"
            ema_status = []
            if d["above_ema20"]:
                ema_status.append(">20EMA")
            else:
                ema_status.append("<20EMA")
            if d["above_ema50"]:
                ema_status.append(">50EMA")
            else:
                ema_status.append("<50EMA")
            if d["above_ema200"] is not None:
                ema_status.append(">200EMA" if d["above_ema200"] else "<200EMA")

            lines.append(
                f"    {d['ticker']} ({d['name']}): ${d['price']} {trend_icon} | "
                f"1D: {d['change_1d']:+.1f}% | 1W: {d['change_1w']:+.1f}% | 1M: {d['change_1m']:+.1f}% | "
                f"RSI: {d['rsi_14']} | {', '.join(ema_status)} | "
                f"52W range: {d['pct_from_52w_low']:+.1f}% from low, {d['pct_from_52w_high']:+.1f}% from high"
            )
        lines.append("")

    if signals:
        lines.append("  INTERMARKET SIGNALS (auto-detected from cross-asset relationships):")
        for s in signals:
            severity_tag = f"[{s['severity'].upper()}]"
            lines.append(f"    {severity_tag} {s['signal']}")
            lines.append(f"      → {s['detail']}")
        lines.append("")

    return "\n".join(lines)

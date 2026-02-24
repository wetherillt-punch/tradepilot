"""
TradePilot API Server
FastAPI application that orchestrates the entire analysis pipeline.
"""

import os
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from app.database import db
from app.parsers.csv_parser import parse_csv_auto, fetch_yfinance
from app.indicators.engine import IndicatorEngine
from app.indicators.confidence import ConfidenceScorer
from app.regime.engine import RegimeEngine
from app.catalysts.engine import CatalystEngine
from app.options.strategy import OptionsStrategyEngine
from app.routes.llm_pipeline import LLMPipeline
from app.models.schemas import (
    Timeframe, TradeType, Direction, EventRisk
)


# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TradePilot Engine",
    description="Professional-grade trade plan generation engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    # allow_origins_OLD=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
regime_engine = RegimeEngine()
catalyst_engine = CatalystEngine()
options_engine = OptionsStrategyEngine()
confidence_scorer = ConfidenceScorer()
llm_pipeline = LLMPipeline(
    api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    model=os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250514"),
)


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


# ─── Request Models ───────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    ticker: str
    trade_type: str = "swing"  # "day_trade" or "swing"
    direction: str = "bullish"  # "bullish" or "bearish"
    timeframe: str = "1d"
    source: Optional[str] = None  # "thinkorswim", "tradingview", or auto-detect

class JournalRequest(BaseModel):
    trade_plan_id: Optional[str] = None
    ticker: str
    trade_type: str = "swing"
    direction: str = "bullish"
    actual_entry: float
    actual_exit: float
    position_size: Optional[float] = None
    pnl_dollar: Optional[float] = None
    pnl_percent: float
    followed_plan: bool = True
    notes: str = ""

class QuickAnalyzeRequest(BaseModel):
    ticker: str
    trade_type: str = "swing"
    direction: str = "bullish"


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


# ─── Session Initialization ──────────────────────────────────────────────────

@app.post("/api/session/init")
async def init_session(watchlist: list[str] = []):
    """
    Initialize session context — runs Stages 1 & 2.
    Call this once at the start of your trading day.
    Returns session_id for subsequent ticker analyses.
    """
    try:
        session_id = str(uuid.uuid4())[:8]

        # Run regime engine (fetches SPY, QQQ, VIX, sectors)
        regime = regime_engine.analyze()

        # Run catalyst engine (fetches earnings calendar)
        catalysts = catalyst_engine.analyze(watchlist)

        # Run LLM Stages 1 & 2
        session = llm_pipeline.run_session_stages(
            regime=regime,
            catalysts=catalysts,
            session_id=session_id,
        )

        # Cache session in MongoDB
        session_data = {
            "session_id": session_id,
            "regime": regime.model_dump(mode="json"),
            "catalysts": catalysts.model_dump(mode="json"),
            "stage1_output": session.stage1_output,
            "stage2_output": session.stage2_output,
        }
        await db.cache_session(session_data)

        return {
            "session_id": session_id,
            "regime": {
                "spy": regime.spy_regime.value,
                "qqq": regime.qqq_regime.value,
                "vix": regime.vix,
                "vix_percentile": regime.vix_percentile,
                "volatility": regime.volatility_regime,
                "bias": regime.bias.value,
                "sectors": {
                    "leaders": [{"sector": s.sector, "etf": s.etf, "perf": s.performance_1w} for s in regime.sector_leaders],
                    "laggards": [{"sector": s.sector, "etf": s.etf, "perf": s.performance_1w} for s in regime.sector_laggards],
                }
            },
            "catalysts": {
                "earnings_count": len(catalysts.earnings_this_week),
                "earnings": [{"ticker": e.ticker, "date": str(e.date), "bellwether": e.is_bellwether} for e in catalysts.earnings_this_week],
                "event_risk": catalysts.overall_event_risk.value,
            },
            "stage1_analysis": session.stage1_output,
            "stage2_analysis": session.stage2_output,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Analyze Ticker (with CSV upload) ────────────────────────────────────────

@app.post("/api/analyze/upload")
async def analyze_with_upload(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    trade_type: str = Form("swing"),
    direction: str = Form("bullish"),
    timeframe: str = Form("1d"),
    source: str = Form("auto"),
):
    """
    Analyze a ticker using uploaded CSV data.
    Requires active session (call /api/session/init first).
    """
    try:
        if not llm_pipeline.session_context:
            raise HTTPException(
                status_code=400,
                detail="No active session. Call /api/session/init first."
            )

        # Parse CSV
        content = await file.read()
        tf = Timeframe(timeframe)
        src = None if source == "auto" else source
        ticker_data = parse_csv_auto(content, ticker, tf, src)

        # Run indicator engine
        engine = IndicatorEngine(ticker_data)
        snapshot = engine.get_snapshot()

        # Determine trade parameters
        tt = TradeType(trade_type)
        dir_ = Direction(direction)

        # Get prior trades for this ticker/setup (feedback loop)
        prior = await db.get_journal_by_ticker(ticker)
        win_rate = await db.get_win_rate()

        # Compute confidence
        regime = llm_pipeline.session_context.regime
        catalysts = llm_pipeline.session_context.catalysts
        confidence = confidence_scorer.score(
            indicators=snapshot,
            direction=dir_,
            trade_type=tt,
            regime=regime,
            catalysts=catalysts,
            personal_win_rate=win_rate,
        )

        # Options strategy
        correlated = CatalystEngine.find_correlated_bellwethers(ticker.upper())
        options_rec = options_engine.recommend(
            trade_type=tt,
            direction=dir_,
            indicators=snapshot,
            confidence=confidence,
            catalyst_risk=catalysts.overall_event_risk,
        )

        # Run LLM Stages 3-5
        plan = llm_pipeline.analyze_ticker(
            indicators=snapshot,
            confidence=confidence,
            options_rec=options_rec,
            trade_type=tt,
            direction=dir_,
            prior_trades=prior[:5],
            correlated_bellwethers=correlated,
        )

        # Save to MongoDB
        plan_dict = plan.model_dump(mode="json")
plan_id = await db.save_trade_plan(plan_dict.copy())
plan_dict["id"] = str(plan_id)

        return {
            "plan": plan_dict,
            "indicators": snapshot.model_dump(mode="json"),
            "confidence": {
                "composite": confidence.composite,
                "rating": confidence.rating,
                "breakdown": {
                    "trend": confidence.trend_alignment,
                    "momentum": confidence.momentum_confirmation,
                    "volume": confidence.volume_confirmation,
                    "volatility": confidence.volatility_context,
                    "regime": confidence.regime_alignment,
                    "catalyst": confidence.catalyst_alignment,
                    "historical": confidence.historical_analog,
                    "personal": confidence.personal_edge,
                },
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Quick Analyze (auto-fetch data) ─────────────────────────────────────────

@app.post("/api/analyze/quick")
async def analyze_quick(req: QuickAnalyzeRequest):
    """
    Analyze a ticker by auto-fetching data from Yahoo Finance.
    No upload required. Good for quick scans.
    """
    try:
        if not llm_pipeline.session_context:
            raise HTTPException(
                status_code=400,
                detail="No active session. Call /api/session/init first."
            )

        # Fetch data from yfinance
        ticker_data = fetch_yfinance(req.ticker, period="6mo", interval="1d")

        # Run indicator engine
        engine = IndicatorEngine(ticker_data)
        snapshot = engine.get_snapshot()

        # Trade parameters
        tt = TradeType(req.trade_type)
        dir_ = Direction(req.direction)

        # Prior trades + win rate
        prior = await db.get_journal_by_ticker(req.ticker)
        win_rate = await db.get_win_rate()

        # Confidence
        regime = llm_pipeline.session_context.regime
        catalysts = llm_pipeline.session_context.catalysts
        confidence = confidence_scorer.score(
            indicators=snapshot, direction=dir_, trade_type=tt,
            regime=regime, catalysts=catalysts, personal_win_rate=win_rate,
        )

        # Options + correlations
        correlated = CatalystEngine.find_correlated_bellwethers(req.ticker.upper())
        options_rec = options_engine.recommend(
            trade_type=tt, direction=dir_, indicators=snapshot,
            confidence=confidence, catalyst_risk=catalysts.overall_event_risk,
        )

        # LLM Stages 3-5
        plan = llm_pipeline.analyze_ticker(
            indicators=snapshot, confidence=confidence, options_rec=options_rec,
            trade_type=tt, direction=dir_, prior_trades=prior[:5],
            correlated_bellwethers=correlated,
        )

        plan_dict = plan.model_dump(mode="json")
plan_id = await db.save_trade_plan(plan_dict.copy())
plan_dict["id"] = str(plan_id)

        return {
            "plan": plan_dict,
            "indicators": snapshot.model_dump(mode="json"),
            "confidence": {
                "composite": confidence.composite,
                "rating": confidence.rating,
                "breakdown": {
                    "trend": confidence.trend_alignment,
                    "momentum": confidence.momentum_confirmation,
                    "volume": confidence.volume_confirmation,
                    "volatility": confidence.volatility_context,
                    "regime": confidence.regime_alignment,
                    "catalyst": confidence.catalyst_alignment,
                    "historical": confidence.historical_analog,
                    "personal": confidence.personal_edge,
                },
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Trade Journal ────────────────────────────────────────────────────────────

@app.post("/api/journal/log")
async def log_trade(req: JournalRequest):
    """Log a completed trade to the journal. Triggers auto-debrief."""
    try:
        entry = req.model_dump()

        # Get the original trade plan if linked
        plan = None
        if req.trade_plan_id:
            plan = await db.get_trade_plan(req.trade_plan_id)
            if plan:
                entry["setup_type"] = plan.get("setup_type", "unknown")

        # Generate AI debrief
        if plan:
            from app.models.schemas import TradePlan
            plan_obj = TradePlan(**{k: v for k, v in plan.items() if k != "_id"})
            debrief = llm_pipeline.generate_debrief(plan_obj, entry)
            entry["ai_debrief"] = debrief

        # Save to MongoDB
        entry_id = await db.save_journal_entry(entry)

        return {
            "id": entry_id,
            "debrief": entry.get("ai_debrief", "No debrief generated"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/journal")
async def get_journal(limit: int = 50):
    """Get recent journal entries."""
    entries = await db.get_journal_entries(limit)
    return {"entries": entries}


# ─── Performance ──────────────────────────────────────────────────────────────

@app.get("/api/performance")
async def get_performance(days: int = 30):
    """Get performance statistics."""
    stats = await db.get_performance_stats(days)
    return stats


@app.post("/api/performance/weekly-digest")
async def weekly_digest():
    """Generate an LLM-powered weekly performance digest."""
    entries = await db.get_journal_entries(50)
    if not entries:
        return {"digest": "No trades to analyze."}

    digest = llm_pipeline.generate_weekly_digest(entries)
    return {"digest": digest}


# ─── Trade Plans History ──────────────────────────────────────────────────────

@app.get("/api/plans")
async def get_plans(limit: int = 20):
    """Get recent trade plans."""
    plans = await db.get_recent_plans(limit)
    return {"plans": plans}


@app.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get a specific trade plan."""
    plan = await db.get_trade_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


# ─── Chart Data ───────────────────────────────────────────────────────────────

@app.get("/api/chart/{ticker}")
async def get_chart_data(ticker: str, period: str = "6mo", interval: str = "1d"):
    """
    Return OHLCV data for lightweight-charts candlestick rendering.
    Returns array of {time, open, high, low, close, volume}.
    """
    from app.data.yahoo_fetcher import fetch_ticker_data
    try:
        df = fetch_ticker_data(ticker.upper(), period=period, interval=interval)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")

        candles = []
        volumes = []
        for dt, row in df.iterrows():
            time_str = dt.strftime("%Y-%m-%d")
            candles.append({
                "time": time_str,
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
            })
            volumes.append({
                "time": time_str,
                "value": int(row["volume"]),
                "color": "rgba(34,197,94,0.3)" if row["close"] >= row["open"] else "rgba(239,68,68,0.3)",
            })

        return {"candles": candles, "volumes": volumes, "ticker": ticker.upper()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Catalyst Data ────────────────────────────────────────────────────────────

# ─── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"|"assistant", "content": "..."}]

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Interactive chat with full session context.
    Requires active session. Loads recent trade plans and performance
    automatically so the LLM has full awareness.
    """
    try:
        if not llm_pipeline.session_context:
            raise HTTPException(
                status_code=400,
                detail="No active session. Call /api/session/init first."
            )

        # Load recent plans for context
        plans = await db.get_recent_plans(10)

        # Load performance stats for context
        perf = await db.get_performance_stats(30)

        # Run chat
        response = llm_pipeline.chat(
            messages=req.messages,
            trade_plans=plans,
            performance_stats=perf,
        )

        return {"response": response}

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Catalyst Data (continued) ───────────────────────────────────────────────

@app.get("/api/catalysts/bellwethers")
async def get_bellwethers():
    """Get bellwether ticker mapping."""
    from app.catalysts.engine import BELLWETHERS
    return BELLWETHERS


@app.get("/api/catalysts/macro-profiles")
async def get_macro_profiles():
    """Get historical macro event profiles."""
    from app.catalysts.engine import MACRO_EVENT_PROFILES
    # Convert EventRisk enums to strings for JSON
    profiles = {}
    for k, v in MACRO_EVENT_PROFILES.items():
        profile = dict(v)
        if "typical_impact" in profile:
            profile["typical_impact"] = profile["typical_impact"].value
        profiles[k] = profile
    return profiles


@app.get("/api/catalysts/geo-templates")
async def get_geo_templates():
    """Get geopolitical event historical templates."""
    from app.catalysts.engine import GEOPOLITICAL_TEMPLATES
    return GEOPOLITICAL_TEMPLATES

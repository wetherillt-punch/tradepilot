"""
TradePilot v2 Plans, Settings, and Watchlist API Routes.
Lifecycle-tracked plans with entry/exit logging and deviation detection.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import db


router = APIRouter(prefix="/api/v2", tags=["v2"])


# ─── Request Models ────────────────────────────────────────────────────────────

class CreatePlanRequest(BaseModel):
    session_id: str
    date: str  # YYYY-MM-DD
    ticker: str
    direction: str  # "call" | "put"
    source: str = "generated"  # "generated" | "manual"

    # Card fields
    confidence_score: Optional[float] = None
    confidence_grade: Optional[str] = None
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_price: Optional[float] = None
    stop_reason: Optional[str] = None
    targets: Optional[list] = None  # [{level, price, exit_pct}]
    strike: Optional[str] = None
    risk_reward: Optional[float] = None
    size_contracts: Optional[int] = None
    size_risk_dollars: Optional[float] = None
    kill_switch: Optional[str] = None

    # Timing
    timing_primary: Optional[str] = None
    timing_secondary: Optional[str] = None
    timing_dead_zones: Optional[list] = None
    timing_hard_cutoff: Optional[str] = None

    # Options
    expected_premium_low: Optional[float] = None
    expected_premium_high: Optional[float] = None
    expected_premium_max: Optional[float] = None

    # Deep dive
    thesis: Optional[str] = None
    regime_context: Optional[str] = None
    catalyst_risk: Optional[str] = None
    invalidation: Optional[list] = None
    cross_asset_note: Optional[str] = None
    options_detail: Optional[str] = None
    scaling_strategy: Optional[str] = None
    position_kill: Optional[list] = None
    discipline_note: Optional[str] = None

    # Checklists
    checklist_premarket: Optional[dict] = None
    checklist_intraday: Optional[dict] = None

    # Confidence breakdown
    confidence_breakdown: Optional[dict] = None


class LogEntryRequest(BaseModel):
    fill_price: float
    contracts: int
    time: Optional[str] = None  # ISO format, auto-filled if missing
    self_reported_deviations: list[str] = []


class LogExitRequest(BaseModel):
    price: float
    contracts: int
    time: Optional[str] = None
    exit_type: str  # target_1, target_2, stopped_out, manual, time_stop
    followed_plan: bool = True
    deviations: list[str] = []


class CancelPlanRequest(BaseModel):
    reason: str


class UpdateSettingsRequest(BaseModel):
    daily_loss_limit: Optional[float] = None
    account_size: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None
    confidence_threshold: Optional[int] = None
    commission_per_contract: Optional[float] = None
    revenge_cooldown_minutes: Optional[int] = None
    quick_check_cooldown_minutes: Optional[int] = None


# ─── Plans Routes ──────────────────────────────────────────────────────────────

@router.post("/plans")
async def create_plan(req: CreatePlanRequest):
    """Create a new plan (from LLM pipeline or manual entry)."""
    plan = {
        "session_id": req.session_id,
        "date": req.date,
        "ticker": req.ticker.upper(),
        "direction": req.direction,
        "status": "watching",
        "source": req.source,

        # Card
        "confidence": {
            "score": req.confidence_score,
            "grade": req.confidence_grade,
        },
        "entry_zone": {
            "low": req.entry_zone_low,
            "high": req.entry_zone_high,
        },
        "stop": {
            "price": req.stop_price,
            "reason": req.stop_reason,
        },
        "targets": req.targets or [],
        "strike": req.strike,
        "risk_reward": req.risk_reward,
        "size": {
            "contracts": req.size_contracts,
            "risk_dollars": req.size_risk_dollars,
        },
        "kill_switch": req.kill_switch,

        # Timing
        "timing": {
            "primary": req.timing_primary,
            "secondary": req.timing_secondary,
            "dead_zones": req.timing_dead_zones or [],
            "hard_cutoff": req.timing_hard_cutoff,
        },

        # Options
        "expected_premium": {
            "low": req.expected_premium_low,
            "high": req.expected_premium_high,
            "max_pay": req.expected_premium_max,
        },

        # Deep dive
        "thesis": req.thesis,
        "regime_context": req.regime_context,
        "catalyst_risk": req.catalyst_risk,
        "invalidation": req.invalidation or [],
        "cross_asset_note": req.cross_asset_note,
        "options_detail": req.options_detail,
        "scaling_strategy": req.scaling_strategy,
        "position_kill": req.position_kill or [],
        "discipline_note": req.discipline_note,

        # Checklists
        "checklist_premarket": req.checklist_premarket or {},
        "checklist_intraday": req.checklist_intraday or {},
        "confidence_breakdown": req.confidence_breakdown or {},

        # Lifecycle (empty until populated)
        "entry": None,
        "exits": [],
        "remaining_contracts": req.size_contracts or 0,
        "total_pnl_dollars": 0,
        "total_pnl_percent": 0,
        "r_realized": 0,
        "debrief": None,
        "cancellation": None,
    }

    plan_id = await db.create_plan_v2(plan.copy())
    plan["id"] = plan_id
    return plan


@router.get("/plans")
async def get_plans(date: Optional[str] = None, status: Optional[str] = None, session_id: Optional[str] = None):
    """Get plans, filtered by date and/or status and/or session."""
    if session_id:
        plans = await db.get_plans_by_session(session_id)
        if status:
            plans = [p for p in plans if p.get("status") == status]
        return {"plans": plans}

    if date:
        plans = await db.get_plans_by_date(date, status)
    else:
        # Default: today
        today = datetime.utcnow().strftime("%Y-%m-%d")
        plans = await db.get_plans_by_date(today, status)

    return {"plans": plans}


@router.get("/plans/history")
async def get_plans_history(days: int = 30):
    """Get plans grouped by date for history view."""
    plans = await db.get_plans_history(days)

    # Group by date
    by_date = {}
    for p in plans:
        d = p.get("date", "unknown")
        if d not in by_date:
            by_date[d] = {"date": d, "plans": [], "total_pnl": 0, "entered_count": 0, "rules_broken": 0}
        by_date[d]["plans"].append(p)
        by_date[d]["total_pnl"] += p.get("total_pnl_dollars", 0)
        if p.get("status") in ("entered", "exited", "stopped_out", "reviewed"):
            by_date[d]["entered_count"] += 1
        entry = p.get("entry", {})
        if entry and entry.get("deviation_count", 0) > 0:
            by_date[d]["rules_broken"] += 1

    # Sort by date descending
    history = sorted(by_date.values(), key=lambda x: x["date"], reverse=True)
    return {"history": history}


@router.get("/plans/search/{ticker}")
async def search_plans_by_ticker(ticker: str, limit: int = 50):
    """Search all plans for a ticker."""
    plans = await db.search_plans_by_ticker(ticker, limit)
    return {"plans": plans, "ticker": ticker.upper()}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get a single plan by ID."""
    plan = await db.get_plan_v2(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/plans/{plan_id}/entry")
async def log_entry(plan_id: str, req: LogEntryRequest):
    """Log an entry for a plan. Auto-detects deviations."""
    plan = await db.get_plan_v2(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.get("status") != "watching":
        raise HTTPException(status_code=400, detail=f"Cannot enter a plan with status '{plan['status']}'")

    # Auto-detect deviations
    auto_deviations = []

    # Check fill price vs entry zone
    entry_zone = plan.get("entry_zone", {})
    premium = plan.get("expected_premium", {})
    max_pay = premium.get("max_pay")
    if max_pay and req.fill_price > max_pay:
        auto_deviations.append("premium_above_max")

    # Check contracts vs planned size
    planned_size = plan.get("size", {}).get("contracts")
    if planned_size and req.contracts > planned_size:
        auto_deviations.append("oversized")

    # Check timing (basic — check if in dead zone by hour)
    # More sophisticated timing checks can be added later

    entry_time = req.time or datetime.utcnow().isoformat()

    entry_data = {
        "fill_price": req.fill_price,
        "contracts": req.contracts,
        "time": entry_time,
        "auto_deviations": auto_deviations,
        "self_reported_deviations": req.self_reported_deviations,
        "deviation_count": len(auto_deviations) + len(req.self_reported_deviations),
    }

    await db.update_plan_v2(plan_id, {
        "status": "entered",
        "entry": entry_data,
        "remaining_contracts": req.contracts,
    })

    return {
        "status": "entered",
        "entry": entry_data,
        "auto_deviations": auto_deviations,
    }


@router.post("/plans/{plan_id}/exit")
async def log_exit(plan_id: str, req: LogExitRequest):
    """Log an exit (partial or full). Calculates P&L."""
    plan = await db.get_plan_v2(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.get("status") not in ("entered",):
        raise HTTPException(status_code=400, detail=f"Cannot exit a plan with status '{plan['status']}'")

    entry = plan.get("entry", {})
    fill_price = entry.get("fill_price", 0)
    remaining = plan.get("remaining_contracts", 0)

    if req.contracts > remaining:
        raise HTTPException(status_code=400, detail=f"Cannot exit {req.contracts} contracts, only {remaining} remaining")

    # Calculate P&L for this exit
    direction = plan.get("direction", "call")
    if direction == "call":
        pnl_per_contract = (req.price - fill_price) * 100
    else:
        pnl_per_contract = (fill_price - req.price) * 100  # For puts bought

    # Actually for options: P&L = (exit_premium - entry_premium) * 100 * contracts
    # fill_price IS the premium paid, req.price IS the premium received
    pnl_dollars = (req.price - fill_price) * 100 * req.contracts
    pnl_percent = ((req.price - fill_price) / fill_price * 100) if fill_price > 0 else 0

    exit_time = req.time or datetime.utcnow().isoformat()
    new_remaining = remaining - req.contracts

    exit_data = {
        "price": req.price,
        "contracts": req.contracts,
        "time": exit_time,
        "type": req.exit_type,
        "followed_plan": req.followed_plan,
        "deviations": req.deviations,
        "pnl_dollars": round(pnl_dollars, 2),
        "pnl_percent": round(pnl_percent, 2),
        "remaining_after": new_remaining,
    }

    await db.add_plan_exit(plan_id, exit_data)

    # Calculate new totals
    existing_exits = plan.get("exits", [])
    all_pnl = sum(e.get("pnl_dollars", 0) for e in existing_exits) + pnl_dollars

    # Determine final status
    new_status = "entered"  # still open
    if new_remaining == 0:
        new_status = "stopped_out" if req.exit_type == "stopped_out" else "exited"

    updates = {
        "total_pnl_dollars": round(all_pnl, 2),
        "status": new_status,
    }

    # Calculate total P&L percent and R realized
    total_entry_cost = fill_price * 100 * entry.get("contracts", remaining)
    if total_entry_cost > 0:
        updates["total_pnl_percent"] = round(all_pnl / total_entry_cost * 100, 2)

    stop_price = plan.get("stop", {}).get("price")
    if stop_price and fill_price > 0:
        risk_per_contract = abs(fill_price - stop_price) * 100  # rough risk estimate
        total_risk = risk_per_contract * entry.get("contracts", remaining)
        if total_risk > 0:
            updates["r_realized"] = round(all_pnl / total_risk, 2)

    await db.update_plan_v2(plan_id, updates)

    return {
        "status": new_status,
        "exit": exit_data,
        "total_pnl_dollars": updates.get("total_pnl_dollars", 0),
        "remaining_contracts": new_remaining,
    }


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan(plan_id: str, req: CancelPlanRequest):
    """Cancel a watching plan."""
    plan = await db.get_plan_v2(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.get("status") != "watching":
        raise HTTPException(status_code=400, detail="Only watching plans can be cancelled")

    await db.update_plan_v2(plan_id, {
        "status": "cancelled",
        "cancellation": {
            "reason": req.reason,
            "time": datetime.utcnow().isoformat(),
        }
    })

    return {"status": "cancelled", "reason": req.reason}


# ─── Settings Routes ───────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    """Get user settings."""
    settings = await db.get_settings()
    settings.pop("_type", None)
    return settings


@router.put("/settings")
async def update_settings(req: UpdateSettingsRequest):
    """Update user settings."""
    updates = {k: v for k, v in req.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No settings to update")
    await db.update_settings(updates)
    settings = await db.get_settings()
    settings.pop("_type", None)
    return settings


# ─── Watchlist Routes ──────────────────────────────────────────────────────────

@router.get("/watchlist")
async def get_watchlist():
    """Get saved watchlist."""
    tickers = await db.get_watchlist()
    return {"tickers": tickers}


@router.put("/watchlist")
async def update_watchlist(tickers: list[str]):
    """Update saved watchlist."""
    await db.update_watchlist(tickers)
    return {"tickers": [t.upper() for t in tickers]}

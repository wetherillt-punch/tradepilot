"""
TradePilot Database Layer
MongoDB operations for trade plans, journal entries, and historical data.
"""

import os
from datetime import datetime, date
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING
from bson import ObjectId


class Database:
    """Async MongoDB client for TradePilot."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[os.getenv("MONGODB_DB", "tradepilot")]

        # Create indexes
        await self.db.trade_plans.create_index([("created_at", DESCENDING)])
        await self.db.trade_plans.create_index("ticker")
        await self.db.trade_plans.create_index("setup_type")
        await self.db.journal.create_index([("created_at", DESCENDING)])
        await self.db.journal.create_index("ticker")
        await self.db.journal.create_index("trade_plan_id")
        await self.db.historical_events.create_index("event_type")
        await self.db.historical_events.create_index("date")

    async def disconnect(self):
        if self.client:
            self.client.close()

    # ─── Trade Plans ──────────────────────────────────────────────────────

    async def save_trade_plan(self, plan: dict) -> str:
        plan["created_at"] = datetime.utcnow()
        result = await self.db.trade_plans.insert_one(plan)
        return str(result.inserted_id)

    async def get_trade_plan(self, plan_id: str) -> Optional[dict]:
        doc = await self.db.trade_plans.find_one({"_id": ObjectId(plan_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_recent_plans(self, limit: int = 20) -> list[dict]:
        cursor = self.db.trade_plans.find().sort("created_at", DESCENDING).limit(limit)
        plans = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            plans.append(doc)
        return plans

    async def get_plans_by_ticker(self, ticker: str, limit: int = 10) -> list[dict]:
        cursor = (
            self.db.trade_plans
            .find({"ticker": ticker.upper()})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        plans = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            plans.append(doc)
        return plans

    async def get_plans_by_setup(self, setup_type: str, limit: int = 20) -> list[dict]:
        cursor = (
            self.db.trade_plans
            .find({"setup_type": setup_type})
            .sort("created_at", DESCENDING)
            .limit(limit)
        )
        plans = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            plans.append(doc)
        return plans

    # ─── Journal Entries ──────────────────────────────────────────────────

    async def save_journal_entry(self, entry: dict) -> str:
        entry["created_at"] = datetime.utcnow()
        result = await self.db.journal.insert_one(entry)
        return str(result.inserted_id)

    async def get_journal_entries(self, limit: int = 50) -> list[dict]:
        cursor = self.db.journal.find().sort("created_at", DESCENDING).limit(limit)
        entries = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            entries.append(doc)
        return entries

    async def get_journal_by_ticker(self, ticker: str) -> list[dict]:
        cursor = self.db.journal.find({"ticker": ticker.upper()}).sort("created_at", DESCENDING)
        entries = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            entries.append(doc)
        return entries

    async def get_journal_by_setup(self, setup_type: str) -> list[dict]:
        """Get journal entries by setup type for win rate calculation."""
        cursor = self.db.journal.find({"setup_type": setup_type}).sort("created_at", DESCENDING)
        entries = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            entries.append(doc)
        return entries

    async def get_win_rate(self, setup_type: Optional[str] = None) -> Optional[float]:
        """Calculate win rate from journal entries."""
        query = {}
        if setup_type:
            query["setup_type"] = setup_type

        cursor = self.db.journal.find(query)
        wins = 0
        total = 0
        async for doc in cursor:
            total += 1
            if doc.get("pnl_percent", 0) > 0:
                wins += 1

        if total == 0:
            return None
        return round((wins / total) * 100, 1)

    # ─── Performance Stats ────────────────────────────────────────────────

    async def get_performance_stats(self, days: int = 30) -> dict:
        """Aggregate performance statistics."""
        cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0)
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)

        cursor = self.db.journal.find({"created_at": {"$gte": cutoff}})
        entries = []
        async for doc in cursor:
            entries.append(doc)

        if not entries:
            return {"total_trades": 0, "message": "No trades in this period"}

        wins = [e for e in entries if e.get("pnl_percent", 0) > 0]
        losses = [e for e in entries if e.get("pnl_percent", 0) <= 0]

        avg_win = sum(e["pnl_percent"] for e in wins) / len(wins) if wins else 0
        avg_loss = sum(e["pnl_percent"] for e in losses) / len(losses) if losses else 0

        # Group by setup type
        setup_stats = {}
        for e in entries:
            st = e.get("setup_type", "unknown")
            if st not in setup_stats:
                setup_stats[st] = {"wins": 0, "losses": 0, "total_pnl": 0}
            if e.get("pnl_percent", 0) > 0:
                setup_stats[st]["wins"] += 1
            else:
                setup_stats[st]["losses"] += 1
            setup_stats[st]["total_pnl"] += e.get("pnl_percent", 0)

        return {
            "period_days": days,
            "total_trades": len(entries),
            "win_rate": round(len(wins) / len(entries) * 100, 1),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else float("inf"),
            "total_pnl_pct": round(sum(e.get("pnl_percent", 0) for e in entries), 2),
            "best_trade": round(max(e.get("pnl_percent", 0) for e in entries), 2),
            "worst_trade": round(min(e.get("pnl_percent", 0) for e in entries), 2),
            "setup_breakdown": setup_stats,
        }

    # ─── Historical Events ────────────────────────────────────────────────

    async def save_historical_event(self, event: dict) -> str:
        result = await self.db.historical_events.insert_one(event)
        return str(result.inserted_id)

    async def get_historical_events(self, event_type: Optional[str] = None) -> list[dict]:
        query = {}
        if event_type:
            query["event_type"] = event_type
        cursor = self.db.historical_events.find(query).sort("date", DESCENDING)
        events = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            events.append(doc)
        return events

    # ─── Session Cache ────────────────────────────────────────────────────

    async def cache_session(self, session_data: dict) -> str:
        session_data["cached_at"] = datetime.utcnow()
        # Upsert by session_id
        result = await self.db.sessions.replace_one(
            {"session_id": session_data["session_id"]},
            session_data,
            upsert=True
        )
        return session_data["session_id"]

    async def get_cached_session(self, session_id: str) -> Optional[dict]:
        return await self.db.sessions.find_one({"session_id": session_id})


# Singleton
db = Database()

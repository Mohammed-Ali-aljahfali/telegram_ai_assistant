"""database/repositories/statistics_repository.py — مستودع الإحصائيات"""
from datetime import datetime, date, timedelta
from typing import Optional
from database.connection import get_db
from infrastructure.logger import get_logger

logger = get_logger("statistics_repo")


class StatisticsRepository:

    def __init__(self):
        self.db = get_db()

    async def _ensure_today(self, bot_user_id: int):
        today = date.today().isoformat()
        await self.db.execute(
            """INSERT OR IGNORE INTO statistics (bot_user_id, date)
               VALUES (?,?)""",
            (bot_user_id, today)
        )

    async def increment(self, bot_user_id: int, field: str):
        valid = {"messages_received", "messages_sent", "new_customers", "ai_responses", "conversions"}
        if field not in valid:
            return
        await self._ensure_today(bot_user_id)
        today = date.today().isoformat()
        await self.db.execute(
            f"UPDATE statistics SET {field}={field}+1 WHERE bot_user_id=? AND date=?",
            (bot_user_id, today)
        )

    async def get_today(self, bot_user_id: int) -> dict:
        today = date.today().isoformat()
        row = await self.db.fetchone(
            "SELECT * FROM statistics WHERE bot_user_id=? AND date=?",
            (bot_user_id, today)
        )
        return dict(row) if row else self._empty_stats(bot_user_id)

    async def get_period(self, bot_user_id: int, days: int) -> dict:
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = await self.db.fetchall(
            "SELECT * FROM statistics WHERE bot_user_id=? AND date >= ? ORDER BY date",
            (bot_user_id, since)
        )
        totals = self._empty_stats(bot_user_id)
        for row in rows:
            d = dict(row)
            totals["messages_received"] += d.get("messages_received", 0)
            totals["messages_sent"] += d.get("messages_sent", 0)
            totals["new_customers"] += d.get("new_customers", 0)
            totals["ai_responses"] += d.get("ai_responses", 0)
            totals["conversions"] += d.get("conversions", 0)
        return totals

    def _empty_stats(self, bot_user_id: int) -> dict:
        return {
            "bot_user_id": bot_user_id,
            "messages_received": 0, "messages_sent": 0,
            "new_customers": 0, "ai_responses": 0, "conversions": 0
        }

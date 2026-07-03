"""database/repositories/notification_repository.py — مستودع التنبيهات"""
from datetime import datetime
from typing import Optional
from database.connection import get_db
from infrastructure.logger import get_logger

logger = get_logger("notification_repo")


class NotificationRepository:

    def __init__(self):
        self.db = get_db()

    async def create(self, bot_user_id: int, type_: str, title: str, content: str) -> int:
        uid = await self.db.execute(
            """INSERT INTO notifications (bot_user_id, type, title, content, is_read)
               VALUES (?,?,?,?,0)""",
            (bot_user_id, type_, title, content)
        )
        return uid

    async def get_unread(self, bot_user_id: int, limit: int = 20) -> list[dict]:
        rows = await self.db.fetchall(
            """SELECT * FROM notifications WHERE bot_user_id=? AND is_read=0
               ORDER BY created_at DESC LIMIT ?""",
            (bot_user_id, limit)
        )
        return [dict(r) for r in rows]

    async def get_recent(self, bot_user_id: int, limit: int = 20) -> list[dict]:
        rows = await self.db.fetchall(
            """SELECT * FROM notifications WHERE bot_user_id=?
               ORDER BY created_at DESC LIMIT ?""",
            (bot_user_id, limit)
        )
        return [dict(r) for r in rows]

    async def mark_read(self, notification_id: int):
        await self.db.execute(
            "UPDATE notifications SET is_read=1 WHERE id=?", (notification_id,)
        )

    async def mark_all_read(self, bot_user_id: int):
        await self.db.execute(
            "UPDATE notifications SET is_read=1 WHERE bot_user_id=?", (bot_user_id,)
        )

    async def count_unread(self, bot_user_id: int) -> int:
        row = await self.db.fetchone(
            "SELECT COUNT(*) FROM notifications WHERE bot_user_id=? AND is_read=0",
            (bot_user_id,)
        )
        return row[0] if row else 0

    async def cleanup_old(self, days: int = 30):
        await self.db.execute(
            "DELETE FROM notifications WHERE created_at < datetime('now', ?)",
            (f"-{days} days",)
        )

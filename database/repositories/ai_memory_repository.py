"""database/repositories/ai_memory_repository.py — مستودع ذاكرة الذكاء الاصطناعي"""
from datetime import datetime, timedelta
from typing import Optional
from database.connection import get_db
from infrastructure.logger import get_logger

logger = get_logger("ai_memory_repo")


class AIMemoryRepository:

    def __init__(self):
        self.db = get_db()

    async def store(self, customer_id: int, bot_user_id: int, memory_type: str,
                    content: str, importance: float = 0.5, expires_days: Optional[int] = None) -> int:
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        uid = await self.db.execute(
            """INSERT INTO ai_memory (customer_id, bot_user_id, memory_type, content, importance, expires_at)
               VALUES (?,?,?,?,?,?)""",
            (customer_id, bot_user_id, memory_type, content, importance, expires_at)
        )
        return uid

    async def get_for_customer(self, customer_id: int, limit: int = 10) -> list[dict]:
        rows = await self.db.fetchall(
            """SELECT * FROM ai_memory
               WHERE customer_id=? AND (expires_at IS NULL OR expires_at > datetime('now'))
               ORDER BY importance DESC, created_at DESC LIMIT ?""",
            (customer_id, limit)
        )
        return [dict(r) for r in rows]

    async def get_summary_context(self, customer_id: int) -> str:
        memories = await self.get_for_customer(customer_id, limit=5)
        if not memories:
            return ""
        lines = [f"- [{m['memory_type']}] {m['content']}" for m in memories]
        return "معلومات مهمة عن العميل:\n" + "\n".join(lines)

    async def cleanup_expired(self):
        await self.db.execute(
            "DELETE FROM ai_memory WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')"
        )

    async def clear_for_customer(self, customer_id: int):
        await self.db.execute(
            "DELETE FROM ai_memory WHERE customer_id=?", (customer_id,)
        )

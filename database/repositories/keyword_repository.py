"""database/repositories/keyword_repository.py — مستودع الكلمات المفتاحية"""
from datetime import datetime
from typing import Optional
from database.connection import get_db
from models.keyword import Keyword, KeywordCategory, KeywordAction
from infrastructure.logger import get_logger

logger = get_logger("keyword_repo")


class KeywordRepository:

    def __init__(self):
        self.db = get_db()

    async def add(self, keyword: Keyword) -> Keyword:
        uid = await self.db.execute(
            """INSERT INTO keywords (bot_user_id, keyword, category, action, reply_template, is_active)
               VALUES (?,?,?,?,?,?)""",
            (keyword.bot_user_id, keyword.keyword,
             keyword.category.value if keyword.category else "custom",
             keyword.action.value if keyword.action else "alert",
             keyword.reply_template, 1 if keyword.is_active else 0)
        )
        keyword.id = uid
        return keyword

    async def remove(self, keyword_id: int, bot_user_id: int):
        await self.db.execute(
            "DELETE FROM keywords WHERE id=? AND bot_user_id=?",
            (keyword_id, bot_user_id)
        )

    async def get_all_for_user(self, bot_user_id: int) -> list[Keyword]:
        rows = await self.db.fetchall(
            "SELECT * FROM keywords WHERE bot_user_id=? ORDER BY created_at DESC",
            (bot_user_id,)
        )
        return [self._row_to_model(r) for r in rows]

    async def get_all_active(self, bot_user_id: int) -> list[Keyword]:
        rows = await self.db.fetchall(
            "SELECT * FROM keywords WHERE bot_user_id=? AND is_active=1",
            (bot_user_id,)
        )
        return [self._row_to_model(r) for r in rows]

    async def toggle_active(self, keyword_id: int, bot_user_id: int):
        row = await self.db.fetchone(
            "SELECT is_active FROM keywords WHERE id=? AND bot_user_id=?",
            (keyword_id, bot_user_id)
        )
        new_val = 0 if (row and row[0]) else 1
        await self.db.execute(
            "UPDATE keywords SET is_active=? WHERE id=?", (new_val, keyword_id)
        )

    async def check_message(self, message_text: str, bot_user_id: int) -> list[Keyword]:
        """تحقق إذا كانت الرسالة تحتوي على كلمات مفتاحية"""
        keywords = await self.get_all_active(bot_user_id)
        text_lower = message_text.lower()
        return [kw for kw in keywords if kw.keyword.lower() in text_lower]

    def _row_to_model(self, row) -> Keyword:
        d = dict(row)
        d["is_active"] = bool(d.get("is_active", 1))
        return Keyword(**d)

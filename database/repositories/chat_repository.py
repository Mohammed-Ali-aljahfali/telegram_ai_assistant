"""database/repositories/chat_repository.py — مستودع المحادثات"""
from datetime import datetime
from typing import Optional
from database.connection import get_db
from models.chat import Chat, ChatType
from infrastructure.logger import get_logger

logger = get_logger("chat_repo")


class ChatRepository:

    def __init__(self):
        self.db = get_db()

    async def create_or_update(self, chat: Chat) -> Chat:
        existing = await self.get_by_chat_id(chat.bot_user_id, chat.chat_id)
        if existing:
            return existing
        uid = await self.db.execute(
            """INSERT OR REPLACE INTO chats
               (bot_user_id, customer_id, chat_id, chat_type, title, username, auto_reply, ai_enabled)
               VALUES (?,?,?,?,?,?,?,?)""",
            (chat.bot_user_id, chat.customer_id, chat.chat_id,
             chat.chat_type.value if chat.chat_type else "private",
             chat.title, chat.username,
             1 if chat.auto_reply else 0,
             1 if chat.ai_enabled else 0)
        )
        chat.id = uid
        return chat

    async def get_by_chat_id(self, bot_user_id: int, chat_id: int) -> Optional[Chat]:
        row = await self.db.fetchone(
            "SELECT * FROM chats WHERE bot_user_id=? AND chat_id=?",
            (bot_user_id, chat_id)
        )
        return self._row_to_model(row) if row else None

    async def get_by_id(self, chat_id: int) -> Optional[Chat]:
        row = await self.db.fetchone("SELECT * FROM chats WHERE id=?", (chat_id,))
        return self._row_to_model(row) if row else None

    async def get_all_for_user(self, bot_user_id: int, page: int = 1, per_page: int = 10) -> list[Chat]:
        offset = (page - 1) * per_page
        rows = await self.db.fetchall(
            "SELECT * FROM chats WHERE bot_user_id=? AND status='active' ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (bot_user_id, per_page, offset)
        )
        return [self._row_to_model(r) for r in rows]

    async def count_for_user(self, bot_user_id: int) -> int:
        row = await self.db.fetchone(
            "SELECT COUNT(*) FROM chats WHERE bot_user_id=?", (bot_user_id,)
        )
        return row[0] if row else 0

    async def toggle_auto_reply(self, bot_user_id: int, chat_id: int) -> bool:
        row = await self.db.fetchone(
            "SELECT auto_reply FROM chats WHERE bot_user_id=? AND chat_id=?",
            (bot_user_id, chat_id)
        )
        new_val = 0 if (row and row[0]) else 1
        await self.db.execute(
            "UPDATE chats SET auto_reply=? WHERE bot_user_id=? AND chat_id=?",
            (new_val, bot_user_id, chat_id)
        )
        return bool(new_val)

    async def toggle_ai(self, bot_user_id: int, chat_id: int) -> bool:
        row = await self.db.fetchone(
            "SELECT ai_enabled FROM chats WHERE bot_user_id=? AND chat_id=?",
            (bot_user_id, chat_id)
        )
        new_val = 0 if (row and row[0]) else 1
        await self.db.execute(
            "UPDATE chats SET ai_enabled=? WHERE bot_user_id=? AND chat_id=?",
            (new_val, bot_user_id, chat_id)
        )
        return bool(new_val)

    def _row_to_model(self, row) -> Chat:
        d = dict(row)
        d["auto_reply"] = bool(d.get("auto_reply", 1))
        d["ai_enabled"] = bool(d.get("ai_enabled", 1))
        return Chat(**d)

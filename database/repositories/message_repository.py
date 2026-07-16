"""database/repositories/message_repository.py — مستودع الرسائل"""
from datetime import datetime, timedelta
from typing import Optional
from database.connection import get_db
from models.message import Message, MessageIntent, SenderType, MessageType
from infrastructure.logger import get_logger

logger = get_logger("message_repo")


class MessageRepository:

    def __init__(self):
        self.db = get_db()

    async def create(self, message: Message) -> Message:
        uid = await self.db.execute(
            """INSERT INTO messages
               (chat_id, telegram_msg_id, sender_id, sender_type, content,
                message_type, intent, sentiment, is_important, ai_analyzed, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (message.chat_id, message.telegram_msg_id, message.sender_id,
             message.sender_type.value if message.sender_type else "user",
             message.content,
             message.message_type.value if message.message_type else "text",
             message.intent.value if message.intent else None,
             message.sentiment.value if message.sentiment else None,
             1 if message.is_important else 0,
             1 if message.ai_analyzed else 0,
             message.created_at or datetime.now())
        )
        message.id = uid
        return message

    async def get_recent_for_chat(self, chat_id: int, limit: int = 20) -> list[Message]:
        rows = await self.db.fetchall(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at DESC LIMIT ?",
            (chat_id, limit)
        )
        return [self._row_to_model(r) for r in reversed(rows)]

    async def get_by_intent(self, chat_id: int, intent: MessageIntent) -> list[Message]:
        rows = await self.db.fetchall(
            "SELECT * FROM messages WHERE chat_id=? AND intent=? ORDER BY created_at DESC",
            (chat_id, intent.value)
        )
        return [self._row_to_model(r) for r in rows]

    async def count_for_period(self, bot_user_id: int, days: int = 1) -> int:
        since = datetime.now() - timedelta(days=days)
        row = await self.db.fetchone(
            """SELECT COUNT(*) FROM messages m
               JOIN chats c ON m.chat_id=c.id
               WHERE c.bot_user_id=? AND m.created_at >= ?""",
            (bot_user_id, since)
        )
        return row[0] if row else 0

    async def mark_analyzed(self, message_id: int):
        await self.db.execute(
            "UPDATE messages SET ai_analyzed=1 WHERE id=?", (message_id,)
        )

    async def update_analysis(self, message_id: int, intent: Optional[str], sentiment: Optional[str], is_important: bool):
        await self.db.execute(
            """UPDATE messages SET intent=?, sentiment=?, is_important=?, ai_analyzed=1
               WHERE id=?""",
            (intent, sentiment, 1 if is_important else 0, message_id)
        )

    async def get_unanalyzed(self, limit: int = 50) -> list[Message]:
        rows = await self.db.fetchall(
            "SELECT * FROM messages WHERE ai_analyzed=0 ORDER BY created_at ASC LIMIT ?",
            (limit,)
        )
        return [self._row_to_model(r) for r in rows]

    def _row_to_model(self, row) -> Message:
        d = dict(row)
        d["is_important"] = bool(d.get("is_important", 0))
        d["ai_analyzed"] = bool(d.get("ai_analyzed", 0))
        return Message(**d)

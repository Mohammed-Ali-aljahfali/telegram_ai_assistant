"""database/repositories/user_repository.py — مستودع مستخدمي البوت"""
import json
from datetime import datetime
from typing import Optional
from database.connection import get_db
from models.user import BotUser, UserRole, UserStatus
from infrastructure.logger import get_logger

logger = get_logger("user_repo")


class UserRepository:

    def __init__(self):
        self.db = get_db()

    async def create(self, user: BotUser) -> BotUser:
        uid = await self.db.execute(
            """INSERT OR IGNORE INTO bot_users
               (telegram_id, username, first_name, phone, role, status, settings)
               VALUES (?,?,?,?,?,?,?)""",
            (user.telegram_id, user.username, user.first_name,
             user.phone, user.role.value, user.status.value,
             json.dumps(user.settings))
        )
        user.id = uid
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[BotUser]:
        row = await self.db.fetchone(
            "SELECT * FROM bot_users WHERE telegram_id=?", (telegram_id,)
        )
        return self._row_to_model(row) if row else None

    async def get_by_id(self, user_id: int) -> Optional[BotUser]:
        row = await self.db.fetchone("SELECT * FROM bot_users WHERE id=?", (user_id,))
        return self._row_to_model(row) if row else None

    async def get_all(self, page: int = 1, per_page: int = 20) -> list[BotUser]:
        offset = (page - 1) * per_page
        rows = await self.db.fetchall(
            "SELECT * FROM bot_users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        return [self._row_to_model(r) for r in rows]

    async def count_all(self) -> int:
        row = await self.db.fetchone("SELECT COUNT(*) FROM bot_users")
        return row[0] if row else 0

    async def get_by_role(self, role: UserRole) -> list[BotUser]:
        rows = await self.db.fetchall(
            "SELECT * FROM bot_users WHERE role=?", (role.value,)
        )
        return [self._row_to_model(r) for r in rows]

    async def update(self, user: BotUser) -> bool:
        await self.db.execute(
            """UPDATE bot_users SET username=?, first_name=?, phone=?,
               role=?, status=?, settings=?, last_active=?
               WHERE telegram_id=?""",
            (user.username, user.first_name, user.phone,
             user.role.value, user.status.value,
             json.dumps(user.settings), datetime.now(),
             user.telegram_id)
        )
        return True

    async def update_session(self, telegram_id: int, session: Optional[str], is_authenticated: bool):
        await self.db.execute(
            "UPDATE bot_users SET telethon_session=?, is_authenticated=?, last_active=? WHERE telegram_id=?",
            (session, 1 if is_authenticated else 0, datetime.now(), telegram_id)
        )

    async def update_status(self, telegram_id: int, status: UserStatus):
        await self.db.execute(
            "UPDATE bot_users SET status=? WHERE telegram_id=?",
            (status.value, telegram_id)
        )

    async def update_role(self, telegram_id: int, role: UserRole):
        await self.db.execute(
            "UPDATE bot_users SET role=? WHERE telegram_id=?",
            (role.value, telegram_id)
        )

    async def update_last_active(self, telegram_id: int):
        await self.db.execute(
            "UPDATE bot_users SET last_active=? WHERE telegram_id=?",
            (datetime.now(), telegram_id)
        )

    async def update_phone(self, telegram_id: int, phone: str):
        await self.db.execute(
            "UPDATE bot_users SET phone=? WHERE telegram_id=?",
            (phone, telegram_id)
        )

    async def delete(self, telegram_id: int):
        await self.db.execute(
            "DELETE FROM bot_users WHERE telegram_id=?", (telegram_id,)
        )

    async def exists(self, telegram_id: int) -> bool:
        row = await self.db.fetchone(
            "SELECT 1 FROM bot_users WHERE telegram_id=?", (telegram_id,)
        )
        return row is not None

    def _row_to_model(self, row) -> BotUser:
        d = dict(row)
        d["is_authenticated"] = bool(d.get("is_authenticated", 0))
        settings = d.get("settings", "{}")
        try:
            d["settings"] = json.loads(settings) if settings else {}
        except Exception:
            d["settings"] = {}
        return BotUser(**d)

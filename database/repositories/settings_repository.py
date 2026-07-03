"""database/repositories/settings_repository.py — مستودع الإعدادات"""
import json
from datetime import datetime
from typing import Optional, Any
from database.connection import get_db
from infrastructure.logger import get_logger

logger = get_logger("settings_repo")


class SettingsRepository:

    def __init__(self):
        self.db = get_db()

    async def get(self, key: str, bot_user_id: Optional[int] = None, default: Any = None) -> Any:
        if bot_user_id is not None:
            row = await self.db.fetchone(
                "SELECT value, value_type FROM settings WHERE key=? AND bot_user_id=?",
                (key, bot_user_id)
            )
            if not row:
                row = await self.db.fetchone(
                    "SELECT value, value_type FROM settings WHERE key=? AND bot_user_id IS NULL",
                    (key,)
                )
        else:
            row = await self.db.fetchone(
                "SELECT value, value_type FROM settings WHERE key=? AND bot_user_id IS NULL",
                (key,)
            )
        if not row:
            return default
        return self._cast(row["value"], row["value_type"])

    async def set(self, key: str, value: Any, bot_user_id: Optional[int] = None,
                  value_type: str = "string", category: str = "general", description: str = ""):
        if isinstance(value, bool):
            value_type = "bool"
            str_value = "true" if value else "false"
        elif isinstance(value, int):
            value_type = "int"
            str_value = str(value)
        elif isinstance(value, (dict, list)):
            value_type = "json"
            str_value = json.dumps(value, ensure_ascii=False)
        else:
            str_value = str(value) if value is not None else None

        await self.db.execute(
            """INSERT INTO settings (bot_user_id, key, value, value_type, category, description, updated_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(bot_user_id, key) DO UPDATE SET
               value=excluded.value, value_type=excluded.value_type, updated_at=excluded.updated_at""",
            (bot_user_id, key, str_value, value_type, category, description, datetime.now())
        )

    async def get_all_for_user(self, bot_user_id: int) -> dict:
        rows = await self.db.fetchall(
            "SELECT key, value, value_type FROM settings WHERE bot_user_id=? OR bot_user_id IS NULL",
            (bot_user_id,)
        )
        result = {}
        for row in rows:
            result[row["key"]] = self._cast(row["value"], row["value_type"])
        return result

    async def delete(self, key: str, bot_user_id: Optional[int] = None):
        await self.db.execute(
            "DELETE FROM settings WHERE key=? AND bot_user_id IS ?",
            (key, bot_user_id)
        )

    def _cast(self, value: Optional[str], value_type: str) -> Any:
        if value is None:
            return None
        if value_type == "int":
            return int(value)
        if value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        if value_type == "json":
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

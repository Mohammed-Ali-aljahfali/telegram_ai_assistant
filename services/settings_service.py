"""services/settings_service.py — خدمة الإعدادات"""
from typing import Any, Optional
from database.repositories.settings_repository import SettingsRepository
from infrastructure.logger import get_logger

logger = get_logger("settings_service")

# قيم افتراضية
DEFAULTS = {
    "auto_reply_enabled": True,
    "ai_enabled": True,
    "working_hours_enabled": False,
    "working_hours_start": "09:00",
    "working_hours_end": "22:00",
    "subscription_enforcement": False,
    "notification_new_customer": True,
    "notification_keyword": True,
    "notification_daily_summary": True,
    "ai_temperature": 0.7,
    "ai_max_tokens": 800,
    "ai_provider": "openai",
    "ai_model": "gpt-4o-mini",
    "response_delay_seconds": 2,
    "max_messages_per_customer_per_day": 50,
}


class SettingsService:

    def __init__(self):
        self.repo = SettingsRepository()

    async def get(self, key: str, bot_user_id: Optional[int] = None) -> Any:
        value = await self.repo.get(key, bot_user_id)
        if value is None:
            return DEFAULTS.get(key)
        return value

    async def set(self, key: str, value: Any, bot_user_id: Optional[int] = None):
        await self.repo.set(key, value, bot_user_id)

    async def get_all(self, bot_user_id: int) -> dict:
        stored = await self.repo.get_all_for_user(bot_user_id)
        result = dict(DEFAULTS)
        result.update(stored)
        return result

    async def is_auto_reply_enabled(self, bot_user_id: int) -> bool:
        return bool(await self.get("auto_reply_enabled", bot_user_id))

    async def is_ai_enabled(self, bot_user_id: int) -> bool:
        return bool(await self.get("ai_enabled", bot_user_id))

    async def is_subscription_enforcement(self) -> bool:
        return bool(await self.get("subscription_enforcement"))

    async def toggle_subscription_enforcement(self) -> bool:
        current = await self.is_subscription_enforcement()
        new_val = not current
        await self.set("subscription_enforcement", new_val)
        return new_val

    async def get_ai_provider_name(self, bot_user_id: int) -> str:
        return await self.get("ai_provider", bot_user_id) or "openai"

    async def get_ai_model(self, bot_user_id: int) -> str:
        return await self.get("ai_model", bot_user_id) or "gpt-4o-mini"

    async def get_ai_temperature(self, bot_user_id: int) -> float:
        val = await self.get("ai_temperature", bot_user_id)
        return float(val) if val is not None else 0.7

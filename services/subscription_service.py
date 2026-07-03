"""services/subscription_service.py — خدمة الاشتراك الإجباري"""
import httpx
from typing import Optional
from config import config
from database.repositories.channel_repository import ChannelRepository
from database.repositories.settings_repository import SettingsRepository
from models.chat import RequiredChannel
from infrastructure.logger import get_logger

logger = get_logger("subscription_service")


class SubscriptionService:

    def __init__(self):
        self.channel_repo = ChannelRepository()
        self.settings_repo = SettingsRepository()

    async def is_enforcement_enabled(self) -> bool:
        val = await self.settings_repo.get("subscription_enforcement")
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    async def toggle_enforcement(self, enabled: bool):
        await self.settings_repo.set(
            "subscription_enforcement", enabled,
            value_type="bool", category="system"
        )
        logger.info(f"🔔 الاشتراك الإجباري: {'مفعّل' if enabled else 'معطّل'}")

    async def get_required_channels(self) -> list[RequiredChannel]:
        return await self.channel_repo.get_required_channels()

    async def add_required_channel(self, channel_id: int, username: str,
                                    title: str, added_by: int) -> RequiredChannel:
        channel = RequiredChannel(
            channel_id=channel_id,
            channel_username=username,
            title=title,
            added_by=added_by
        )
        return await self.channel_repo.add_required_channel(channel)

    async def remove_required_channel(self, channel_id: int):
        await self.channel_repo.remove_required_channel(channel_id)

    async def check_user_subscriptions(self, telegram_id: int) -> dict[int, bool]:
        """تحقق من اشتراك المستخدم في جميع القنوات المطلوبة"""
        channels = await self.get_required_channels()
        results: dict[int, bool] = {}
        if not channels:
            return results

        async with httpx.AsyncClient(timeout=10) as client:
            for ch in channels:
                try:
                    resp = await client.get(
                        f"https://api.telegram.org/bot{config.BOT_TOKEN}/getChatMember",
                        params={"chat_id": ch.channel_id, "user_id": telegram_id}
                    )
                    data = resp.json()
                    if data.get("ok"):
                        status = data["result"].get("status", "")
                        results[ch.channel_id] = status in (
                            "member", "administrator", "creator"
                        )
                    else:
                        results[ch.channel_id] = False
                except Exception as e:
                    logger.error(f"خطأ في التحقق من {ch.channel_id}: {e}")
                    results[ch.channel_id] = False

        return results

    async def is_user_subscribed_to_all(self, telegram_id: int) -> bool:
        """هل المستخدم مشترك في جميع القنوات؟"""
        if not await self.is_enforcement_enabled():
            return True
        results = await self.check_user_subscriptions(telegram_id)
        return all(results.values()) if results else True

    async def get_unsubscribed_channels(self, telegram_id: int) -> list[RequiredChannel]:
        """القنوات التي لم يشترك فيها المستخدم"""
        results = await self.check_user_subscriptions(telegram_id)
        all_channels = await self.get_required_channels()
        return [ch for ch in all_channels if not results.get(ch.channel_id, False)]

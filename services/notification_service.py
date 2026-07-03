"""services/notification_service.py — خدمة الإشعارات"""
from typing import Optional, TYPE_CHECKING
from database.repositories.notification_repository import NotificationRepository
from infrastructure.logger import get_logger

if TYPE_CHECKING:
    from telegram.ext import Application

logger = get_logger("notification_service")


class NotificationService:

    def __init__(self, bot_app=None):
        self.repo = NotificationRepository()
        self._bot_app = bot_app

    def set_bot_app(self, bot_app):
        self._bot_app = bot_app

    async def send(self, bot_user_id: int, telegram_id: int,
                   type_: str, title: str, content: str) -> int:
        """حفظ التنبيه في قاعدة البيانات وإرساله فوراً عبر البوت"""
        notif_id = await self.repo.create(bot_user_id, type_, title, content)
        await self.send_immediate(telegram_id, f"🔔 *{title}*\n\n{content}")
        return notif_id

    async def send_immediate(self, telegram_id: int, text: str):
        """إرسال رسالة فورية عبر البوت"""
        if not self._bot_app:
            logger.warning("Bot app غير متاح")
            return
        try:
            await self._bot_app.bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"فشل إرسال التنبيه لـ {telegram_id}: {e}")

    async def get_unread(self, bot_user_id: int) -> list[dict]:
        return await self.repo.get_unread(bot_user_id)

    async def get_recent(self, bot_user_id: int) -> list[dict]:
        return await self.repo.get_recent(bot_user_id)

    async def mark_read(self, notification_id: int):
        await self.repo.mark_read(notification_id)

    async def mark_all_read(self, bot_user_id: int):
        await self.repo.mark_all_read(bot_user_id)

    async def count_unread(self, bot_user_id: int) -> int:
        return await self.repo.count_unread(bot_user_id)

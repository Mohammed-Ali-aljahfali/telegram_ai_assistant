"""telethon_client/client.py — مدير عملاء Telethon"""
import asyncio
from typing import Optional, Callable
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config import config
from infrastructure.logger import get_logger
from infrastructure.crypto import decrypt_text

logger = get_logger("telethon.client")


class TelethonClientManager:
    """يدير عملاء Telethon لكل مستخدم"""

    def __init__(self):
        self._clients: dict[int, TelegramClient] = {}
        self._message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """تعيين دالة المعالجة عند وصول رسالة جديدة"""
        self._message_callback = callback

    async def create_and_start(self, bot_user_id: int, encrypted_session: str) -> bool:
        """إنشاء وبدء عميل Telethon لمستخدم"""
        try:
            if bot_user_id in self._clients:
                if self._clients[bot_user_id].is_connected():
                    return True

            session_str = decrypt_text(encrypted_session)
            client = TelegramClient(
                StringSession(session_str),
                config.API_ID,
                config.API_HASH
            )
            await client.connect()

            if not await client.is_user_authorized():
                logger.warning(f"⚠️ جلسة المستخدم {bot_user_id} غير مصرح بها")
                return False

            self._clients[bot_user_id] = client
            self._register_handlers(client, bot_user_id)
            logger.info(f"✅ Telethon client بدأ للمستخدم {bot_user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ خطأ في بدء client للمستخدم {bot_user_id}: {e}")
            return False

    def _register_handlers(self, client: TelegramClient, bot_user_id: int):
        """تسجيل معالجات الأحداث"""
        @client.on(events.NewMessage(incoming=True))
        async def on_new_message(event):
            if self._message_callback:
                try:
                    await self._message_callback(event, bot_user_id)
                except Exception as e:
                    logger.error(f"خطأ في معالجة الرسالة: {e}")

    async def get_client(self, bot_user_id: int) -> Optional[TelegramClient]:
        client = self._clients.get(bot_user_id)
        if client and client.is_connected():
            return client
        return None

    async def stop(self, bot_user_id: int):
        """إيقاف عميل مستخدم"""
        client = self._clients.pop(bot_user_id, None)
        if client:
            try:
                await client.disconnect()
                logger.info(f"🛑 Telethon client أُوقف للمستخدم {bot_user_id}")
            except Exception:
                pass

    async def stop_all(self):
        """إيقاف جميع العملاء"""
        for uid in list(self._clients.keys()):
            await self.stop(uid)

    async def send_message(self, bot_user_id: int, chat_id: int, text: str) -> bool:
        """إرسال رسالة بصفة المستخدم"""
        client = await self.get_client(bot_user_id)
        if not client:
            return False
        try:
            await client.send_message(chat_id, text)
            return True
        except Exception as e:
            logger.error(f"send_message error: {e}")
            return False

    async def get_me(self, bot_user_id: int) -> Optional[dict]:
        client = await self.get_client(bot_user_id)
        if not client:
            return None
        try:
            me = await client.get_me()
            return {"id": me.id, "first_name": me.first_name,
                    "username": me.username, "phone": me.phone}
        except Exception:
            return None

    def is_connected(self, bot_user_id: int) -> bool:
        client = self._clients.get(bot_user_id)
        return client is not None and client.is_connected()

    def get_connected_count(self) -> int:
        return sum(1 for c in self._clients.values() if c.is_connected())


telethon_manager = TelethonClientManager()

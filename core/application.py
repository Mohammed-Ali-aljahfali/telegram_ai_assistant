"""core/application.py — تطبيق المساعد الذكي الرئيسي"""
import asyncio
from infrastructure.logger import get_logger
from config import config

logger = get_logger("core.app")


class TelegramAIApplication:
    """المدير الرئيسي للتطبيق"""

    def __init__(self):
        self.db = None
        self.bot_app = None
        self.notification_service = None

    async def initialize(self):
        """تهيئة جميع مكونات النظام"""
        logger.info("🚀 تهيئة المساعد الذكي...")

        # 0. فحوصات سلامة التخزين — يجب أن تكون أول شيء
        from infrastructure.startup_checks import run_startup_checks
        await run_startup_checks()

        # 1. التحقق من الإعدادات
        errors = config.validate()
        if errors:
            for e in errors:
                logger.error(f"❌ إعداد مفقود: {e}")
            raise ValueError(f"إعدادات مفقودة: {', '.join(errors)}")

        # 2. تهيئة قاعدة البيانات
        from database.connection import get_db
        self.db = get_db()
        await self.db.initialize()
        logger.info("✅ قاعدة البيانات جاهزة")


        # 3. بناء تطبيق البوت
        from bot.bot_app import build_application
        self.bot_app = build_application()
        logger.info("✅ البوت جاهز")

        # 4. تهيئة خدمة الإشعارات
        from services.notification_service import NotificationService
        self.notification_service = NotificationService(self.bot_app.bot)

        # 5. ربط callback الرسائل مع Telethon
        from telethon_client.client import telethon_manager
        from core.message_processor import process_incoming_message
        telethon_manager.set_message_callback(
            lambda event, uid: process_incoming_message(event, uid, self.bot_app, self.notification_service)
        )

        # 6. استعادة جلسات Telethon للمستخدمين المصادقين
        await self._restore_sessions()

        # 7. جدولة المهام الدورية
        from infrastructure.scheduler import task_scheduler
        from database.backup import backup_database
        task_scheduler.add_cron_job(backup_database, config.BACKUP_HOUR, 0, "daily_backup")
        task_scheduler.start()
        logger.info("✅ مجدول المهام بدأ")

        logger.info("🎉 جميع المكونات جاهزة!")

    async def _restore_sessions(self):
        """استعادة جلسات Telethon عند بدء التشغيل"""
        from database.repositories.user_repository import UserRepository
        from telethon_client.client import telethon_manager

        repo = UserRepository()
        users = await repo.get_all(per_page=100)
        count = 0
        for user in users:
            if user.is_authenticated and user.telethon_session:
                try:
                    ok = await telethon_manager.create_and_start(user.telegram_id, user.telethon_session)
                    if ok:
                        count += 1
                except Exception as e:
                    logger.error(f"فشل استعادة جلسة {user.telegram_id}: {e}")
        logger.info(f"✅ استُعيدت {count} جلسة Telethon")

    async def start(self):
        """تشغيل البوت"""
        logger.info("🤖 البوت يعمل الآن...")
        await self.bot_app.initialize()
        await self.bot_app.start()
        await self.bot_app.updater.start_polling(
            allowed_updates=["message", "callback_query", "chat_member"],
            drop_pending_updates=False,
        )
        self._running = True
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """إيقاف منظم للتطبيق"""
        logger.info("🛑 إيقاف التطبيق...")
        self._running = False

        if self.bot_app:
            try:
                if self.bot_app.updater and self.bot_app.updater.running:
                    await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
            except Exception as e:
                logger.error(f"خطأ أثناء إيقاف البوت: {e}")

        from telethon_client.client import telethon_manager
        await telethon_manager.stop_all()

        from infrastructure.scheduler import task_scheduler
        task_scheduler.stop()

        if self.db:
            await self.db.close()

        logger.info("👋 التطبيق أُوقف")

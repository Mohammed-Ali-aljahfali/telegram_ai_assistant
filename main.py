"""main.py — نقطة دخول المساعد الذكي لـ Telegram"""
import asyncio
import sys
import signal
from pathlib import Path

# إضافة المسار للـ Python path
sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.logger import get_logger
from core.application import TelegramAIApplication

logger = get_logger("main")


async def main():
    app = TelegramAIApplication()
    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("🛑 إشارة إيقاف مستقبَلة...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except (NotImplementedError, OSError):
            # Windows لا يدعم add_signal_handler
            pass

    try:
        await app.initialize()
        logger.info("=" * 50)
        logger.info("🤖 المساعد الذكي لـ Telegram يعمل الآن!")
        logger.info("=" * 50)
        await app.start()
    except KeyboardInterrupt:
        logger.info("⌨️ تم الإيقاف بـ Ctrl+C")
    except Exception as e:
        logger.critical(f"💥 خطأ فادح: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 تم الإيقاف")

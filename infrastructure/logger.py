"""infrastructure/logger.py — نظام التسجيل باستخدام Loguru"""
import sys
from pathlib import Path
from loguru import logger as _logger
from config import config


def setup_logger():
    """إعداد نظام التسجيل"""
    import io
    config.create_directories()
    _logger.remove()

    # إصلاح encoding على Windows
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Console
    _logger.add(
        sys.stdout,
        level=config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        colorize=False,
    )

    # ملف عام
    _logger.add(
        config.LOG_DIR / "app.log",
        level=config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )

    # ملف الأخطاء فقط
    _logger.add(
        config.LOG_DIR / "error.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}\n{exception}",
        rotation="5 MB",
        retention="60 days",
        encoding="utf-8",
    )

    # ملف الذكاء الاصطناعي
    _logger.add(
        config.LOG_DIR / "ai.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
        rotation="5 MB",
        retention="14 days",
        encoding="utf-8",
        filter=lambda r: "ai" in r["name"].lower() or "agent" in r["name"].lower(),
    )


def get_logger(name: str = "app"):
    """الحصول على logger مخصص باسم"""
    return _logger.bind(name=name)


setup_logger()

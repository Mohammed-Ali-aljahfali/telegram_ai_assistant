"""
config.py — إعدادات النظام المركزية
=====================================
جميع مسارات البيانات مستمدة من DATA_DIR الذي يمكن تحديده عبر متغير البيئة.

على Railway:
    DATA_DIR=/data   (Railway Volume مُوصَّل على /data)

محلياً:
    DATA_DIR غير محدد → يستخدم ./data بجانب الكود تلقائياً

هذا الفصل بين الكود والبيانات يضمن عدم فقدان البيانات عند إعادة النشر.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ─── تحميل ملف .env ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

_log = logging.getLogger("config")


def _resolve_data_dir() -> Path:
    """
    تحديد مجلد البيانات الدائم.

    الأولوية:
    1. DATA_DIR من متغير البيئة (مسار مطلق للـ Volume على Railway)
    2. ./data بجانب ملف الكود (للتطوير المحلي)
    """
    raw = os.getenv("DATA_DIR", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else BASE_DIR / p
    # الافتراضي للتطوير المحلي
    return BASE_DIR / "data"


# حساب DATA_DIR مرة واحدة عند تحميل الموديول
_DATA_DIR: Path = _resolve_data_dir()


class Config:
    """إعدادات النظام المركزية."""

    BOT_TOKEN: str     = os.getenv("BOT_TOKEN", "")
    API_ID: int        = int(os.getenv("API_ID", "0"))
    API_HASH: str      = os.getenv("API_HASH", "")
    ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "5372717005"))
    DEVELOPER_ID: int  = int(os.getenv("DEVELOPER_ID", str(ADMIN_CHAT_ID)))

    # ─── التشفير ─────────────────────────────────────────────────────────────
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # ─── مجلد البيانات الدائم ────────────────────────────────────────────────
    # DATA_DIR هو الجذر لكل ملفات البيانات.
    # على Railway يُوصَّل Volume على هذا المسار.
    DATA_DIR: Path = _DATA_DIR

    # ─── مسارات البيانات — جميعها داخل DATA_DIR ─────────────────────────────
    DATABASE_PATH: Path = _DATA_DIR / "database.db"
    BACKUP_DIR: Path    = _DATA_DIR / "backups"
    SESSIONS_DIR: Path  = _DATA_DIR / "sessions"
    LOG_DIR: Path       = _DATA_DIR / "logs"

    # ─── السجلات ─────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ─── الذكاء الاصطناعي ────────────────────────────────────────────────────
    AI_PROVIDER: str    = os.getenv("AI_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    LOCAL_AI_URL: str   = os.getenv("LOCAL_AI_URL", "http://localhost:11434")

    # ─── حدود النظام ─────────────────────────────────────────────────────────
    MAX_CONTEXT_MESSAGES: int = 20
    MAX_RETRIES: int          = 3
    RETRY_DELAY: float        = 1.0
    RATE_LIMIT_MESSAGES: int  = 30   # رسالة في الدقيقة
    RATE_LIMIT_WINDOW: int    = 60   # ثانية

    # ─── الجدولة ─────────────────────────────────────────────────────────────
    BACKUP_HOUR: int  = 3    # 3 صباحاً
    SUMMARY_HOUR: int = 22   # 10 مساءً

    # ─── التحقق ──────────────────────────────────────────────────────────────

    @classmethod
    def validate(cls) -> list[str]:
        """تحقق من الإعدادات الضرورية."""
        errors: list[str] = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN مطلوب")
        if not cls.API_ID:
            errors.append("API_ID مطلوب")
        if not cls.API_HASH:
            errors.append("API_HASH مطلوب")
        if not cls.DEVELOPER_ID:
            errors.append("DEVELOPER_ID مطلوب")
        if not cls.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY مطلوب")
        return errors

    @classmethod
    def create_directories(cls) -> None:
        """إنشاء جميع مجلدات البيانات الضرورية إذا لم تكن موجودة."""
        for directory in [
            cls.DATABASE_PATH.parent,
            cls.BACKUP_DIR,
            cls.SESSIONS_DIR,
            cls.LOG_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def log_storage_paths(cls) -> None:
        """تسجيل مسارات التخزين عند بدء التشغيل للتشخيص."""
        _log.info("=" * 55)
        _log.info("📂 مسارات التخزين الدائم:")
        _log.info("   DATA_DIR    : %s", cls.DATA_DIR)
        _log.info("   DATABASE    : %s", cls.DATABASE_PATH)
        _log.info("   BACKUPS     : %s", cls.BACKUP_DIR)
        _log.info("   SESSIONS    : %s", cls.SESSIONS_DIR)
        _log.info("   LOGS        : %s", cls.LOG_DIR)
        db_exists = cls.DATABASE_PATH.exists()
        _log.info("   DB موجودة   : %s", "✅ نعم" if db_exists else "⚠️ لا (ستُنشأ)")
        _log.info("=" * 55)


config = Config()

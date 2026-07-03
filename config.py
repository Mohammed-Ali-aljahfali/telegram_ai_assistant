"""
config.py — إعدادات النظام المركزية
تحميل وتحقق جميع متغيرات البيئة
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل ملف .env
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """إعدادات النظام المركزية"""

    # ─── Telegram ───────────────────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    DEVELOPER_ID: int = int(os.getenv("DEVELOPER_ID", "0"))

    # ─── التشفير ─────────────────────────────────────────────────
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # ─── قاعدة البيانات ──────────────────────────────────────────
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/database.db")
    BACKUP_DIR: Path = BASE_DIR / "data" / "backups"
    SESSIONS_DIR: Path = BASE_DIR / "data" / "sessions"

    # ─── السجلات ─────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = BASE_DIR / "logs"

    # ─── الذكاء الاصطناعي ────────────────────────────────────────
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    LOCAL_AI_URL: str = os.getenv("LOCAL_AI_URL", "http://localhost:11434")

    # ─── حدود النظام ─────────────────────────────────────────────
    MAX_CONTEXT_MESSAGES: int = 20
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    RATE_LIMIT_MESSAGES: int = 30  # رسالة في الدقيقة
    RATE_LIMIT_WINDOW: int = 60    # ثانية

    # ─── الجدولة ─────────────────────────────────────────────────
    BACKUP_HOUR: int = 3           # 3 صباحاً
    SUMMARY_HOUR: int = 22         # 10 مساءً

    @classmethod
    def validate(cls) -> list[str]:
        """تحقق من الإعدادات الضرورية"""
        errors = []
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
    def create_directories(cls):
        """إنشاء المجلدات الضرورية"""
        for directory in [
            cls.DATABASE_PATH.parent,
            cls.BACKUP_DIR,
            cls.SESSIONS_DIR,
            cls.LOG_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


config = Config()

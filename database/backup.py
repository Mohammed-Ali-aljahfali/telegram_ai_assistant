"""database/backup.py — نظام النسخ الاحتياطي التلقائي"""
import shutil
from datetime import datetime
from pathlib import Path
from config import config
from infrastructure.logger import get_logger

logger = get_logger("backup")


async def backup_database() -> Path:
    """إنشاء نسخة احتياطية"""
    config.create_directories()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config.BACKUP_DIR / f"database_{timestamp}.db"
    shutil.copy2(str(config.DATABASE_PATH), str(backup_path))
    logger.info(f"✅ نسخة احتياطية: {backup_path}")
    await cleanup_old_backups()
    return backup_path


async def cleanup_old_backups(keep_last: int = 7):
    """حذف النسخ الاحتياطية القديمة"""
    backups = sorted(config.BACKUP_DIR.glob("database_*.db"), reverse=True)
    for old_backup in backups[keep_last:]:
        old_backup.unlink()
        logger.info(f"🗑️ حُذفت نسخة قديمة: {old_backup.name}")


async def restore_database(backup_path: str) -> bool:
    """استعادة قاعدة البيانات من نسخة احتياطية"""
    try:
        shutil.copy2(backup_path, str(config.DATABASE_PATH))
        logger.info(f"✅ استُعيدت قاعدة البيانات من: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل الاستعادة: {e}")
        return False

"""database/backup.py — نظام النسخ الاحتياطي التلقائي

يدعم:
    - نسخة احتياطية يدوية أو مجدولة
    - نسخة احتياطية تلقائية قبل Migration
    - تنظيف النسخ القديمة (الاحتفاظ بآخر 7)
    - استعادة من نسخة احتياطية
    - Logging واضح لمكان النسخ
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from config import config
from infrastructure.logger import get_logger

logger = get_logger("backup")


async def backup_database(label: str = "scheduled") -> Path | None:
    """
    إنشاء نسخة احتياطية من قاعدة البيانات.

    Parameters
    ----------
    label:
        وسم للنسخة الاحتياطية يُضاف لاسم الملف (scheduled / manual / pre_migration).

    Returns
    -------
    مسار ملف النسخة الاحتياطية، أو None إذا فشلت العملية.
    """
    db_path = config.DATABASE_PATH

    if not db_path.exists():
        logger.warning(
            "backup_database: قاعدة البيانات غير موجودة في %s — تخطي", db_path
        )
        return None

    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"database_{label}_{timestamp}.db"
    backup_path = config.BACKUP_DIR / backup_name

    try:
        shutil.copy2(str(db_path), str(backup_path))
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(
            "💾 نسخة احتياطية (%s) | الملف: %s | الحجم: %.2f MB | المجلد: %s",
            label, backup_name, size_mb, config.BACKUP_DIR,
        )
        await _cleanup_old_backups()
        return backup_path

    except PermissionError as exc:
        logger.error(
            "❌ لا توجد صلاحية لإنشاء النسخة الاحتياطية في %s: %s",
            config.BACKUP_DIR, exc,
        )
        return None
    except Exception as exc:
        logger.error("❌ فشل إنشاء النسخة الاحتياطية: %s", exc)
        return None


async def _cleanup_old_backups(keep_last: int = 7) -> None:
    """حذف النسخ الاحتياطية القديمة مع الاحتفاظ بآخر `keep_last`."""
    if not config.BACKUP_DIR.exists():
        return

    backups = sorted(
        config.BACKUP_DIR.glob("database_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[keep_last:]:
        try:
            old_backup.unlink()
            logger.info("🗑️  حُذفت نسخة قديمة: %s", old_backup.name)
        except Exception as exc:
            logger.warning("تعذر حذف النسخة القديمة %s: %s", old_backup.name, exc)


async def restore_database(backup_path: str | Path) -> bool:
    """
    استعادة قاعدة البيانات من نسخة احتياطية.

    ينشئ نسخة احتياطية من الحالة الحالية أولاً قبل الاستعادة.
    """
    backup_path = Path(backup_path)
    if not backup_path.exists():
        logger.error("❌ ملف النسخة الاحتياطية غير موجود: %s", backup_path)
        return False

    # نسخة احتياطية من الحالة الحالية قبل الاستعادة
    db_path = config.DATABASE_PATH
    if db_path.exists():
        await backup_database(label="pre_restore")

    try:
        shutil.copy2(str(backup_path), str(db_path))
        logger.info(
            "✅ تم استعادة قاعدة البيانات من: %s → %s",
            backup_path.name, db_path,
        )
        return True
    except Exception as exc:
        logger.error("❌ فشل الاستعادة: %s", exc)
        return False


def list_backups() -> list[dict]:
    """
    قائمة بجميع النسخ الاحتياطية المتاحة.

    Returns
    -------
    قائمة بالقواميس: {name, path, size_mb, created_at}
    """
    if not config.BACKUP_DIR.exists():
        return []

    result = []
    for backup_file in sorted(
        config.BACKUP_DIR.glob("database_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        stat = backup_file.stat()
        result.append({
            "name":       backup_file.name,
            "path":       str(backup_file),
            "size_mb":    round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        })
    return result

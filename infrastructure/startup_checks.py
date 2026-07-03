"""infrastructure/startup_checks.py — فحوصات سلامة النظام عند بدء التشغيل

يتحقق من:
    1. وجود DATA_DIR وصلاحيات القراءة/الكتابة
    2. سلامة قاعدة البيانات إذا كانت موجودة
    3. إنشاء مجلدات البيانات إذا لم تكن موجودة
    4. تسجيل واضح لمكان كل ملف
    5. نسخة احتياطية قبل أي migration

لا يُنشئ قاعدة بيانات جديدة إذا كانت هناك قاعدة موجودة.
يرفع استثناء واضحاً إذا كان DATA_DIR غير قابل للكتابة.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from config import config
from infrastructure.logger import get_logger

logger = get_logger("startup")


# ─── نتيجة الفحص ─────────────────────────────────────────────────────────────

class StartupCheckResult:
    """نتيجة فحوصات بدء التشغيل."""

    def __init__(self) -> None:
        self.ok        = True
        self.warnings: list[str] = []
        self.errors:   list[str] = []
        self.db_exists  = False
        self.db_size_mb = 0.0

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning(f"⚠️  {msg}")

    def add_error(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)
        logger.error(f"❌ {msg}")

    def add_ok(self, msg: str) -> None:
        logger.info(f"✅ {msg}")


# ─── الفحوصات ────────────────────────────────────────────────────────────────

async def run_startup_checks() -> StartupCheckResult:
    """
    تشغيل جميع فحوصات بدء التشغيل.

    يُستدعى مرة واحدة في بداية `TelegramAIApplication.initialize()`.
    يرفع `RuntimeError` إذا كانت هناك أخطاء حرجة تمنع التشغيل.
    """
    result = StartupCheckResult()

    logger.info("=" * 55)
    logger.info("🔍 فحوصات بدء التشغيل...")
    logger.info("=" * 55)

    # ─── 1. تسجيل مسارات التخزين ─────────────────────────────────────────
    _log_storage_paths()

    # ─── 2. فحص DATA_DIR ─────────────────────────────────────────────────
    _check_data_dir(result)
    if not result.ok:
        _raise_if_errors(result)

    # ─── 3. إنشاء المجلدات الضرورية ──────────────────────────────────────
    _create_required_directories(result)

    # ─── 4. فحص قاعدة البيانات ───────────────────────────────────────────
    _check_database(result)

    # ─── 5. فحص مجلد الجلسات ─────────────────────────────────────────────
    _check_sessions_dir(result)

    # ─── 6. ملخص الفحص ───────────────────────────────────────────────────
    _print_summary(result)

    # ─── 7. رفع استثناء إذا كانت هناك أخطاء حرجة ────────────────────────
    _raise_if_errors(result)

    return result


# ─── دوال الفحص الفردية ──────────────────────────────────────────────────────

def _log_storage_paths() -> None:
    """تسجيل مسارات التخزين للتشخيص."""
    logger.info("=" * 55)
    logger.info("📂 مسارات التخزين الدائم:")
    logger.info(f"   DATA_DIR    : {config.DATA_DIR}")
    logger.info(f"   DATABASE    : {config.DATABASE_PATH}")
    logger.info(f"   BACKUPS     : {config.BACKUP_DIR}")
    logger.info(f"   SESSIONS    : {config.SESSIONS_DIR}")
    logger.info(f"   LOGS        : {config.LOG_DIR}")
    db_exists = config.DATABASE_PATH.exists()
    logger.info(f"   DB موجودة   : {'✅ نعم' if db_exists else '⚠️ لا (ستُنشأ)'}")
    logger.info("=" * 55)


def _check_data_dir(result: StartupCheckResult) -> None:
    """التحقق من وجود DATA_DIR وصلاحيات القراءة والكتابة."""
    data_dir = config.DATA_DIR
    logger.info(f"📂 فحص DATA_DIR: {data_dir}")

    # إنشاء المجلد إذا لم يكن موجوداً
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        result.add_error(
            f"DATA_DIR غير قابل للإنشاء: {data_dir} — {exc}\n"
            "على Railway: تأكد من إنشاء Volume وضبط DATA_DIR=/data"
        )
        return
    except OSError as exc:
        result.add_error(f"خطأ في إنشاء DATA_DIR: {data_dir} — {exc}")
        return

    # فحص الصلاحيات
    readable = os.access(data_dir, os.R_OK)
    writable = os.access(data_dir, os.W_OK)

    if not readable:
        result.add_error(f"DATA_DIR غير قابل للقراءة: {data_dir}")
    if not writable:
        result.add_error(
            f"DATA_DIR غير قابل للكتابة: {data_dir}\n"
            "على Railway: تأكد من تفعيل Volume وأن Mount Path = /data"
        )

    if readable and writable:
        result.add_ok(f"DATA_DIR جاهز للقراءة والكتابة: {data_dir}")

    # اختبار فعلي بكتابة ملف مؤقت
    test_file = data_dir / ".write_test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
        result.add_ok("اختبار الكتابة في DATA_DIR نجح")
    except Exception as exc:
        result.add_error(f"فشل اختبار الكتابة في DATA_DIR: {exc}")


def _create_required_directories(result: StartupCheckResult) -> None:
    """إنشاء جميع مجلدات البيانات الضرورية."""
    dirs = {
        "database":  config.DATABASE_PATH.parent,
        "backups":   config.BACKUP_DIR,
        "sessions":  config.SESSIONS_DIR,
        "logs":      config.LOG_DIR,
    }
    for name, directory in dirs.items():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"📁 {name}: {directory}")
        except Exception as exc:
            result.add_error(f"فشل إنشاء مجلد {name}: {directory} — {exc}")


def _check_database(result: StartupCheckResult) -> None:
    """
    فحص قاعدة البيانات.

    - إذا كانت موجودة: يتحقق من سلامتها ويسجل حجمها.
    - إذا لم تكن موجودة: يُسجِّل تحذيراً (ستُنشأ عند أول تشغيل).
    - لا يُنشئ قاعدة جديدة هنا — هذا مسؤولية DatabaseManager.
    """
    db_path = config.DATABASE_PATH

    if not db_path.exists():
        result.add_warning(
            f"قاعدة البيانات غير موجودة: {db_path}\n"
            "   سيتم إنشاؤها تلقائياً عند أول تشغيل."
        )
        return

    # قاعدة البيانات موجودة — تحقق من سلامتها
    result.db_exists = True
    size_bytes = db_path.stat().st_size
    result.db_size_mb = size_bytes / (1024 * 1024)

    result.add_ok(
        f"قاعدة البيانات موجودة ({result.db_size_mb:.2f} MB): {db_path}"
    )

    # فحص سلامة SQLite
    try:
        with sqlite3.connect(str(db_path), timeout=5) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if integrity and integrity[0] == "ok":
                result.add_ok("سلامة قاعدة البيانات: ✅ جيدة")
            else:
                result.add_error(
                    f"قاعدة البيانات تالفة: {integrity}\n"
                    f"   مسار الملف: {db_path}"
                )
    except sqlite3.DatabaseError as exc:
        result.add_error(
            f"قاعدة البيانات غير قابلة للفتح: {exc}\n"
            f"   مسار الملف: {db_path}"
        )


def _check_sessions_dir(result: StartupCheckResult) -> None:
    """فحص مجلد الجلسات."""
    sessions_dir = config.SESSIONS_DIR
    if not sessions_dir.exists():
        return

    session_files = list(sessions_dir.glob("*.session"))
    if session_files:
        result.add_ok(f"مجلد الجلسات: {len(session_files)} ملف جلسة موجود")
    else:
        logger.info("📂 مجلد الجلسات: لا توجد ملفات جلسة محلية (الجلسات محفوظة في DB)")


def _print_summary(result: StartupCheckResult) -> None:
    """طباعة ملخص نتائج الفحص."""
    logger.info("=" * 55)
    logger.info("📋 ملخص فحوصات بدء التشغيل:")
    logger.info(f"   الحالة  : {'✅ جاهز' if result.ok else '❌ يوجد أخطاء'}")
    logger.info(f"   تحذيرات : {len(result.warnings)}")
    logger.info(f"   أخطاء   : {len(result.errors)}")
    if result.db_exists:
        logger.info(f"   DB      : موجودة ({result.db_size_mb:.2f} MB)")
    else:
        logger.info("   DB      : ستُنشأ")
    logger.info("=" * 55)


def _raise_if_errors(result: StartupCheckResult) -> None:
    """رفع استثناء إذا كانت هناك أخطاء حرجة."""
    if not result.ok:
        error_msg = "\n".join(result.errors)
        raise RuntimeError(
            f"فشلت فحوصات بدء التشغيل:\n{error_msg}\n\n"
            "على Railway:\n"
            "  1. أنشئ Volume من Dashboard\n"
            "  2. اضبط Mount Path = /data\n"
            "  3. أضف DATA_DIR=/data في Environment Variables"
        )


# ─── نسخة احتياطية قبل Migration ─────────────────────────────────────────────

async def backup_before_migration() -> Path | None:
    """
    إنشاء نسخة احتياطية من قاعدة البيانات قبل تطبيق Migration.

    يُستدعى من `database/migrations.py` قبل كل migration جديد.
    لا يفعل شيئاً إذا لم تكن قاعدة البيانات موجودة بعد.
    """
    db_path = config.DATABASE_PATH
    if not db_path.exists():
        logger.debug("backup_before_migration: قاعدة البيانات غير موجودة — تخطي")
        return None

    import shutil
    from datetime import datetime

    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config.BACKUP_DIR / f"pre_migration_{timestamp}.db"

    try:
        shutil.copy2(str(db_path), str(backup_path))
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        logger.info(
            f"💾 نسخة احتياطية قبل Migration: {backup_path.name} ({size_mb:.2f} MB)"
        )
        return backup_path
    except Exception as exc:
        logger.error(f"❌ فشل إنشاء نسخة احتياطية قبل Migration: {exc}")
        return None

"""database/repositories/login_session_repository.py
Login Session Repository
========================
يُدير حالات تسجيل الدخول الجارية في قاعدة البيانات.
يضمن استمرارية العملية حتى بعد إعادة تشغيل البرنامج.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from database.connection import get_db

logger = logging.getLogger("auth.login_session_repo")

# صلاحية رمز التحقق الافتراضية بالثواني (Telegram يمنح ~5 دقائق)
CODE_EXPIRY_SECONDS = 300


class LoginSessionRepository:
    """Repository لجلسات تسجيل الدخول الجارية."""

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def upsert(
        self,
        bot_user_id: int,
        phone: str,
        phone_code_hash: str,
        session_string: str = "",
        login_state: str = "WAIT_CODE",
        resend_count: int = 0,
    ) -> None:
        """حفظ أو تحديث جلسة تسجيل الدخول الجارية."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=CODE_EXPIRY_SECONDS)
        ).isoformat()

        await db.execute(
            """
            INSERT INTO login_sessions
                (bot_user_id, phone, phone_code_hash, session_string,
                 login_state, code_sent_at, expires_at, resend_count,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bot_user_id) DO UPDATE SET
                phone           = excluded.phone,
                phone_code_hash = excluded.phone_code_hash,
                session_string  = excluded.session_string,
                login_state     = excluded.login_state,
                code_sent_at    = excluded.code_sent_at,
                expires_at      = excluded.expires_at,
                resend_count    = excluded.resend_count,
                attempt_count   = 0,
                last_error      = NULL,
                updated_at      = excluded.updated_at
            """,
            (
                bot_user_id, phone, phone_code_hash, session_string,
                login_state, now, expires_at, resend_count,
                now, now,
            ),
        )
        logger.info(
            "login_session upserted | user=%s state=%s resend_count=%s",
            bot_user_id, login_state, resend_count,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, bot_user_id: int) -> Optional[dict]:
        """استرجاع جلسة تسجيل الدخول الجارية أو None."""
        db = get_db()
        row = await db.fetchone(
            "SELECT * FROM login_sessions WHERE bot_user_id = ?",
            (bot_user_id,),
        )
        if row is None:
            return None
        return dict(row)

    async def is_expired(self, bot_user_id: int) -> bool:
        """هل انتهت صلاحية رمز التحقق الحالي؟"""
        session = await self.get(bot_user_id)
        if not session or not session.get("expires_at"):
            return True
        try:
            expires_at = datetime.fromisoformat(session["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > expires_at
        except (ValueError, TypeError):
            return True

    # ------------------------------------------------------------------
    # State Updates
    # ------------------------------------------------------------------

    async def update_state(
        self,
        bot_user_id: int,
        login_state: str,
        last_error: Optional[str] = None,
    ) -> None:
        """تحديث حالة عملية تسجيل الدخول."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            UPDATE login_sessions
            SET login_state = ?, last_error = ?, updated_at = ?
            WHERE bot_user_id = ?
            """,
            (login_state, last_error, now, bot_user_id),
        )
        logger.info(
            "login_session state → %s | user=%s error=%s",
            login_state, bot_user_id, last_error,
        )

    async def update_code_hash(
        self,
        bot_user_id: int,
        new_phone_code_hash: str,
        resend_count: int,
    ) -> None:
        """تحديث phone_code_hash وإعادة ضبط مؤشر انتهاء الصلاحية عند إعادة إرسال الرمز."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=CODE_EXPIRY_SECONDS)
        ).isoformat()
        await db.execute(
            """
            UPDATE login_sessions
            SET phone_code_hash = ?, code_sent_at = ?, expires_at = ?,
                resend_count = ?, attempt_count = 0, last_error = NULL,
                login_state = 'WAIT_CODE', updated_at = ?
            WHERE bot_user_id = ?
            """,
            (new_phone_code_hash, now, expires_at, resend_count, now, bot_user_id),
        )
        logger.info(
            "login_session code_hash refreshed | user=%s resend_count=%s",
            bot_user_id, resend_count,
        )

    async def increment_attempt(self, bot_user_id: int) -> int:
        """زيادة عداد محاولات إدخال الرمز. يُرجع العداد الجديد."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            UPDATE login_sessions
            SET attempt_count = attempt_count + 1, updated_at = ?
            WHERE bot_user_id = ?
            """,
            (now, bot_user_id),
        )
        row = await db.fetchone(
            "SELECT attempt_count FROM login_sessions WHERE bot_user_id = ?",
            (bot_user_id,),
        )
        return row["attempt_count"] if row else 0

    async def set_session_string(
        self, bot_user_id: int, session_string: str
    ) -> None:
        """حفظ StringSession الجزئي (للاستعادة في حالة 2FA)."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE login_sessions SET session_string = ?, updated_at = ? WHERE bot_user_id = ?",
            (session_string, now, bot_user_id),
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, bot_user_id: int) -> None:
        """حذف جلسة تسجيل الدخول بعد الاكتمال أو الإلغاء."""
        db = get_db()
        await db.execute(
            "DELETE FROM login_sessions WHERE bot_user_id = ?",
            (bot_user_id,),
        )
        logger.info("login_session deleted | user=%s", bot_user_id)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def cleanup_expired(self) -> int:
        """حذف الجلسات المنتهية الصلاحية. يُرجع عدد السجلات المحذوفة."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        # نحتفظ بها لمدة ساعة إضافية للتشخيص
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        await db.execute(
            "DELETE FROM login_sessions WHERE expires_at < ?",
            (cutoff,),
        )
        logger.debug("login_sessions cleanup done | cutoff=%s", cutoff)
        return 0

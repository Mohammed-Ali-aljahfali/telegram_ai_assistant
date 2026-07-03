"""telethon_client/auth_handler.py — معالج المصادقة (Login State Machine)

نظرة عامة
----------
يُدير هذا الملف عملية تسجيل الدخول عبر Telethon بشكل كامل، بما يشمل:

    1. State Machine واضحة للانتقال بين مراحل تسجيل الدخول.
    2. حفظ الحالة في SQLite لضمان الاستمرارية عند إعادة التشغيل.
    3. إعادة إرسال رمز التحقق وتحديث phone_code_hash تلقائياً.
    4. معالجة كاملة لجميع أخطاء Telethon الشائعة.
    5. دعم التحقق بخطوتين (2FA) تلقائياً.
    6. Retry تلقائي على أخطاء الشبكة.
    7. Logging احترافي بدون تسجيل بيانات حساسة.

حالات State Machine
-------------------
    WAIT_PHONE  → المستخدم لم يُدخل رقم الهاتف بعد
    CODE_SENT   → تم إرسال الرمز، ننتظر إدخاله
    WAIT_CODE   → ننتظر إدخال رمز التحقق
    WAIT_2FA    → الحساب محمي بـ 2FA، ننتظر كلمة المرور
    COMPLETED   → تسجيل الدخول اكتمل بنجاح
    FAILED      → فشل نهائي يتطلب البدء من جديد
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthRestartError,
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeEmptyError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    RpcCallFailError,
    SessionPasswordNeededError,
)

from config import config
from database.repositories.login_session_repository import LoginSessionRepository
from infrastructure.logger import get_logger

logger = get_logger("telethon.auth")

# الحد الأقصى لمحاولات إعادة الإرسال قبل رفض العملية
MAX_RESEND_ATTEMPTS = 3
# الحد الأقصى لمحاولات إدخال الرمز الخاطئ
MAX_CODE_ATTEMPTS = 5
# الحد الأقصى لمحاولات Retry عند أخطاء الشبكة
MAX_NETWORK_RETRIES = 3
# وقت الانتظار الأولي بين محاولات Retry (ثواني)
RETRY_BASE_DELAY = 1.5


# ---------------------------------------------------------------------------
# Login State Enum
# ---------------------------------------------------------------------------


class LoginState(str, Enum):
    """حالات عملية تسجيل الدخول."""
    WAIT_PHONE = "WAIT_PHONE"
    CODE_SENT  = "CODE_SENT"
    WAIT_CODE  = "WAIT_CODE"
    WAIT_2FA   = "WAIT_2FA"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"


# ---------------------------------------------------------------------------
# نتائج العمليات (Result Objects)
# ---------------------------------------------------------------------------


class AuthResult:
    """نتيجة أي عملية مصادقة."""

    __slots__ = ("success", "state", "message", "extra")

    def __init__(
        self,
        success: bool,
        state: LoginState,
        message: str,
        extra: Optional[dict] = None,
    ) -> None:
        self.success = success
        self.state   = state
        self.message = message
        self.extra   = extra or {}

    def __repr__(self) -> str:
        return (
            f"AuthResult(success={self.success}, state={self.state.value}, "
            f"message={self.message!r})"
        )


# ---------------------------------------------------------------------------
# TelethonAuthHandler
# ---------------------------------------------------------------------------


class TelethonAuthHandler:
    """
    مُعالج المصادقة الرئيسي.

    يُخزِّن عملاء Telethon المؤقتة (أثناء التسجيل) في الذاكرة،
    وحالة التسجيل بالكامل في SQLite.
    """

    def __init__(self) -> None:
        # عملاء Telethon المؤقتة أثناء عملية التسجيل
        self._temp_clients: dict[int, TelegramClient] = {}
        # Repository الخاص بجلسات تسجيل الدخول
        self._repo = LoginSessionRepository()

    # ------------------------------------------------------------------
    # الخطوة 1 — إرسال رمز التحقق
    # ------------------------------------------------------------------

    async def send_code(
        self, bot_user_id: int, phone: str
    ) -> AuthResult:
        """
        إرسال رمز التحقق للمستخدم.

        يُنشئ TelegramClient مؤقتاً، يُرسل الرمز، ويُحفظ الحالة
        في قاعدة البيانات.

        المُعاد: AuthResult
            success=True  → تم الإرسال، state=WAIT_CODE
            success=False → فشل الإرسال مع سبب واضح
        """
        logger.info("send_code | user=%s phone=+%s****", bot_user_id, phone[:3])
        start_ts = time.monotonic()

        # إغلاق أي عميل مؤقت سابق إذا وُجد
        await self._cleanup_temp_client(bot_user_id)

        client = TelegramClient(
            StringSession(), config.API_ID, config.API_HASH
        )

        for attempt in range(1, MAX_NETWORK_RETRIES + 1):
            try:
                await client.connect()
                result = await client.send_code_request(phone)
                break  # نجح

            except PhoneNumberInvalidError:
                await self._safe_disconnect(client)
                logger.warning("send_code | invalid phone | user=%s", bot_user_id)
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_PHONE,
                    message=(
                        "❌ رقم الجوال غير صحيح.\n"
                        "تأكد من تضمين رمز الدولة، مثال: `+966501234567`"
                    ),
                )

            except PhoneNumberBannedError:
                await self._safe_disconnect(client)
                logger.warning("send_code | phone banned | user=%s", bot_user_id)
                return AuthResult(
                    success=False,
                    state=LoginState.FAILED,
                    message=(
                        "🚫 هذا الرقم محظور من Telegram.\n"
                        "لا يمكن المتابعة بهذا الحساب."
                    ),
                )

            except FloodWaitError as exc:
                await self._safe_disconnect(client)
                logger.warning(
                    "send_code | flood wait %ss | user=%s", exc.seconds, bot_user_id
                )
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_PHONE,
                    message=(
                        f"⏳ طلبات كثيرة جداً.\n"
                        f"انتظر **{exc.seconds}** ثانية ثم حاول مجدداً."
                    ),
                    extra={"wait_seconds": exc.seconds},
                )

            except AuthRestartError:
                logger.warning(
                    "send_code | AuthRestartError attempt %s | user=%s",
                    attempt, bot_user_id,
                )
                if attempt < MAX_NETWORK_RETRIES:
                    await asyncio.sleep(RETRY_BASE_DELAY * attempt)
                    continue
                await self._safe_disconnect(client)
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_PHONE,
                    message="❌ خطأ في الاتصال بـ Telegram. حاول مجدداً.",
                )

            except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
                logger.warning(
                    "send_code | network error attempt %s/%s: %s | user=%s",
                    attempt, MAX_NETWORK_RETRIES, exc, bot_user_id,
                )
                if attempt < MAX_NETWORK_RETRIES:
                    await asyncio.sleep(RETRY_BASE_DELAY * attempt)
                    continue
                await self._safe_disconnect(client)
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_PHONE,
                    message=(
                        "❌ تعذر الاتصال بـ Telegram.\n"
                        "تحقق من اتصالك بالإنترنت وحاول مجدداً."
                    ),
                )

            except RpcCallFailError as exc:
                logger.error("send_code | RpcCallFail: %s | user=%s", exc, bot_user_id)
                await self._safe_disconnect(client)
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_PHONE,
                    message="❌ خطأ من خوادم Telegram. حاول بعد لحظات.",
                )

            except Exception as exc:  # noqa: BLE001
                logger.exception("send_code | unexpected error | user=%s", bot_user_id)
                await self._safe_disconnect(client)
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_PHONE,
                    message=f"❌ خطأ غير متوقع: {type(exc).__name__}",
                )

        # حفظ الحالة في قاعدة البيانات
        session_snapshot = client.session.save()
        await self._repo.upsert(
            bot_user_id=bot_user_id,
            phone=phone,
            phone_code_hash=result.phone_code_hash,
            session_string=session_snapshot,
            login_state=LoginState.WAIT_CODE.value,
        )

        # حفظ العميل في الذاكرة
        self._temp_clients[bot_user_id] = client

        elapsed = time.monotonic() - start_ts
        logger.info(
            "send_code | success | user=%s elapsed=%.2fs", bot_user_id, elapsed
        )
        return AuthResult(
            success=True,
            state=LoginState.WAIT_CODE,
            message="✅ تم إرسال رمز التحقق.",
        )

    # ------------------------------------------------------------------
    # الخطوة 1-b — إعادة إرسال رمز التحقق
    # ------------------------------------------------------------------

    async def resend_code(self, bot_user_id: int) -> AuthResult:
        """
        طلب رمز تحقق جديد وتحديث phone_code_hash.

        يُعلم المستخدم أن الرمز القديم لم يعد صالحاً.
        """
        logger.info("resend_code | user=%s", bot_user_id)

        db_session = await self._repo.get(bot_user_id)
        if not db_session:
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message="❌ لا توجد جلسة تسجيل دخول نشطة. أعد البدء من جديد.",
            )

        resend_count = db_session.get("resend_count", 0) + 1
        if resend_count > MAX_RESEND_ATTEMPTS:
            await self._repo.delete(bot_user_id)
            await self._cleanup_temp_client(bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.FAILED,
                message=(
                    "❌ تجاوزت الحد الأقصى لإعادة إرسال الرمز.\n"
                    "ابدأ عملية تسجيل الدخول من جديد."
                ),
            )

        # استعادة العميل من الذاكرة أو إعادة إنشائه من DB
        client = await self._get_or_restore_client(bot_user_id, db_session)
        if client is None:
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message="❌ انتهت جلسة الاتصال. أدخل رقم الهاتف مجدداً.",
            )

        phone = db_session["phone"]

        for attempt in range(1, MAX_NETWORK_RETRIES + 1):
            try:
                result = await client.send_code_request(phone)
                break
            except FloodWaitError as exc:
                logger.warning(
                    "resend_code | flood wait %ss | user=%s", exc.seconds, bot_user_id
                )
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_CODE,
                    message=(
                        f"⏳ انتظر **{exc.seconds}** ثانية قبل إعادة الإرسال."
                    ),
                    extra={"wait_seconds": exc.seconds},
                )
            except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
                logger.warning(
                    "resend_code | network error attempt %s: %s | user=%s",
                    attempt, exc, bot_user_id,
                )
                if attempt < MAX_NETWORK_RETRIES:
                    await asyncio.sleep(RETRY_BASE_DELAY * attempt)
                    continue
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_CODE,
                    message=(
                        "❌ تعذر إعادة الإرسال بسبب مشكلة في الشبكة.\n"
                        "حاول مجدداً بعد لحظات."
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("resend_code | unexpected error | user=%s", bot_user_id)
                return AuthResult(
                    success=False,
                    state=LoginState.WAIT_CODE,
                    message=f"❌ خطأ غير متوقع: {type(exc).__name__}",
                )

        # تحديث phone_code_hash في قاعدة البيانات
        await self._repo.update_code_hash(
            bot_user_id=bot_user_id,
            new_phone_code_hash=result.phone_code_hash,
            resend_count=resend_count,
        )

        logger.info(
            "resend_code | success | user=%s resend_count=%s", bot_user_id, resend_count
        )
        return AuthResult(
            success=True,
            state=LoginState.WAIT_CODE,
            message=(
                "🔄 تم إرسال رمز تحقق جديد.\n"
                "⚠️ الرمز السابق لم يعد صالحاً."
            ),
        )

    # ------------------------------------------------------------------
    # الخطوة 2 — التحقق من الرمز
    # ------------------------------------------------------------------

    async def verify_code(
        self, bot_user_id: int, code: str
    ) -> AuthResult:
        """
        التحقق من رمز SMS/Telegram.

        المُعاد: AuthResult
            success=True, state=COMPLETED → session موجود في extra["session"]
            success=True, state=WAIT_2FA  → يحتاج كلمة مرور 2FA
            success=False                 → فشل مع سبب + الحالة المناسبة
        """
        logger.info("verify_code | user=%s code_len=%s", bot_user_id, len(code))

        db_session = await self._repo.get(bot_user_id)
        if not db_session:
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message=(
                    "❌ انتهت جلسة تسجيل الدخول.\n"
                    "أدخل رقم الهاتف مجدداً للبدء."
                ),
            )

        # التحقق من انتهاء الصلاحية قبل الإرسال
        if await self._repo.is_expired(bot_user_id):
            await self._repo.update_state(
                bot_user_id, LoginState.WAIT_CODE.value,
                last_error="code_expired_before_attempt"
            )
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message=(
                    "⏰ انتهت صلاحية رمز التحقق.\n"
                    "اضغط 🔄 **إعادة إرسال الرمز** للحصول على رمز جديد."
                ),
            )

        # زيادة عداد المحاولات
        attempts = await self._repo.increment_attempt(bot_user_id)
        if attempts > MAX_CODE_ATTEMPTS:
            await self._repo.delete(bot_user_id)
            await self._cleanup_temp_client(bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.FAILED,
                message=(
                    "🚫 تجاوزت الحد الأقصى لمحاولات إدخال الرمز.\n"
                    "ابدأ عملية تسجيل الدخول من جديد."
                ),
            )

        client = await self._get_or_restore_client(bot_user_id, db_session)
        if client is None:
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message="❌ انتهت جلسة الاتصال. أدخل رقم الهاتف مجدداً.",
            )

        phone          = db_session["phone"]
        code_hash      = db_session["phone_code_hash"]

        try:
            await client.sign_in(phone, code, phone_code_hash=code_hash)

        except PhoneCodeEmptyError:
            logger.warning("verify_code | empty code | user=%s", bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message="❌ لم تُدخل رمز التحقق. أرسل الرمز المكون من 5 أرقام.",
            )

        except PhoneCodeInvalidError:
            logger.warning(
                "verify_code | invalid code attempt=%s | user=%s", attempts, bot_user_id
            )
            remaining = MAX_CODE_ATTEMPTS - attempts
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message=(
                    f"❌ الرمز غير صحيح. تبقى لك {remaining} محاولة.\n"
                    "تأكد من إدخال الرمز كاملاً دون مسافات."
                ),
            )

        except PhoneCodeExpiredError:
            logger.warning("verify_code | code expired | user=%s", bot_user_id)
            await self._repo.update_state(
                bot_user_id, LoginState.WAIT_CODE.value,
                last_error="PhoneCodeExpiredError"
            )
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message=(
                    "⏰ انتهت صلاحية رمز التحقق.\n"
                    "اضغط 🔄 **إعادة إرسال الرمز** للحصول على رمز جديد."
                ),
            )

        except SessionPasswordNeededError:
            # الحساب محمي بـ 2FA — احفظ حالة العميل وانتقل
            logger.info("verify_code | 2FA required | user=%s", bot_user_id)
            session_snapshot = client.session.save()
            await self._repo.set_session_string(bot_user_id, session_snapshot)
            await self._repo.update_state(bot_user_id, LoginState.WAIT_2FA.value)
            return AuthResult(
                success=True,
                state=LoginState.WAIT_2FA,
                message=(
                    "🔒 حسابك محمي بالتحقق بخطوتين.\n"
                    "أدخل كلمة مرور 2FA:"
                ),
            )

        except FloodWaitError as exc:
            logger.warning(
                "verify_code | flood wait %ss | user=%s", exc.seconds, bot_user_id
            )
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message=f"⏳ انتظر **{exc.seconds}** ثانية ثم حاول مجدداً.",
                extra={"wait_seconds": exc.seconds},
            )

        except AuthRestartError:
            logger.warning("verify_code | AuthRestartError | user=%s", bot_user_id)
            await self._repo.update_state(
                bot_user_id, LoginState.WAIT_PHONE.value,
                last_error="AuthRestartError"
            )
            await self._cleanup_temp_client(bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message=(
                    "❌ انتهت جلسة المصادقة بسبب خطأ داخلي في Telegram.\n"
                    "أدخل رقم الهاتف مجدداً."
                ),
            )

        except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
            logger.warning("verify_code | network error: %s | user=%s", exc, bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message=(
                    "❌ تعذر الاتصال بـ Telegram.\n"
                    "تحقق من اتصالك بالإنترنت وأعد المحاولة."
                ),
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("verify_code | unexpected error | user=%s", bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_CODE,
                message=f"❌ خطأ غير متوقع: {type(exc).__name__}",
            )

        # ✅ تسجيل الدخول ناجح
        session = client.session.save()
        await self._safe_disconnect(client)
        self._temp_clients.pop(bot_user_id, None)
        await self._repo.delete(bot_user_id)

        logger.info("verify_code | LOGIN_SUCCESS | user=%s", bot_user_id)
        return AuthResult(
            success=True,
            state=LoginState.COMPLETED,
            message="✅ تم تسجيل الدخول بنجاح!",
            extra={"session": session},
        )

    # ------------------------------------------------------------------
    # الخطوة 3 — التحقق من 2FA
    # ------------------------------------------------------------------

    async def verify_2fa(
        self, bot_user_id: int, password: str
    ) -> AuthResult:
        """
        التحقق من كلمة مرور التحقق بخطوتين.

        لا تُسجَّل كلمة المرور في أي مكان.
        """
        logger.info("verify_2fa | user=%s", bot_user_id)

        db_session = await self._repo.get(bot_user_id)
        if not db_session:
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message="❌ انتهت جلسة تسجيل الدخول. ابدأ من جديد.",
            )

        client = await self._get_or_restore_client(bot_user_id, db_session)
        if client is None:
            return AuthResult(
                success=False,
                state=LoginState.WAIT_PHONE,
                message="❌ انتهت جلسة الاتصال. أدخل رقم الهاتف مجدداً.",
            )

        try:
            await client.sign_in(password=password)

        except PasswordHashInvalidError:
            logger.warning("verify_2fa | wrong password | user=%s", bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_2FA,
                message=(
                    "❌ كلمة مرور 2FA غير صحيحة.\n"
                    "أعد المحاولة أو تحقق من التلميح في إعدادات Telegram."
                ),
            )

        except FloodWaitError as exc:
            logger.warning(
                "verify_2fa | flood wait %ss | user=%s", exc.seconds, bot_user_id
            )
            return AuthResult(
                success=False,
                state=LoginState.WAIT_2FA,
                message=f"⏳ انتظر **{exc.seconds}** ثانية ثم حاول مجدداً.",
                extra={"wait_seconds": exc.seconds},
            )

        except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
            logger.warning("verify_2fa | network error: %s | user=%s", exc, bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_2FA,
                message=(
                    "❌ تعذر الاتصال. تحقق من الإنترنت وأعد المحاولة."
                ),
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("verify_2fa | unexpected error | user=%s", bot_user_id)
            return AuthResult(
                success=False,
                state=LoginState.WAIT_2FA,
                message=f"❌ خطأ غير متوقع: {type(exc).__name__}",
            )

        # ✅ نجاح 2FA
        session = client.session.save()
        await self._safe_disconnect(client)
        self._temp_clients.pop(bot_user_id, None)
        await self._repo.delete(bot_user_id)

        logger.info("verify_2fa | 2FA_SUCCESS | user=%s", bot_user_id)
        return AuthResult(
            success=True,
            state=LoginState.COMPLETED,
            message="✅ تم تسجيل الدخول بنجاح!",
            extra={"session": session},
        )

    # ------------------------------------------------------------------
    # تسجيل الخروج
    # ------------------------------------------------------------------

    async def logout(self, bot_user_id: int, encrypted_session: str) -> bool:
        """تسجيل الخروج وحذف الجلسة."""
        from infrastructure.crypto import decrypt_text
        try:
            session_str = decrypt_text(encrypted_session)
            client = TelegramClient(
                StringSession(session_str), config.API_ID, config.API_HASH
            )
            await client.connect()
            await client.log_out()
            logger.info("logout | success | user=%s", bot_user_id)
            return True
        except Exception as exc:
            logger.error("logout | error: %s | user=%s", exc, bot_user_id)
            return False

    # ------------------------------------------------------------------
    # معلومات الحساب
    # ------------------------------------------------------------------

    async def get_account_info(self, session_string: str) -> Optional[dict]:
        """جلب معلومات الحساب من Telegram."""
        from infrastructure.crypto import decrypt_text
        try:
            decrypted = decrypt_text(session_string)
            client = TelegramClient(
                StringSession(decrypted), config.API_ID, config.API_HASH
            )
            await client.connect()
            me = await client.get_me()
            has_2fa = False
            try:
                from telethon.tl.functions.account import GetPasswordRequest
                pwd = await client(GetPasswordRequest())
                has_2fa = pwd.has_password
            except Exception:
                pass
            await client.disconnect()
            return {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
                "has_2fa": has_2fa,
            }
        except Exception as exc:
            logger.error("get_account_info | error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # إلغاء عملية التسجيل
    # ------------------------------------------------------------------

    async def cancel_auth(self, bot_user_id: int) -> None:
        """إلغاء عملية تسجيل الدخول الجارية وتنظيف الموارد."""
        await self._cleanup_temp_client(bot_user_id)
        await self._repo.delete(bot_user_id)
        logger.info("cancel_auth | user=%s", bot_user_id)

    # ------------------------------------------------------------------
    # استعادة الحالة عند إعادة التشغيل
    # ------------------------------------------------------------------

    async def get_pending_state(
        self, bot_user_id: int
    ) -> Optional[LoginState]:
        """
        استعادة حالة تسجيل الدخول من قاعدة البيانات.

        يُستخدم عند إعادة تشغيل البرنامج للاستئناف من حيث توقف.
        يُرجع None إذا لا توجد جلسة تسجيل دخول جارية.
        """
        db_session = await self._repo.get(bot_user_id)
        if not db_session:
            return None
        try:
            return LoginState(db_session["login_state"])
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # دوال مساعدة داخلية
    # ------------------------------------------------------------------

    async def _get_or_restore_client(
        self, bot_user_id: int, db_session: dict
    ) -> Optional[TelegramClient]:
        """
        استعادة عميل Telethon من الذاكرة أو إعادة إنشائه من DB.
        """
        # 1. محاولة استخدام العميل الموجود في الذاكرة
        client = self._temp_clients.get(bot_user_id)
        if client and client.is_connected():
            logger.debug("_get_or_restore_client | using in-memory client | user=%s", bot_user_id)
            return client

        # 2. إعادة إنشاء العميل من StringSession المحفوظ في DB
        session_string = db_session.get("session_string", "")
        if not session_string:
            logger.warning(
                "_get_or_restore_client | no session_string in DB | user=%s", bot_user_id
            )
            return None

        logger.info(
            "_get_or_restore_client | restoring from DB | user=%s", bot_user_id
        )
        client = TelegramClient(
            StringSession(session_string), config.API_ID, config.API_HASH
        )
        for attempt in range(1, MAX_NETWORK_RETRIES + 1):
            try:
                await client.connect()
                self._temp_clients[bot_user_id] = client
                return client
            except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
                logger.warning(
                    "_get_or_restore_client | connect attempt %s failed: %s | user=%s",
                    attempt, exc, bot_user_id,
                )
                if attempt < MAX_NETWORK_RETRIES:
                    await asyncio.sleep(RETRY_BASE_DELAY * attempt)
                else:
                    return None
            except Exception as exc:
                logger.exception(
                    "_get_or_restore_client | unexpected error | user=%s", bot_user_id
                )
                return None

    async def _cleanup_temp_client(self, bot_user_id: int) -> None:
        """إغلاق العميل المؤقت وإزالته من الذاكرة."""
        client = self._temp_clients.pop(bot_user_id, None)
        if client:
            await self._safe_disconnect(client)

    @staticmethod
    async def _safe_disconnect(client: TelegramClient) -> None:
        """قطع الاتصال بأمان بدون رفع استثناء."""
        try:
            await client.disconnect()
        except Exception:
            pass

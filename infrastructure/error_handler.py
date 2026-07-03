"""infrastructure/error_handler.py — معالجة الأخطاء المركزية"""
import functools
import traceback
from typing import Callable, Type
from infrastructure.logger import get_logger

logger = get_logger("error_handler")


# ─── استثناءات مخصصة ────────────────────────────────────────────────────────

class TelegramAIError(Exception):
    """الاستثناء الأساسي للنظام"""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(message)
        self.user_message = user_message or "حدث خطأ في النظام. يرجى المحاولة لاحقاً."


class DatabaseError(TelegramAIError):
    """خطأ في قاعدة البيانات"""
    def __init__(self, message: str):
        super().__init__(message, "خطأ في قاعدة البيانات.")


class AIError(TelegramAIError):
    """خطأ في الذكاء الاصطناعي"""
    def __init__(self, message: str):
        super().__init__(message, "تعذر الاتصال بالذكاء الاصطناعي. تحقق من مفتاح API.")


class AuthError(TelegramAIError):
    """خطأ في المصادقة"""
    def __init__(self, message: str):
        super().__init__(message, "خطأ في المصادقة. يرجى تسجيل الدخول مجدداً.")


class RateLimitError(TelegramAIError):
    """تجاوز حد الطلبات"""
    def __init__(self):
        super().__init__("Rate limit exceeded", "⚠️ لقد تجاوزت الحد المسموح. انتظر دقيقة.")


class SessionError(TelegramAIError):
    """خطأ في الجلسة"""
    def __init__(self, message: str):
        super().__init__(message, "انتهت صلاحية الجلسة. يرجى تسجيل الدخول مجدداً.")


# ─── Decorators ──────────────────────────────────────────────────────────────

def handle_errors(user_friendly: bool = True):
    """Decorator لمعالجة الأخطاء في الدوال غير المتزامنة"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except TelegramAIError:
                raise
            except Exception as e:
                logger.error(f"خطأ غير متوقع في {func.__name__}: {e}\n{traceback.format_exc()}")
                if user_friendly:
                    raise TelegramAIError(str(e))
                raise
        return wrapper
    return decorator


def format_error_for_user(error: Exception) -> str:
    """تنسيق رسالة الخطأ للمستخدم"""
    if isinstance(error, TelegramAIError):
        return error.user_message
    return "❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقاً."

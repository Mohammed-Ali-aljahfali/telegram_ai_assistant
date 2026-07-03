"""infrastructure/rate_limiter.py — تحديد معدل الطلبات"""
import time
import asyncio
from collections import defaultdict, deque
from config import config
from infrastructure.logger import get_logger

logger = get_logger("rate_limiter")


class RateLimiter:
    """Rate limiter باستخدام نافذة منزلقة"""

    def __init__(self, max_requests: int = None, window_seconds: int = None):
        self.max_requests = max_requests or config.RATE_LIMIT_MESSAGES
        self.window = window_seconds or config.RATE_LIMIT_WINDOW
        self._requests: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        """هل المستخدم مسموح له؟"""
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.window
            user_requests = self._requests[key]

            # إزالة الطلبات القديمة
            while user_requests and user_requests[0] < window_start:
                user_requests.popleft()

            if len(user_requests) >= self.max_requests:
                logger.warning(f"Rate limit exceeded for: {key}")
                return False

            user_requests.append(now)
            return True

    async def remaining(self, key: str) -> int:
        """عدد الطلبات المتبقية"""
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.window
            user_requests = self._requests[key]
            while user_requests and user_requests[0] < window_start:
                user_requests.popleft()
            return max(0, self.max_requests - len(user_requests))

    def reset(self, key: str):
        """إعادة تعيين لمستخدم معين"""
        self._requests.pop(key, None)


# Singleton
_rate_limiter = RateLimiter()


async def check_rate_limit(user_id: int, action: str = "default") -> bool:
    """تحقق من حد الطلبات"""
    key = f"{user_id}:{action}"
    return await _rate_limiter.is_allowed(key)


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter

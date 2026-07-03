"""infrastructure/retry.py — آلية إعادة المحاولة مع Exponential Backoff"""
import asyncio
import functools
from typing import Callable, Type, tuple
from infrastructure.logger import get_logger

logger = get_logger("retry")


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
):
    """Decorator لإعادة المحاولة تلقائياً"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"فشل {func.__name__} بعد {max_retries} محاولات: {e}")
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"محاولة {attempt + 1}/{max_retries} فشلت في {func.__name__}: {e}. انتظار {delay:.1f}s")
                    await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator

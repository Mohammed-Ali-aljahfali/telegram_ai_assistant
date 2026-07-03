"""
Message Formatters
==================
Utility functions for formatting text, dates, numbers,
and other display values for the bot UI.
"""

import html
import re
from datetime import datetime, timezone
from typing import Union, Optional


# Arabic month names
_AR_MONTHS = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

# Arabic day names
_AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

# Arabic-Indic digit map
_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def format_number(n: Union[int, float], arabic_numerals: bool = False) -> str:
    """
    Format a number with thousands separator.

    Args:
        n: The number to format.
        arabic_numerals: If True, convert to Arabic-Indic numerals.

    Returns:
        Formatted number string.
    """
    try:
        if isinstance(n, float):
            result = f"{n:,.2f}"
        else:
            result = f"{int(n):,}"
        if arabic_numerals:
            result = result.translate(_AR_DIGITS)
        return result
    except (TypeError, ValueError):
        return str(n)


def format_date_ar(dt: Optional[datetime], include_time: bool = True) -> str:
    """
    Format a datetime object to a human-readable Arabic string.

    Args:
        dt: datetime object (aware or naive).
        include_time: Whether to include the time portion.

    Returns:
        Arabic formatted date string.
    """
    if dt is None:
        return "غير محدد"
    try:
        day_name = _AR_DAYS[dt.weekday()]
        month_name = _AR_MONTHS[dt.month]
        date_str = f"{day_name} {dt.day} {month_name} {dt.year}"
        if include_time:
            date_str += f" - {dt.hour:02d}:{dt.minute:02d}"
        return date_str
    except (AttributeError, IndexError):
        return str(dt)


def format_date_short(dt: Optional[datetime]) -> str:
    """Format date as DD/MM/YYYY HH:MM."""
    if dt is None:
        return "—"
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except AttributeError:
        return str(dt)


def format_status_emoji(status: str) -> str:
    """
    Return an emoji for a given status string.

    Args:
        status: Status key string.

    Returns:
        Corresponding emoji character.
    """
    status_map = {
        # General
        "active": "🟢",
        "inactive": "🔴",
        "pending": "🟡",
        "disabled": "⚫",
        "enabled": "🟢",
        "on": "✅",
        "off": "❌",
        # Customer statuses
        "new": "🆕",
        "contacted": "📞",
        "interested": "✨",
        "converted": "✅",
        "rejected": "❌",
        "follow_up": "🔄",
        # System
        "connected": "🟢",
        "disconnected": "🔴",
        "running": "▶️",
        "stopped": "⏹",
        "error": "❗",
        "warning": "⚠️",
        "ok": "✅",
        "loading": "⏳",
    }
    return status_map.get(status.lower(), "❓")


def format_status_text(status: str) -> str:
    """Return Arabic text for a given status string."""
    status_map = {
        "active": "نشط",
        "inactive": "غير نشط",
        "pending": "قيد الانتظار",
        "disabled": "معطّل",
        "enabled": "مفعّل",
        "on": "مفعّل",
        "off": "معطّل",
        "new": "جديد",
        "contacted": "تم التواصل",
        "interested": "مهتم",
        "converted": "تم التحويل",
        "rejected": "مرفوض",
        "follow_up": "متابعة",
        "connected": "متصل",
        "disconnected": "منقطع",
        "running": "يعمل",
        "stopped": "متوقف",
        "error": "خطأ",
        "banned": "محظور",
        "suspended": "موقوف",
        "user": "مستخدم",
        "admin": "مدير",
        "developer": "مطوّر",
    }
    return status_map.get(status.lower(), status)


def truncate_message(text: str, max_len: int = 4000, suffix: str = "...") -> str:
    """
    Safely truncate a message to max_len characters.

    Args:
        text: The text to truncate.
        max_len: Maximum allowed length (default 4000 for Telegram).
        suffix: Appended when truncation occurs.

    Returns:
        Truncated string.
    """
    if not text:
        return ""
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def escape_html(text: str) -> str:
    """
    Escape HTML special characters for safe use in HTML parse mode.

    Args:
        text: Raw text to escape.

    Returns:
        HTML-safe string.
    """
    if not text:
        return ""
    return html.escape(str(text), quote=False)


def format_percentage(value: Union[int, float], total: Union[int, float]) -> str:
    """
    Format a value as a percentage of total.

    Args:
        value: The partial count.
        total: The total count.

    Returns:
        Percentage string, e.g. "34.5%".
    """
    if not total:
        return "0%"
    try:
        pct = (float(value) / float(total)) * 100
        return f"{pct:.1f}%"
    except (TypeError, ZeroDivisionError):
        return "0%"


def format_file_size(size_bytes: int) -> str:
    """
    Format bytes into human-readable size.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Readable string like "1.5 MB".
    """
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: int) -> str:
    """
    Format seconds into a human-readable Arabic duration.

    Args:
        seconds: Duration in seconds.

    Returns:
        Arabic duration string.
    """
    if seconds < 60:
        return f"{seconds} ثانية"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} دقيقة"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        if remaining_minutes:
            return f"{hours} ساعة و{remaining_minutes} دقيقة"
        return f"{hours} ساعة"
    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours:
        return f"{days} يوم و{remaining_hours} ساعة"
    return f"{days} يوم"


def format_phone(phone: Optional[str]) -> str:
    """Format phone number for display."""
    if not phone:
        return "غير مرتبط"
    phone = str(phone).strip()
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone


def strip_html_tags(text: str) -> str:
    """Remove all HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", str(text))


def bold(text: str) -> str:
    """Wrap text in HTML bold tags."""
    return f"<b>{escape_html(text)}</b>"


def italic(text: str) -> str:
    """Wrap text in HTML italic tags."""
    return f"<i>{escape_html(text)}</i>"


def code(text: str) -> str:
    """Wrap text in HTML code tags."""
    return f"<code>{escape_html(str(text))}</code>"


def progress_bar(value: int, total: int, length: int = 10) -> str:
    """
    Generate a Unicode progress bar.

    Args:
        value: Current value.
        total: Maximum value.
        length: Bar length in characters.

    Returns:
        Progress bar string like [████░░░░░░] 40%
    """
    if not total:
        filled = 0
    else:
        filled = int(length * min(value, total) / total)
    bar = "█" * filled + "░" * (length - filled)
    pct = format_percentage(value, total)
    return f"[{bar}] {pct}"


def now_ar() -> str:
    """Return current datetime as Arabic formatted string."""
    return format_date_ar(datetime.now())

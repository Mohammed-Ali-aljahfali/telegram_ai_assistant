"""utils/text_utils.py — أدوات معالجة النصوص"""
import re
from typing import Optional


def truncate_text(text: str, max_len: int = 4000, suffix: str = "...") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def clean_markdown(text: str) -> str:
    """تنظيف رموز Markdown"""
    return re.sub(r"[*_`\[\]()~>#+=|{}.!]", lambda m: f"\\{m.group()}", text)


def detect_language(text: str) -> str:
    """كشف اللغة بشكل بسيط"""
    arabic = len(re.findall(r"[\u0600-\u06FF]", text))
    total = len(text.strip()) or 1
    return "ar" if arabic / total > 0.3 else "en"


def extract_mentions(text: str) -> list[str]:
    return re.findall(r"@(\w+)", text)


def normalize_arabic(text: str) -> str:
    """توحيد الحروف العربية"""
    text = re.sub(r"[أإآا]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = re.sub(r"ة", "ه", text)
    return text

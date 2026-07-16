"""bot/keyboards/main_keyboard.py — لوحات المفاتيح الرئيسية

يدعم python-telegram-bot v22.7+ خاصية style للأزرار الملونة (Bot API 9.4+):
  - "primary"  → 🔵 أزرق داكن  (الإجراء الرئيسي)
  - "success"  → 🟢 أخضر       (تأكيد / نجاح)
  - "danger"   → 🔴 أحمر       (حذف / خطر)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
import telegram

# ─── كشف دعم الأزرار الملونة (Bot API 9.4 / PTB 22.7+) ───────────────────────
_PTB_VERSION = tuple(int(x) for x in telegram.__version__.split(".")[:2])
_COLORED_BUTTONS_SUPPORTED = _PTB_VERSION >= (22, 7)


def _btn(text: str, callback_data: str, style: str = None) -> InlineKeyboardButton:
    """
    إنشاء زر Inline مع دعم اختياري للألوان.
    إذا لم تكن المكتبة تدعم الألوان يُتجاهل style بهدوء.
    """
    kwargs = {"text": text, "callback_data": callback_data}
    if style and _COLORED_BUTTONS_SUPPORTED:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


def get_main_menu_keyboard(is_developer: bool = False) -> InlineKeyboardMarkup:
    """القائمة الرئيسية"""
    buttons = [
        [
            _btn("📊 الإحصائيات", "stats_menu"),
            _btn("👥 العملاء", "customers_menu"),
        ],
        [
            _btn("💬 المحادثات", "conversations_menu"),
            _btn("📡 القنوات", "channels_menu"),
        ],
        [
            _btn("🤖 الذكاء الاصطناعي", "ai_menu"),
            _btn("⚙️ الإعدادات", "settings_menu"),
        ],
        [
            _btn("🔔 التنبيهات", "notifications_menu"),
            _btn("🖥️ حالة النظام", "system_status"),
        ],
    ]
    if is_developer:
        buttons.append([
            _btn("👑 إعدادات المطور", "developer_menu", style="primary"),
        ])
    return InlineKeyboardMarkup(buttons)


def get_back_button(callback: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("🔙 رجوع", callback)]])


def get_home_and_back(back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        _btn("🔙 رجوع", back_callback),
        _btn("🏠 الرئيسية", "main_menu"),
    ]])


def get_confirmation_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    """زر تأكيد أخضر + زر إلغاء أحمر"""
    return InlineKeyboardMarkup([[
        _btn("✅ تأكيد", confirm_cb, style="success"),
        _btn("❌ إلغاء", cancel_cb, style="danger"),
    ]])


def get_pagination_keyboard(page: int, total_pages: int, prefix: str,
                             back_cb: str = "main_menu") -> InlineKeyboardMarkup:
    buttons = []
    nav = []
    if page > 1:
        nav.append(_btn("◀️", f"{prefix}_page_{page-1}"))
    nav.append(_btn(f"📄 {page}/{total_pages}", "noop"))
    if page < total_pages:
        nav.append(_btn("▶️", f"{prefix}_page_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([
        _btn("🔙 رجوع", back_cb),
        _btn("🏠 الرئيسية", "main_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def get_toggle_keyboard(label_on: str, label_off: str,
                        cb_on: str, cb_off: str, is_on: bool,
                        back_cb: str = "main_menu") -> InlineKeyboardMarkup:
    toggle_text = f"🟢 {label_on}" if is_on else f"🔴 {label_off}"
    toggle_cb = cb_off if is_on else cb_on
    toggle_style = "success" if is_on else "danger"
    return InlineKeyboardMarkup([
        [_btn(toggle_text, toggle_cb, style=toggle_style)],
        [_btn("🔙 رجوع", back_cb)],
    ])


def get_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 مشاركة رقم الجوال", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def get_code_actions_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح أثناء انتظار رمز التحقق — تشمل إعادة الإرسال والإلغاء."""
    return InlineKeyboardMarkup([
        [_btn("🔄 إعادة إرسال الرمز", "resend_code", style="primary")],
        [_btn("❌ إلغاء تسجيل الدخول", "cancel_login", style="danger")],
    ])


def get_login_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        _btn("🔐 تسجيل الدخول", "start_login", style="success"),
    ]])

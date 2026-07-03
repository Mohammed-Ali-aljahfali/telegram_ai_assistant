"""bot/keyboards/main_keyboard.py — لوحات المفاتيح الرئيسية"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard(is_developer: bool = False) -> InlineKeyboardMarkup:
    """القائمة الرئيسية"""
    buttons = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="stats_menu"),
            InlineKeyboardButton("👥 العملاء", callback_data="customers_menu"),
        ],
        [
            InlineKeyboardButton("💬 المحادثات", callback_data="conversations_menu"),
            InlineKeyboardButton("📡 القنوات", callback_data="channels_menu"),
        ],
        [
            InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="ai_menu"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings_menu"),
        ],
        [
            InlineKeyboardButton("🔔 التنبيهات", callback_data="notifications_menu"),
            InlineKeyboardButton("🖥️ حالة النظام", callback_data="system_status"),
        ],
    ]
    if is_developer:
        buttons.append([
            InlineKeyboardButton("👑 إعدادات المطور", callback_data="developer_menu"),
        ])
    return InlineKeyboardMarkup(buttons)


def get_back_button(callback: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=callback)]])


def get_home_and_back(back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=back_callback),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu"),
    ]])


def get_confirmation_keyboard(confirm_cb: str, cancel_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تأكيد", callback_data=confirm_cb),
        InlineKeyboardButton("❌ إلغاء", callback_data=cancel_cb),
    ]])


def get_pagination_keyboard(page: int, total_pages: int, prefix: str,
                             back_cb: str = "main_menu") -> InlineKeyboardMarkup:
    buttons = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"{prefix}_page_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"{prefix}_page_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([
        InlineKeyboardButton("🔙 رجوع", callback_data=back_cb),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def get_toggle_keyboard(label_on: str, label_off: str,
                        cb_on: str, cb_off: str, is_on: bool,
                        back_cb: str = "main_menu") -> InlineKeyboardMarkup:
    toggle_text = f"🟢 {label_on}" if is_on else f"🔴 {label_off}"
    toggle_cb = cb_off if is_on else cb_on
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=toggle_cb)],
        [InlineKeyboardButton("🔙 رجوع", callback_data=back_cb)],
    ])


def get_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 مشاركة رقم الجوال", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def get_login_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔐 تسجيل الدخول", callback_data="start_login"),
    ]])

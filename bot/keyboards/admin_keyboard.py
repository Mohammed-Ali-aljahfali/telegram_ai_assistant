"""bot/keyboards/admin_keyboard.py — لوحات مفاتيح المطور"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_developer_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="dev_users"),
            InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="dev_subscription"),
        ],
        [
            InlineKeyboardButton("⚙️ إعدادات النظام", callback_data="dev_system_settings"),
            InlineKeyboardButton("📋 سجل الأحداث", callback_data="dev_logs"),
        ],
        [
            InlineKeyboardButton("💾 نسخة احتياطية", callback_data="dev_backup"),
            InlineKeyboardButton("📣 إرسال لجميع المستخدمين", callback_data="dev_broadcast"),
        ],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")],
    ])


def get_user_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ إضافة مستخدم", callback_data="dev_add_user"),
            InlineKeyboardButton("📋 قائمة المستخدمين", callback_data="dev_users_list_1"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="developer_menu")],
    ])


def get_user_actions_keyboard(telegram_id: int, status: str, role: str) -> InlineKeyboardMarkup:
    buttons = []
    if status == "active":
        buttons.append([
            InlineKeyboardButton("⏸️ إيقاف الحساب", callback_data=f"dev_suspend_{telegram_id}"),
            InlineKeyboardButton("🚫 حظر", callback_data=f"dev_ban_{telegram_id}"),
        ])
    elif status == "suspended":
        buttons.append([
            InlineKeyboardButton("▶️ تفعيل", callback_data=f"dev_activate_{telegram_id}"),
            InlineKeyboardButton("🚫 حظر", callback_data=f"dev_ban_{telegram_id}"),
        ])
    elif status == "banned":
        buttons.append([
            InlineKeyboardButton("✅ رفع الحظر", callback_data=f"dev_unban_{telegram_id}"),
        ])

    if role != "developer":
        if role == "user":
            buttons.append([InlineKeyboardButton("⬆️ ترقية لمشرف", callback_data=f"dev_promote_{telegram_id}")])
        else:
            buttons.append([InlineKeyboardButton("⬇️ تخفيض لمستخدم", callback_data=f"dev_demote_{telegram_id}")])

    buttons.append([
        InlineKeyboardButton("🗑️ حذف", callback_data=f"dev_delete_{telegram_id}"),
        InlineKeyboardButton("🔙 رجوع", callback_data="dev_users_list_1"),
    ])
    return InlineKeyboardMarkup(buttons)


def get_subscription_menu_keyboard(enforcement_enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "🔴 تعطيل الاشتراك الإجباري" if enforcement_enabled else "🟢 تفعيل الاشتراك الإجباري"
    toggle_cb = "dev_sub_disable" if enforcement_enabled else "dev_sub_enable"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=toggle_cb)],
        [
            InlineKeyboardButton("➕ إضافة قناة", callback_data="dev_sub_add"),
            InlineKeyboardButton("📋 القنوات المطلوبة", callback_data="dev_sub_list"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="developer_menu")],
    ])

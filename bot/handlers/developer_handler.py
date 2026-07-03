"""bot/handlers/developer_handler.py — معالج إعدادات المطور"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from config import config
from services.user_service import UserService
from services.subscription_service import SubscriptionService
from database.repositories.channel_repository import ChannelRepository
from models.user import UserRole, UserStatus
from models.chat import RequiredChannel
from bot.keyboards.admin_keyboard import (
    get_developer_menu_keyboard, get_user_management_keyboard,
    get_user_actions_keyboard, get_subscription_menu_keyboard
)
from bot.keyboards.main_keyboard import get_back_button, get_pagination_keyboard, get_confirmation_keyboard
from infrastructure.logger import get_logger
import math

logger = get_logger("bot.developer")

user_service = UserService()
sub_service = SubscriptionService()
channel_repo = ChannelRepository()

WAITING_NEW_USER_ID = 10
WAITING_BROADCAST = 11
WAITING_SUB_CHANNEL = 12

PER_PAGE = 10


def is_developer(telegram_id: int) -> bool:
    return telegram_id == config.DEVELOPER_ID


async def handle_developer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_developer(update.effective_user.id):
        await query.answer("🚫 غير مصرح", show_alert=True)
        return
    await query.edit_message_text(
        "👑 *لوحة تحكم المطور*\n\nاختر ما تريد إدارته:",
        reply_markup=get_developer_menu_keyboard(),
        parse_mode="Markdown"
    )


async def handle_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_developer(update.effective_user.id):
        return

    # استخراج رقم الصفحة من callback_data
    data = query.data  # dev_users_list_1
    try:
        page = int(data.split("_")[-1])
    except Exception:
        page = 1

    users, total = await user_service.get_all(page, PER_PAGE)
    total_pages = max(1, math.ceil(total / PER_PAGE))

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    for u in users:
        status_icon = {"active": "🟢", "suspended": "⏸️", "banned": "🚫"}.get(u.status.value, "❓")
        role_icon = {"developer": "👑", "admin": "⭐", "user": "👤"}.get(u.role.value, "👤")
        label = f"{status_icon}{role_icon} {u.display_name}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dev_user_{u.telegram_id}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"dev_users_list_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"dev_users_list_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("➕ إضافة مستخدم", callback_data="dev_add_user")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="developer_menu")])

    await query.edit_message_text(
        f"👥 *المستخدمون* — {total} مستخدم",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def handle_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_developer(update.effective_user.id):
        return

    telegram_id = int(query.data.split("_")[-1])
    user = await user_service.get(telegram_id)
    if not user:
        await query.answer("❌ المستخدم غير موجود", show_alert=True)
        return

    text = f"""👤 *تفاصيل المستخدم*

🆔 ID: `{user.telegram_id}`
📝 الاسم: `{user.display_name}`
🔖 Username: `@{user.username or 'غير محدد'}`
📱 الهاتف: `{user.phone or 'غير محدد'}`
👑 الدور: `{user.role.value}`
📊 الحالة: `{user.status.value}`
🔐 مصادق: `{'نعم' if user.is_authenticated else 'لا'}`
📅 التسجيل: `{user.created_at.strftime('%Y-%m-%d') if user.created_at else 'غير محدد'}`
"""
    await query.edit_message_text(
        text,
        reply_markup=get_user_actions_keyboard(user.telegram_id, user.status.value, user.role.value),
        parse_mode="Markdown"
    )


async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.ban(telegram_id)
    await query.answer("🚫 تم حظر المستخدم", show_alert=True)
    await handle_user_detail(update, context)


async def handle_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.unban(telegram_id)
    await query.answer("✅ تم رفع الحظر", show_alert=True)
    await handle_user_detail(update, context)


async def handle_suspend_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.suspend(telegram_id)
    await query.answer("⏸️ تم إيقاف الحساب", show_alert=True)
    await handle_user_detail(update, context)


async def handle_activate_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.update_status(telegram_id, UserStatus.ACTIVE)
    await query.answer("✅ تم تفعيل الحساب", show_alert=True)
    await handle_user_detail(update, context)


async def handle_promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.set_role(telegram_id, UserRole.ADMIN)
    await query.answer("⬆️ تمت الترقية لمشرف", show_alert=True)
    await handle_user_detail(update, context)


async def handle_demote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.set_role(telegram_id, UserRole.USER)
    await query.answer("⬇️ تم التخفيض لمستخدم", show_alert=True)
    await handle_user_detail(update, context)


async def handle_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = int(query.data.split("_")[-1])
    await user_service.delete(telegram_id)
    await query.edit_message_text(
        "🗑️ تم حذف المستخدم.",
        reply_markup=get_back_button("dev_users_list_1")
    )


# ─── الاشتراك الإجباري ────────────────────────────────────────────────────────

async def handle_subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_developer(update.effective_user.id):
        return

    enforcement = await sub_service.is_enforcement_enabled()
    channels = await sub_service.get_required_channels()
    channels_text = "\n".join(
        [f"• {ch.title or ch.channel_username} (`{ch.channel_id}`)" for ch in channels]
    ) or "لا توجد قنوات مضافة"

    text = f"""📢 *إدارة الاشتراك الإجباري*

الحالة: {'🟢 مفعّل' if enforcement else '🔴 معطّل'}

القنوات المطلوبة:
{channels_text}
"""
    await query.edit_message_text(
        text,
        reply_markup=get_subscription_menu_keyboard(enforcement),
        parse_mode="Markdown"
    )


async def handle_enable_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await sub_service.toggle_enforcement(True)
    await handle_subscription_menu(update, context)


async def handle_disable_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await sub_service.toggle_enforcement(False)
    await handle_subscription_menu(update, context)


async def handle_add_required_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📢 *إضافة قناة للاشتراك الإجباري*\n\n"
        "أرسل رابط القناة أو اسم المستخدم مثل:\n"
        "`@channel_username`\n\n"
        "أو أعد توجيه رسالة من القناة مباشرة.",
        reply_markup=get_back_button("dev_subscription"),
        parse_mode="Markdown"
    )
    return WAITING_SUB_CHANNEL


async def handle_add_required_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال معلومات القناة"""
    text = update.message.text.strip()
    username = text.lstrip("@").replace("https://t.me/", "")
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/getChat",
            params={"chat_id": f"@{username}"}
        )
        data = resp.json()

    if not data.get("ok"):
        await update.message.reply_text(
            "❌ تعذر جلب معلومات القناة. تأكد أن البوت مضاف كمشرف فيها.",
            reply_markup=get_back_button("dev_subscription")
        )
        return ConversationHandler.END

    chat = data["result"]
    await sub_service.add_required_channel(
        channel_id=chat["id"],
        username=chat.get("username", username),
        title=chat.get("title", username),
        added_by=update.effective_user.id
    )
    await update.message.reply_text(
        f"✅ تمت إضافة *{chat.get('title', username)}* للاشتراك الإجباري.",
        reply_markup=get_back_button("dev_subscription"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def handle_backup_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_developer(update.effective_user.id):
        return
    await query.edit_message_text("💾 جاري إنشاء النسخة الاحتياطية...")
    from database.backup import backup_database
    path = await backup_database()
    await query.edit_message_text(
        f"✅ تمت النسخة الاحتياطية:\n`{path.name}`",
        reply_markup=get_back_button("developer_menu"),
        parse_mode="Markdown"
    )

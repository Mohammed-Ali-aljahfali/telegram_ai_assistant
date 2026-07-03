"""bot/handlers/system_handler.py — معالج حالة النظام"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telethon_client.client import telethon_manager
from services.user_service import UserService
from bot.keyboards.main_keyboard import get_back_button
from bot.messages.templates import format_system_status
from infrastructure.logger import get_logger
from config import config
import os

logger = get_logger("bot.system")
user_service = UserService()


async def handle_system_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = await user_service.get(user_id)

    connected = telethon_manager.is_connected(user_id)
    ai_status = "🟢 متصل" if connected else "🔴 غير متصل"

    db_path = config.DATABASE_PATH
    db_size = f"{os.path.getsize(db_path) / 1024:.1f} KB" if db_path.exists() else "0 KB"
    connected_count = telethon_manager.get_connected_count()

    text = format_system_status(connected_count, ai_status, db_size)

    start_label = "🔴 إيقاف المراقبة" if connected else "🟢 بدء المراقبة"
    start_cb = "system_stop" if connected else "system_start"

    buttons = [
        [InlineKeyboardButton(start_label, callback_data=start_cb)],
        [InlineKeyboardButton("🔄 إعادة الاتصال", callback_data="system_reconnect")],
        [InlineKeyboardButton("📋 السجلات", callback_data="system_logs")],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def handle_start_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = await user_service.get(user_id)

    if not user or not user.telethon_session:
        await query.answer("❌ يجب تسجيل الدخول أولاً", show_alert=True)
        return

    await query.edit_message_text("⏳ جاري بدء المراقبة...")
    success = await telethon_manager.create_and_start(user_id, user.telethon_session)
    if success:
        await query.edit_message_text(
            "✅ تم بدء المراقبة بنجاح!",
            reply_markup=get_back_button("system_status")
        )
    else:
        await query.edit_message_text(
            "❌ فشل الاتصال. تحقق من الجلسة وأعد تسجيل الدخول.",
            reply_markup=get_back_button("system_status")
        )


async def handle_stop_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await telethon_manager.stop(user_id)
    await query.edit_message_text(
        "🛑 تم إيقاف المراقبة.",
        reply_markup=get_back_button("system_status")
    )


async def handle_system_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log_path = config.LOG_DIR / "app.log"
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        last_lines = "".join(lines[-20:])
        text = f"📋 *آخر السجلات:*\n\n```\n{last_lines[-3000:]}\n```"
    except Exception:
        text = "❌ لا توجد سجلات."
    await query.edit_message_text(text, reply_markup=get_back_button("system_status"), parse_mode="Markdown")


async def handle_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    from services.notification_service import NotificationService
    notif_service = NotificationService()
    notifications = await notif_service.get_recent(user_id)
    unread = await notif_service.count_unread(user_id)

    if not notifications:
        await query.edit_message_text(
            "🔔 *التنبيهات*\n\nلا توجد تنبيهات حتى الآن.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="Markdown"
        )
        return

    from bot.messages.templates import format_notification
    text = f"🔔 *التنبيهات* — {unread} غير مقروء\n\n"
    for n in notifications[:10]:
        text += format_notification(n) + "\n\n"

    buttons = [
        [InlineKeyboardButton("✅ تحديد الكل كمقروء", callback_data="notif_mark_all_read")],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def handle_mark_all_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    from services.notification_service import NotificationService
    await NotificationService().mark_all_read(user_id)
    await handle_notifications_menu(update, context)

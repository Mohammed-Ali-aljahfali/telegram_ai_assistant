"""bot/handlers/channels_handler.py — معالج إدارة القنوات"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from database.repositories.channel_repository import ChannelRepository
from bot.keyboards.main_keyboard import get_back_button
from infrastructure.logger import get_logger
import httpx
from config import config

logger = get_logger("bot.channels")
channel_repo = ChannelRepository()

WAITING_CHANNEL_USERNAME = 20


async def handle_channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    channels = await channel_repo.get_all_for_user(user_id)

    buttons = []
    for ch in channels:
        status = "🟢" if ch.is_active else "🔴"
        buttons.append([InlineKeyboardButton(
            f"{status} {ch.title or ch.username or str(ch.channel_id)}",
            callback_data=f"channel_{ch.id}"
        )])
    buttons.append([InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])

    await query.edit_message_text(
        f"📡 *القنوات المراقبة* — {len(channels)} قناة",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def handle_channel_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel_id_db = int(query.data.split("_")[-1])

    channels = await channel_repo.get_all_for_user(update.effective_user.id)
    ch = next((c for c in channels if c.id == channel_id_db), None)
    if not ch:
        await query.answer("❌ غير موجود", show_alert=True)
        return

    status = "🟢 نشط" if ch.is_active else "🔴 متوقف"
    text = f"""📡 *{ch.title or ch.username}*

🆔 ID: `{ch.channel_id}`
📊 الحالة: {status}
🤖 رد تلقائي: {'نعم' if ch.auto_reply else 'لا'}
🔑 كلمات مفتاحية فقط: {'نعم' if ch.keywords_only else 'لا'}
"""
    toggle_label = "🔴 إيقاف" if ch.is_active else "🟢 تفعيل"
    toggle_cb = f"ch_disable_{channel_id_db}" if ch.is_active else f"ch_enable_{channel_id_db}"
    buttons = [
        [InlineKeyboardButton(toggle_label, callback_data=toggle_cb)],
        [InlineKeyboardButton("🗑️ حذف القناة", callback_data=f"ch_delete_{channel_id_db}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="channels_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def handle_toggle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    action = parts[1]    # enable | disable
    ch_id_db = int(parts[2])

    channels = await channel_repo.get_all_for_user(update.effective_user.id)
    ch = next((c for c in channels if c.id == ch_id_db), None)
    if ch:
        await channel_repo.toggle_active(update.effective_user.id, ch.channel_id, action == "enable")

    query.data = f"channel_{ch_id_db}"
    await handle_channel_detail(update, context)


async def handle_delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ch_id_db = int(query.data.split("_")[-1])
    channels = await channel_repo.get_all_for_user(update.effective_user.id)
    ch = next((c for c in channels if c.id == ch_id_db), None)
    if ch:
        await channel_repo.remove_channel(update.effective_user.id, ch.channel_id)
    await query.edit_message_text("✅ تم حذف القناة.", reply_markup=get_back_button("channels_menu"))


async def handle_add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📡 *إضافة قناة للمراقبة*\n\n"
        "أرسل اسم مستخدم القناة:\n`@channel_name`",
        reply_markup=get_back_button("channels_menu"),
        parse_mode="Markdown"
    )
    return WAITING_CHANNEL_USERNAME


async def handle_add_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lstrip("@")
    user_id = update.effective_user.id

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{config.BOT_TOKEN}/getChat",
            params={"chat_id": f"@{text}"}
        )
        data = resp.json()

    if not data.get("ok"):
        await update.message.reply_text(
            "❌ تعذر جلب معلومات القناة.",
            reply_markup=get_back_button("channels_menu")
        )
        return ConversationHandler.END

    from models.chat import Channel
    chat = data["result"]
    channel = Channel(
        bot_user_id=user_id,
        channel_id=chat["id"],
        username=chat.get("username", text),
        title=chat.get("title", text),
        channel_type=chat.get("type", "channel"),
    )
    await channel_repo.add_channel(channel)
    await update.message.reply_text(
        f"✅ تمت إضافة *{chat.get('title', text)}* للمراقبة!",
        reply_markup=get_back_button("channels_menu"),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

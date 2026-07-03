"""bot/handlers/start_handler.py — معالج البداية وتسجيل الدخول"""
import re
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from services.user_service import UserService
from services.subscription_service import SubscriptionService
from telethon_client.auth_handler import TelethonAuthHandler
from infrastructure.crypto import encrypt_text
from bot.keyboards.main_keyboard import (
    get_main_menu_keyboard, get_login_keyboard,
    get_phone_keyboard, get_back_button
)
from bot.messages.templates import (
    WELCOME_NEW, WELCOME_BACK, LOGIN_PHONE_PROMPT,
    LOGIN_CODE_PROMPT, LOGIN_2FA_PROMPT,
    SUBSCRIPTION_REQUIRED, BANNED_MESSAGE, SUSPENDED_MESSAGE
)
from infrastructure.logger import get_logger

logger = get_logger("bot.start")

# ─── States ──────────────────────────────────────────────────────────────────
WAITING_PHONE = 1
WAITING_CODE = 2
WAITING_2FA = 3
CHECKING_SUB = 4

user_service = UserService()
sub_service = SubscriptionService()
auth_handler = TelethonAuthHandler()


async def _show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """عرض القائمة الرئيسية"""
    is_dev = user.is_developer
    text = WELCOME_BACK.format(user.display_name)
    keyboard = get_main_menu_keyboard(is_developer=is_dev)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة دخول البوت"""
    tg_user = update.effective_user
    user = await user_service.get_or_create(
        tg_user.id, tg_user.username, tg_user.first_name
    )

    # فحص الحظر
    if user.status.value == "banned":
        await update.message.reply_text(BANNED_MESSAGE)
        return ConversationHandler.END

    if user.status.value == "suspended":
        await update.message.reply_text(SUSPENDED_MESSAGE)
        return ConversationHandler.END

    # مستخدم مسجل ومصادق
    if user.is_authenticated and user.telethon_session:
        # فحص الاشتراك الإجباري
        if await sub_service.is_enforcement_enabled():
            unsubscribed = await sub_service.get_unsubscribed_channels(tg_user.id)
            if unsubscribed:
                await _show_subscription_required(update, context, unsubscribed)
                return CHECKING_SUB
        await _show_main_menu(update, context, user)
        return ConversationHandler.END

    # مستخدم جديد — عرض شاشة الترحيب
    await update.message.reply_text(
        WELCOME_NEW,
        reply_markup=get_login_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def handle_main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user
    user = await user_service.get(tg_user.id)
    if user:
        await _show_main_menu(update, context, user)


async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية تسجيل الدخول"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        LOGIN_PHONE_PROMPT,
        reply_markup=get_back_button("cancel_login"),
        parse_mode="Markdown"
    )
    # إرسال زر مشاركة رقم الجوال
    await query.message.reply_text(
        "📱 أو اضغط هنا:",
        reply_markup=get_phone_keyboard()
    )
    return WAITING_PHONE


async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال رقم الجوال"""
    if update.message.contact:
        phone = update.message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    else:
        phone = update.message.text.strip()
        if not re.match(r"^\+\d{7,15}$", phone):
            await update.message.reply_text(
                "❌ صيغة الرقم غير صحيحة. مثال: `+966501234567`",
                parse_mode="Markdown"
            )
            return WAITING_PHONE

    user_id = update.effective_user.id
    context.user_data["phone"] = phone

    await update.message.reply_text("⏳ جاري إرسال رمز التحقق...",
                                    reply_markup=ReplyKeyboardRemove())

    success, result = await auth_handler.send_code(user_id, phone)
    if not success:
        await update.message.reply_text(result)
        return WAITING_PHONE

    context.user_data["phone_code_hash"] = result
    await user_service.update_phone(user_id, phone)
    await update.message.reply_text(LOGIN_CODE_PROMPT, parse_mode="Markdown")
    return WAITING_CODE


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال رمز التحقق"""
    code = update.message.text.strip().replace(" ", "")
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ جاري التحقق...")

    success, needs_2fa, result = await auth_handler.verify_code(user_id, code)

    if needs_2fa:
        await update.message.reply_text(LOGIN_2FA_PROMPT, parse_mode="Markdown")
        return WAITING_2FA

    if not success:
        await update.message.reply_text(result)
        return WAITING_CODE

    return await _complete_login(update, context, result)


async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال كلمة مرور 2FA"""
    password = update.message.text.strip()
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ جاري التحقق من كلمة المرور...")
    success, result = await auth_handler.verify_2fa(user_id, password)

    if not success:
        await update.message.reply_text(result)
        return WAITING_2FA

    return await _complete_login(update, context, result)


async def _complete_login(update: Update, context: ContextTypes.DEFAULT_TYPE, session: str):
    """إتمام تسجيل الدخول"""
    user_id = update.effective_user.id
    encrypted_session = encrypt_text(session)
    await user_service.save_session(user_id, encrypted_session)

    # بدء عميل Telethon
    from telethon_client.client import telethon_manager
    connected = await telethon_manager.create_and_start(user_id, encrypted_session)

    if not connected:
        await update.message.reply_text("⚠️ تم حفظ الجلسة لكن تعذر الاتصال التلقائي.")

    # فحص الاشتراك الإجباري
    if await sub_service.is_enforcement_enabled():
        unsubscribed = await sub_service.get_unsubscribed_channels(user_id)
        if unsubscribed:
            await _show_subscription_required(update, context, unsubscribed)
            return CHECKING_SUB

    user = await user_service.get(user_id)
    await update.message.reply_text("✅ تم تسجيل الدخول بنجاح!")
    await _show_main_menu(update, context, user)
    return ConversationHandler.END


async def _show_subscription_required(update, context, unsubscribed_channels):
    """عرض شاشة الاشتراك الإجباري"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    channels_text = "\n".join(
        [f"• [{ch.title or ch.channel_username}](https://t.me/{ch.channel_username})"
         for ch in unsubscribed_channels]
    )
    keyboard = []
    for ch in unsubscribed_channels:
        link = f"https://t.me/{ch.channel_username}" if ch.channel_username else f"https://t.me/c/{ch.channel_id}"
        keyboard.append([InlineKeyboardButton(f"📢 {ch.title or 'انضم'}", url=link)])
    keyboard.append([InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="verify_subscription")])

    text = SUBSCRIPTION_REQUIRED.format(channels_text)
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard),
                                        parse_mode="Markdown", disable_web_page_preview=True)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard),
                                                       parse_mode="Markdown", disable_web_page_preview=True)


async def verify_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من الاشتراك"""
    query = update.callback_query
    await query.answer("⏳ جاري التحقق...")
    user_id = update.effective_user.id

    unsubscribed = await sub_service.get_unsubscribed_channels(user_id)
    if unsubscribed:
        await _show_subscription_required(update, context, unsubscribed)
        return CHECKING_SUB

    user = await user_service.get(user_id)
    await query.edit_message_text("✅ تم التحقق من الاشتراك!")
    await _show_main_menu(update, context, user)
    return ConversationHandler.END


async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء تسجيل الدخول"""
    user_id = update.effective_user.id
    auth_handler.cancel_auth(user_id)
    await update.callback_query.edit_message_text(
        "❌ تم إلغاء تسجيل الدخول.",
        reply_markup=get_login_keyboard()
    )
    return ConversationHandler.END


def get_auth_conversation_handler() -> ConversationHandler:
    """بناء ConversationHandler لعملية تسجيل الدخول"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_login, pattern="^start_login$"),
        ],
        states={
            WAITING_PHONE: [
                MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, handle_phone),
            ],
            WAITING_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code),
            ],
            WAITING_2FA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_2fa),
            ],
            CHECKING_SUB: [
                CallbackQueryHandler(verify_subscription, pattern="^verify_subscription$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_login, pattern="^cancel_login$"),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

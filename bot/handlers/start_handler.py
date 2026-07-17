"""bot/handlers/start_handler.py — معالج البداية وتسجيل الدخول

يُدير ConversationHandler الخاص بعملية تسجيل الدخول.
يتكامل مع TelethonAuthHandler الذي يُشغِّل Login State Machine الكاملة.

الحالات:
    WAITING_PHONE  → انتظار رقم الهاتف
    WAITING_CODE   → انتظار رمز التحقق
    WAITING_2FA    → انتظار كلمة مرور 2FA
    CHECKING_SUB   → انتظار تأكيد الاشتراك الإجباري
"""
from __future__ import annotations

import re

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.keyboards.main_keyboard import (
    get_back_button,
    get_code_actions_keyboard,
    get_login_keyboard,
    get_main_menu_keyboard,
    get_phone_keyboard,
)
from bot.messages.templates import (
    BANNED_MESSAGE,
    LOGIN_2FA_PROMPT,
    LOGIN_AUTH_RESTART,
    LOGIN_CODE_EXPIRED,
    LOGIN_CODE_PROMPT,
    LOGIN_CODE_RESENT,
    LOGIN_FLOOD_WAIT,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_PHONE_PROMPT,
    SUBSCRIPTION_REQUIRED,
    SUSPENDED_MESSAGE,
    WELCOME_BACK,
    WELCOME_NEW,
)
from infrastructure.crypto import encrypt_text
from infrastructure.logger import get_logger
from services.subscription_service import SubscriptionService
from services.user_service import UserService
from telethon_client.auth_handler import LoginState, TelethonAuthHandler

logger = get_logger("bot.start")

# ─── حالات ConversationHandler ───────────────────────────────────────────────
WAITING_PHONE = 1
WAITING_CODE  = 2
WAITING_2FA   = 3
CHECKING_SUB  = 4

# ─── Singletons ───────────────────────────────────────────────────────────────
user_service  = UserService()
sub_service   = SubscriptionService()
auth_handler  = TelethonAuthHandler()


# ─── مساعدات ─────────────────────────────────────────────────────────────────

async def _show_main_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user
) -> None:
    """عرض القائمة الرئيسية."""
    is_dev = user.is_developer
    text   = WELCOME_BACK.format(user.display_name)
    keyboard = get_main_menu_keyboard(is_developer=is_dev)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )


async def _show_subscription_required(
    update: Update, context: ContextTypes.DEFAULT_TYPE, unsubscribed_channels
) -> None:
    """عرض شاشة الاشتراك الإجباري."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    channels_text = "\n".join(
        f"• [{ch.title or ch.channel_username}](https://t.me/{ch.channel_username})"
        for ch in unsubscribed_channels
    )
    keyboard = []
    for ch in unsubscribed_channels:
        link = (
            f"https://t.me/{ch.channel_username}"
            if ch.channel_username
            else f"https://t.me/c/{ch.channel_id}"
        )
        keyboard.append([InlineKeyboardButton(f"📢 {ch.title or 'انضم'}", url=link)])
    keyboard.append(
        [InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="verify_subscription")]
    )

    text = SUBSCRIPTION_REQUIRED.format(channels_text)
    send = (
        update.message.reply_text
        if update.message
        else update.callback_query.edit_message_text
    )
    await send(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة دخول البوت."""
    tg_user = update.effective_user
    user = await user_service.get_or_create(
        tg_user.id, tg_user.username, tg_user.first_name
    )

    if user.status.value == "banned":
        await update.message.reply_text(BANNED_MESSAGE)
        return ConversationHandler.END

    if user.status.value == "suspended":
        await update.message.reply_text(SUSPENDED_MESSAGE)
        return ConversationHandler.END

    # ─ مسؤول/مطور النظام — صلاحيات كاملة والدخول المباشر بدون تسجيل دخول Telethon ──
    from config import config
    if user.is_developer or tg_user.id in (config.DEVELOPER_ID, config.ADMIN_CHAT_ID):
        if not user.is_authenticated:
            user.is_authenticated = True
            await user_service.repo.update_session(tg_user.id, user.telethon_session or "", True)
        if await sub_service.is_enforcement_enabled():
            unsubscribed = await sub_service.get_unsubscribed_channels(tg_user.id)
            if unsubscribed:
                await _show_subscription_required(update, context, unsubscribed)
                return CHECKING_SUB
        await _show_main_menu(update, context, user)
        return ConversationHandler.END

    # ─ مستخدم مسجل ومصادق ─────────────────────────────────────────────────
    if user.is_authenticated and user.telethon_session:
        if await sub_service.is_enforcement_enabled():
            unsubscribed = await sub_service.get_unsubscribed_channels(tg_user.id)
            if unsubscribed:
                await _show_subscription_required(update, context, unsubscribed)
                return CHECKING_SUB
        await _show_main_menu(update, context, user)
        return ConversationHandler.END

    # ─ مستخدم جديد / غير مسجل ────────────────────────────────────────────
    # فحص: هل توجد جلسة تسجيل دخول جارية من قبل؟ (استئناف بعد إعادة التشغيل)
    pending_state = await auth_handler.get_pending_state(tg_user.id)
    if pending_state == LoginState.WAIT_CODE:
        await update.message.reply_text(
            "⚠️ يبدو أنك في منتصف عملية تسجيل الدخول.\n"
            "أدخل رمز التحقق الذي وصلك، أو اضغط إعادة إرسال:",
            reply_markup=get_code_actions_keyboard(),
            parse_mode="Markdown",
        )
        return WAITING_CODE

    if pending_state == LoginState.WAIT_2FA:
        await update.message.reply_text(
            "⚠️ يبدو أنك في مرحلة التحقق بخطوتين.\n"
            "أدخل كلمة مرور 2FA للمتابعة:",
            parse_mode="Markdown",
        )
        return WAITING_2FA

    await update.message.reply_text(
        WELCOME_NEW,
        reply_markup=get_login_keyboard(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ─── بدء تسجيل الدخول ────────────────────────────────────────────────────────

async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية تسجيل الدخول."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        LOGIN_PHONE_PROMPT,
        reply_markup=get_back_button("cancel_login"),
        parse_mode="Markdown",
    )
    await query.message.reply_text(
        "📱 أو اضغط هنا:",
        reply_markup=get_phone_keyboard(),
    )
    return WAITING_PHONE


# ─── استقبال رقم الهاتف ──────────────────────────────────────────────────────

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال رقم الجوال والتحقق منه، ثم إرسال رمز التحقق."""
    if update.message.contact:
        phone = update.message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    else:
        phone = update.message.text.strip()
        if not re.match(r"^\+\d{7,15}$", phone):
            await update.message.reply_text(
                "❌ صيغة الرقم غير صحيحة.\n"
                "مثال: `+966501234567`",
                parse_mode="Markdown",
                reply_markup=get_back_button("cancel_login"),
            )
            return WAITING_PHONE

    user_id = update.effective_user.id
    await update.message.reply_text(
        "⏳ جاري إرسال رمز التحقق...",
        reply_markup=ReplyKeyboardRemove(),
    )

    result = await auth_handler.send_code(user_id, phone)

    if not result.success:
        # فشل إرسال الرمز
        if result.state == LoginState.FAILED:
            # فشل نهائي (حساب محظور مثلاً)
            await update.message.reply_text(
                result.message,
                parse_mode="Markdown",
                reply_markup=get_login_keyboard(),
            )
            return ConversationHandler.END

        await update.message.reply_text(
            result.message,
            parse_mode="Markdown",
            reply_markup=get_back_button("cancel_login"),
        )
        return WAITING_PHONE

    # نجح الإرسال
    await user_service.update_phone(user_id, phone)
    await update.message.reply_text(
        LOGIN_CODE_PROMPT,
        parse_mode="Markdown",
        reply_markup=get_code_actions_keyboard(),
    )
    return WAITING_CODE


# ─── استقبال رمز التحقق ──────────────────────────────────────────────────────

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال رمز التحقق والتحقق منه."""
    code    = update.message.text.strip().replace(" ", "").replace("-", "")
    user_id = update.effective_user.id

    if not code.isdigit() or not (4 <= len(code) <= 8):
        await update.message.reply_text(
            "❌ الرمز يجب أن يتكون من أرقام فقط (4-8 أرقام).\n"
            "مثال: `12345`",
            parse_mode="Markdown",
            reply_markup=get_code_actions_keyboard(),
        )
        return WAITING_CODE

    await update.message.reply_text("⏳ جاري التحقق...")

    result = await auth_handler.verify_code(user_id, code)

    # ─ 2FA مطلوب ──────────────────────────────────────────────────────────
    if result.state == LoginState.WAIT_2FA:
        await update.message.reply_text(
            LOGIN_2FA_PROMPT,
            parse_mode="Markdown",
        )
        return WAITING_2FA

    # ─ تسجيل ناجح ──────────────────────────────────────────────────────────
    if result.state == LoginState.COMPLETED:
        return await _complete_login(update, context, result.extra["session"])

    # ─ فشل نهائي (تجاوز الحد الأقصى / auth restart) ────────────────────────
    if result.state in (LoginState.FAILED, LoginState.WAIT_PHONE):
        await update.message.reply_text(
            result.message,
            parse_mode="Markdown",
            reply_markup=get_login_keyboard(),
        )
        return ConversationHandler.END

    # ─ رمز منتهي الصلاحية أو خاطئ — يبقى في WAITING_CODE مع زر إعادة الإرسال
    await update.message.reply_text(
        result.message,
        parse_mode="Markdown",
        reply_markup=get_code_actions_keyboard(),
    )
    return WAITING_CODE


# ─── إعادة إرسال رمز التحقق ──────────────────────────────────────────────────

async def handle_resend_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر 🔄 إعادة إرسال الرمز أو أمر /resend_code."""
    # تحديد مصدر الطلب (callback أم command)
    if update.callback_query:
        query = update.callback_query
        await query.answer("⏳ جاري إعادة الإرسال...")
        send_fn = lambda text, **kw: query.message.reply_text(text, **kw)
    else:
        send_fn = lambda text, **kw: update.message.reply_text(text, **kw)

    user_id = update.effective_user.id
    result  = await auth_handler.resend_code(user_id)

    if not result.success:
        # فشل نهائي؟ أعِد للبداية
        if result.state in (LoginState.FAILED, LoginState.WAIT_PHONE):
            await send_fn(
                result.message,
                parse_mode="Markdown",
                reply_markup=get_login_keyboard(),
            )
            return ConversationHandler.END

        await send_fn(
            result.message,
            parse_mode="Markdown",
            reply_markup=get_code_actions_keyboard(),
        )
        return WAITING_CODE

    # نجح إعادة الإرسال
    await send_fn(
        LOGIN_CODE_RESENT,
        parse_mode="Markdown",
        reply_markup=get_code_actions_keyboard(),
    )
    return WAITING_CODE


# ─── استقبال كلمة مرور 2FA ───────────────────────────────────────────────────

async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال كلمة مرور التحقق بخطوتين."""
    password = update.message.text.strip()
    user_id  = update.effective_user.id

    await update.message.reply_text("⏳ جاري التحقق من كلمة المرور...")

    result = await auth_handler.verify_2fa(user_id, password)

    if result.state == LoginState.COMPLETED:
        return await _complete_login(update, context, result.extra["session"])

    if result.state in (LoginState.FAILED, LoginState.WAIT_PHONE):
        await update.message.reply_text(
            result.message,
            parse_mode="Markdown",
            reply_markup=get_login_keyboard(),
        )
        return ConversationHandler.END

    # كلمة مرور خاطئة أو انتظار — يبقى في WAITING_2FA
    await update.message.reply_text(
        result.message,
        parse_mode="Markdown",
    )
    return WAITING_2FA


# ─── إتمام تسجيل الدخول ──────────────────────────────────────────────────────

async def _complete_login(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: str
):
    """حفظ الجلسة، بدء Telethon client، وعرض القائمة الرئيسية."""
    user_id           = update.effective_user.id
    encrypted_session = encrypt_text(session)

    await user_service.save_session(user_id, encrypted_session)

    # بدء عميل Telethon للمستخدم
    from telethon_client.client import telethon_manager
    connected = await telethon_manager.create_and_start(user_id, encrypted_session)
    if not connected:
        logger.warning("_complete_login | Telethon client failed to start | user=%s", user_id)
        await update.message.reply_text(
            "⚠️ تم حفظ الجلسة لكن تعذر بدء العميل تلقائياً.\n"
            "سيُعاد المحاولة عند الاتصال القادم."
        )

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


# ─── الاشتراك الإجباري ───────────────────────────────────────────────────────

async def verify_subscription(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """التحقق من الاشتراك في القنوات الإجبارية."""
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


# ─── العودة للقائمة الرئيسية ─────────────────────────────────────────────────

async def handle_main_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """العودة للقائمة الرئيسية."""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user
    user = await user_service.get(tg_user.id)
    if user:
        await _show_main_menu(update, context, user)


# ─── إلغاء تسجيل الدخول ──────────────────────────────────────────────────────

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية تسجيل الدخول."""
    user_id = update.effective_user.id
    await auth_handler.cancel_auth(user_id)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ تم إلغاء تسجيل الدخول.",
            reply_markup=get_login_keyboard(),
        )
    else:
        await update.message.reply_text(
            "❌ تم إلغاء تسجيل الدخول.",
            reply_markup=get_login_keyboard(),
        )
    return ConversationHandler.END


# ─── ConversationHandler ──────────────────────────────────────────────────────

def get_auth_conversation_handler() -> ConversationHandler:
    """بناء ConversationHandler لعملية تسجيل الدخول."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_login, pattern="^start_login$"),
        ],
        states={
            WAITING_PHONE: [
                MessageHandler(
                    filters.CONTACT | (filters.TEXT & ~filters.COMMAND),
                    handle_phone,
                ),
            ],
            WAITING_CODE: [
                # زر إعادة الإرسال
                CallbackQueryHandler(handle_resend_code, pattern="^resend_code$"),
                # إدخال الرمز
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code),
            ],
            WAITING_2FA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_2fa),
            ],
            CHECKING_SUB: [
                CallbackQueryHandler(
                    verify_subscription, pattern="^verify_subscription$"
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_login, pattern="^cancel_login$"),
            CommandHandler("cancel", cancel_login),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
        # استمر في المحادثة حتى لو أرسل المستخدم رسالة غير متوقعة
        per_message=False,
    )


def get_resend_command_handler() -> CommandHandler:
    """
    Command handler مستقل لـ /resend_code.
    يُسجَّل خارج ConversationHandler ليعمل في أي وقت.
    """
    return CommandHandler("resend_code", handle_resend_code)

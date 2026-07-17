"""bot/bot_app.py — تهيئة وتشغيل بوت Telegram"""
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)
from config import config
from infrastructure.logger import get_logger

logger = get_logger("bot.app")


def build_application() -> Application:
    """بناء وتهيئة تطبيق البوت"""
    from telegram.request import HTTPXRequest
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = Application.builder().token(config.BOT_TOKEN).request(req).build()

    # ─── Import handlers ─────────────────────────────────────────
    from bot.handlers.start_handler import (
        start, handle_main_menu_callback, get_auth_conversation_handler,
        get_resend_command_handler, verify_subscription
    )
    from bot.handlers.stats_handler import (
        handle_stats_menu, handle_today_stats, handle_weekly_stats, handle_monthly_stats
    )
    from bot.handlers.customers_handler import (
        handle_customers_menu, handle_customer_detail,
        handle_customer_status_menu, handle_set_customer_status
    )
    from bot.handlers.channels_handler import (
        handle_channels_menu, handle_channel_detail,
        handle_toggle_channel, handle_delete_channel,
        handle_add_channel_start, handle_add_channel_input,
        WAITING_CHANNEL_USERNAME
    )
    from bot.handlers.ai_settings_handler import (
        handle_ai_menu, handle_toggle_ai, handle_select_provider,
        handle_set_provider, handle_set_api_key_start, handle_api_key_input,
        handle_ai_test, WAITING_API_KEY
    )
    from bot.handlers.system_handler import (
        handle_system_status, handle_start_system, handle_stop_system,
        handle_system_logs, handle_notifications_menu, handle_mark_all_read
    )
    from bot.handlers.developer_handler import (
        handle_developer_menu, handle_users_list, handle_user_detail,
        handle_ban_user, handle_unban_user, handle_suspend_user,
        handle_activate_user, handle_promote_user, handle_demote_user,
        handle_delete_user, handle_subscription_menu,
        handle_enable_subscription, handle_disable_subscription,
        handle_add_required_channel_start, handle_add_required_channel_input,
        handle_backup_now, WAITING_SUB_CHANNEL,
        handle_add_user_start, handle_add_user_input, WAITING_NEW_USER_ID
    )

    # ─── Auth Middleware ──────────────────────────────────────────
    async def auth_check(update: Update, context):
        """فحص سريع قبل كل طلب"""
        if not update.effective_user:
            return
        from services.user_service import UserService
        user_svc = UserService()
        if await user_svc.is_banned(update.effective_user.id):
            from bot.messages.templates import BANNED_MESSAGE
            if update.callback_query:
                await update.callback_query.answer(BANNED_MESSAGE, show_alert=True)
            elif update.message:
                await update.message.reply_text(BANNED_MESSAGE)
            return

    # ─── /start command ────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))

    # /resend_code — يعمل خارج ConversationHandler أيضاً
    app.add_handler(get_resend_command_handler())

    # ─── Login ConversationHandler ────────────────────────────────
    app.add_handler(get_auth_conversation_handler())

    # ─── Add Channel ConversationHandler ─────────────────────────
    add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_add_channel_start, pattern="^add_channel$")],
        states={
            WAITING_CHANNEL_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_channel_input)
            ],
        },
        fallbacks=[CallbackQueryHandler(handle_channels_menu, pattern="^channels_menu$")],
        allow_reentry=True,
    )
    app.add_handler(add_channel_conv)

    # ─── AI Key ConversationHandler ───────────────────────────────
    ai_key_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_set_api_key_start, pattern="^ai_set_key$")],
        states={
            WAITING_API_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_key_input)
            ],
        },
        fallbacks=[CallbackQueryHandler(handle_ai_menu, pattern="^ai_menu$")],
        allow_reentry=True,
    )
    app.add_handler(ai_key_conv)

    # ─── Required Channel ConversationHandler ─────────────────────
    req_ch_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_add_required_channel_start, pattern="^dev_sub_add$")],
        states={
            WAITING_SUB_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_required_channel_input)
            ],
        },
        fallbacks=[CallbackQueryHandler(handle_subscription_menu, pattern="^dev_subscription$")],
        allow_reentry=True,
    )
    app.add_handler(req_ch_conv)

    # ─── Add User ConversationHandler (Developer) ────────────────
    add_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_add_user_start, pattern="^dev_add_user$")],
        states={
            WAITING_NEW_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_user_input)
            ],
        },
        fallbacks=[CallbackQueryHandler(handle_users_list, pattern="^dev_users")],
        allow_reentry=True,
    )
    app.add_handler(add_user_conv)

    # ─── Callback Query Handlers ──────────────────────────────────
    # Navigation
    app.add_handler(CallbackQueryHandler(handle_main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))

    # Stats
    app.add_handler(CallbackQueryHandler(handle_stats_menu, pattern="^stats_menu$"))
    app.add_handler(CallbackQueryHandler(handle_today_stats, pattern="^stats_today$"))
    app.add_handler(CallbackQueryHandler(handle_weekly_stats, pattern="^stats_week$"))
    app.add_handler(CallbackQueryHandler(handle_monthly_stats, pattern="^stats_month$"))

    # Customers
    app.add_handler(CallbackQueryHandler(handle_customers_menu, pattern="^customers_menu$"))
    app.add_handler(CallbackQueryHandler(handle_customers_menu, pattern=r"^customers_page_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_customer_detail, pattern=r"^customer_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_customer_status_menu, pattern=r"^cust_status_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_set_customer_status, pattern=r"^set_cstatus_\d+_\w+$"))

    # Channels
    app.add_handler(CallbackQueryHandler(handle_channels_menu, pattern="^channels_menu$"))
    app.add_handler(CallbackQueryHandler(handle_channel_detail, pattern=r"^channel_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_toggle_channel, pattern=r"^ch_(enable|disable)_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_delete_channel, pattern=r"^ch_delete_\d+$"))

    # AI Settings
    app.add_handler(CallbackQueryHandler(handle_ai_menu, pattern="^ai_menu$"))
    app.add_handler(CallbackQueryHandler(handle_toggle_ai, pattern="^ai_(enable|disable)$"))
    app.add_handler(CallbackQueryHandler(handle_select_provider, pattern="^ai_select_provider$"))
    app.add_handler(CallbackQueryHandler(handle_set_provider, pattern=r"^ai_prov_\w+$"))
    app.add_handler(CallbackQueryHandler(handle_ai_test, pattern="^ai_test$"))

    # System
    app.add_handler(CallbackQueryHandler(handle_system_status, pattern="^system_status$"))
    app.add_handler(CallbackQueryHandler(handle_start_system, pattern="^system_start$"))
    app.add_handler(CallbackQueryHandler(handle_stop_system, pattern="^system_stop$"))
    app.add_handler(CallbackQueryHandler(handle_system_logs, pattern="^system_logs$"))

    # Notifications
    app.add_handler(CallbackQueryHandler(handle_notifications_menu, pattern="^notifications_menu$"))
    app.add_handler(CallbackQueryHandler(handle_mark_all_read, pattern="^notif_mark_all_read$"))

    # Developer
    app.add_handler(CallbackQueryHandler(handle_developer_menu, pattern="^developer_menu$"))
    app.add_handler(CallbackQueryHandler(handle_users_list, pattern=r"^dev_users_list_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_users_list, pattern="^dev_users$"))
    app.add_handler(CallbackQueryHandler(handle_user_detail, pattern=r"^dev_user_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_ban_user, pattern=r"^dev_ban_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_unban_user, pattern=r"^dev_unban_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_suspend_user, pattern=r"^dev_suspend_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_activate_user, pattern=r"^dev_activate_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_promote_user, pattern=r"^dev_promote_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_demote_user, pattern=r"^dev_demote_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_delete_user, pattern=r"^dev_delete_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_subscription_menu, pattern="^dev_subscription$"))
    app.add_handler(CallbackQueryHandler(handle_enable_subscription, pattern="^dev_sub_enable$"))
    app.add_handler(CallbackQueryHandler(handle_disable_subscription, pattern="^dev_sub_disable$"))
    app.add_handler(CallbackQueryHandler(handle_backup_now, pattern="^dev_backup$"))

    # Subscription verify
    app.add_handler(CallbackQueryHandler(verify_subscription, pattern="^verify_subscription$"))

    # ─── Error Handler ────────────────────────────────────────────
    async def error_handler(update, context):
        logger.error(f"Bot error: {context.error}", exc_info=context.error)
        if update and update.callback_query:
            try:
                await update.callback_query.answer("❌ حدث خطأ. حاول مرة أخرى.", show_alert=True)
            except Exception:
                pass

    app.add_error_handler(error_handler)

    logger.info("✅ تطبيق البوت جاهز")
    return app

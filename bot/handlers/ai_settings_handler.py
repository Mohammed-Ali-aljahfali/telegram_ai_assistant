"""bot/handlers/ai_settings_handler.py — معالج إعدادات الذكاء الاصطناعي"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from services.ai_service import AIService
from services.settings_service import SettingsService
from bot.keyboards.main_keyboard import get_back_button
from infrastructure.logger import get_logger

logger = get_logger("bot.ai_settings")
ai_service = AIService()
settings_service = SettingsService()

WAITING_API_KEY = 30
WAITING_PROMPT = 31
WAITING_TEST_MSG = 32


async def handle_ai_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    provider = await settings_service.get("ai_provider", user_id) or "openai"
    model = await settings_service.get("ai_model", user_id) or "gpt-4o-mini"
    ai_enabled = await settings_service.is_ai_enabled(user_id)
    temp = await settings_service.get_ai_temperature(user_id)

    toggle_label = "🔴 تعطيل AI" if ai_enabled else "🟢 تفعيل AI"
    toggle_cb = "ai_disable" if ai_enabled else "ai_enable"

    text = f"""🤖 *إعدادات الذكاء الاصطناعي*

المزود: `{provider}`
النموذج: `{model}`
الحالة: {'🟢 مفعّل' if ai_enabled else '🔴 معطّل'}
درجة الحرارة: `{temp}`
"""
    buttons = [
        [InlineKeyboardButton(toggle_label, callback_data=toggle_cb)],
        [
            InlineKeyboardButton("🔌 اختيار المزود", callback_data="ai_select_provider"),
            InlineKeyboardButton("🔑 إضافة API Key", callback_data="ai_set_key"),
        ],
        [
            InlineKeyboardButton("📝 تعديل البرومبت", callback_data="ai_edit_prompt"),
            InlineKeyboardButton("🧪 اختبار AI", callback_data="ai_test"),
        ],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")


async def handle_toggle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    action = query.data   # ai_enable | ai_disable
    await settings_service.set("ai_enabled", action == "ai_enable", user_id)
    await handle_ai_menu(update, context)


async def handle_select_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    buttons = [
        [InlineKeyboardButton("🟢 OpenAI (GPT)", callback_data="ai_prov_openai")],
        [InlineKeyboardButton("🔵 Google Gemini", callback_data="ai_prov_gemini")],
        [InlineKeyboardButton("🟣 Anthropic Claude", callback_data="ai_prov_claude")],
        [InlineKeyboardButton("⚫ نموذج محلي (Ollama)", callback_data="ai_prov_local")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="ai_menu")],
    ]
    await query.edit_message_text(
        "🔌 *اختر مزود الذكاء الاصطناعي:*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# النموذج الافتراضي لكل مزود
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "claude": "claude-3-haiku-20240307",
    "local": "llama3",
}

async def handle_set_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    provider = query.data.split("_")[-1]   # openai | gemini | claude | local
    user_id = update.effective_user.id

    # ✅ حفظ المزود وإعادة تعيين النموذج الافتراضي الصحيح
    await settings_service.set("ai_provider", provider, user_id)
    default_model = _DEFAULT_MODELS.get(provider, "gemini-1.5-flash")
    await settings_service.set("ai_model", default_model, user_id)
    ai_service.clear_provider_cache(user_id)

    await query.answer(f"✅ تم اختيار {provider} | النموذج: {default_model}", show_alert=True)
    await handle_ai_menu(update, context)


async def handle_set_api_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    provider = await settings_service.get("ai_provider", user_id) or "openai"
    await query.edit_message_text(
        f"🔑 *إضافة API Key لـ {provider}*\n\nأرسل المفتاح:",
        reply_markup=get_back_button("ai_menu"),
        parse_mode="Markdown"
    )
    context.user_data["ai_key_provider"] = provider
    return WAITING_API_KEY


async def handle_api_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = update.message.text.strip()
    user_id = update.effective_user.id
    provider = context.user_data.get("ai_key_provider", "openai")

    from infrastructure.crypto import encrypt_text
    from database.repositories.settings_repository import SettingsRepository
    repo = SettingsRepository()
    await repo.set(f"{provider}_api_key", encrypt_text(api_key), user_id, category="ai")
    ai_service.clear_provider_cache(user_id)

    await update.message.reply_text(
        "✅ تم حفظ المفتاح بأمان.",
        reply_markup=get_back_button("ai_menu")
    )
    return ConversationHandler.END


async def handle_ai_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.edit_message_text("🧪 جاري اختبار الذكاء الاصطناعي...")
    success, msg = await ai_service.test(user_id)
    await query.edit_message_text(
        msg,
        reply_markup=get_back_button("ai_menu"),
        parse_mode="Markdown"
    )

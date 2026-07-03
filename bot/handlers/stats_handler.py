"""bot/handlers/stats_handler.py — معالج الإحصائيات"""
from telegram import Update
from telegram.ext import ContextTypes
from services.statistics_service import StatisticsService
from bot.keyboards.main_keyboard import get_back_button, get_home_and_back
from bot.messages.templates import format_stats_card
from infrastructure.logger import get_logger

logger = get_logger("bot.stats")
stats_service = StatisticsService()


async def handle_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    stats = await stats_service.get_dashboard(user_id)
    text = format_stats_card(stats)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 اليوم", callback_data="stats_today"),
            InlineKeyboardButton("📆 الأسبوع", callback_data="stats_week"),
            InlineKeyboardButton("🗓️ الشهر", callback_data="stats_month"),
        ],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_today_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    stats = await stats_service.get_dashboard(user_id)
    text = format_stats_card(stats, "اليوم")
    await query.edit_message_text(text, reply_markup=get_back_button("stats_menu"), parse_mode="Markdown")


async def handle_weekly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    weekly = await stats_service.get_period_stats(user_id, 7)
    stats = {"today": weekly, "total_customers": 0, "new_customers_today": 0}
    text = format_stats_card(stats, "آخر 7 أيام")
    await query.edit_message_text(text, reply_markup=get_back_button("stats_menu"), parse_mode="Markdown")


async def handle_monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    monthly = await stats_service.get_period_stats(user_id, 30)
    stats = {"today": monthly, "total_customers": 0, "new_customers_today": 0}
    text = format_stats_card(stats, "آخر 30 يوماً")
    await query.edit_message_text(text, reply_markup=get_back_button("stats_menu"), parse_mode="Markdown")

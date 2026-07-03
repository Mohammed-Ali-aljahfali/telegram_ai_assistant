"""bot/handlers/customers_handler.py — معالج إدارة العملاء"""
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.customer_service import CustomerService
from models.customer import CustomerStatus
from bot.keyboards.main_keyboard import get_back_button, get_home_and_back
from bot.messages.templates import format_customer_card
from infrastructure.logger import get_logger

logger = get_logger("bot.customers")
customer_service = CustomerService()
PER_PAGE = 8


async def handle_customers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    data = query.data  # customers_menu OR customers_page_2
    try:
        page = int(data.split("_page_")[-1]) if "_page_" in data else 1
    except Exception:
        page = 1

    customers, total = await customer_service.get_paginated(user_id, page, PER_PAGE)
    total_pages = max(1, math.ceil(total / PER_PAGE))

    buttons = []
    for c in customers:
        label = f"{c.status_emoji} {c.display_name} ({c.message_count} رسالة)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"customer_{c.id}")])

    # فلاتر
    buttons.append([
        InlineKeyboardButton("🆕 الجدد", callback_data="cust_filter_new"),
        InlineKeyboardButton("⭐ المهتمون", callback_data="cust_filter_interested"),
        InlineKeyboardButton("✅ المحوّلون", callback_data="cust_filter_converted"),
    ])

    # تصفح
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"customers_page_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"customers_page_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")])

    await query.edit_message_text(
        f"👥 *العملاء* — {total} عميل",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def handle_customer_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    customer_id = int(query.data.split("_")[-1])
    customer = await customer_service.get_by_id(customer_id)
    if not customer:
        await query.answer("❌ العميل غير موجود", show_alert=True)
        return

    text = format_customer_card(customer)
    if customer.notes:
        text += f"\n📝 *الملاحظات:*\n{customer.notes[:200]}"
    if customer.summary:
        text += f"\n\n📋 *الملخص:*\n{customer.summary[:300]}"

    buttons = [
        [
            InlineKeyboardButton("📊 تغيير الحالة", callback_data=f"cust_status_{customer_id}"),
            InlineKeyboardButton("📝 إضافة ملاحظة", callback_data=f"cust_note_{customer_id}"),
        ],
        [
            InlineKeyboardButton("📋 الملخص", callback_data=f"cust_summary_{customer_id}"),
            InlineKeyboardButton("💬 المحادثة", callback_data=f"cust_conv_{customer_id}"),
        ],
        [InlineKeyboardButton("🔙 العملاء", callback_data="customers_menu")],
    ]
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def handle_customer_status_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    customer_id = int(query.data.split("_")[-1])
    statuses = [
        ("🆕 جديد", CustomerStatus.NEW),
        ("🟢 نشط", CustomerStatus.ACTIVE),
        ("⭐ مهتم", CustomerStatus.INTERESTED),
        ("✅ محوّل", CustomerStatus.CONVERTED),
        ("❌ خسارة", CustomerStatus.LOST),
    ]
    buttons = [[
        InlineKeyboardButton(label, callback_data=f"set_cstatus_{customer_id}_{s.value}")
    ] for label, s in statuses]
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"customer_{customer_id}")])
    await query.edit_message_text(
        "📊 *اختر الحالة الجديدة للعميل:*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def handle_set_customer_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    customer_id = int(parts[-2])
    status_val = parts[-1]
    try:
        status = CustomerStatus(status_val)
        await customer_service.update_status(customer_id, status)
        await query.answer("✅ تم تحديث الحالة", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ {e}", show_alert=True)
    # إعادة تحميل بيانات العميل
    query.data = f"customer_{customer_id}"
    await handle_customer_detail(update, context)

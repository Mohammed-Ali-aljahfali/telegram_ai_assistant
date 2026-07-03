"""core/message_processor.py — معالج رسائل Telethon الواردة"""
from infrastructure.logger import get_logger

logger = get_logger("core.message_processor")


async def process_incoming_message(event, bot_user_id: int, bot_app, notification_service):
    """معالجة رسالة واردة عبر Telethon"""
    try:
        if not event.message or not event.message.text:
            return

        message_text = event.message.text
        chat_id = event.chat_id
        sender = await event.get_sender()

        if not sender:
            return

        sender_id = sender.id
        sender_name = getattr(sender, "first_name", str(sender_id))
        sender_username = getattr(sender, "username", None)

        logger.info(f"📨 رسالة من {sender_name} ({sender_id}) للمستخدم {bot_user_id}")

        # 1. حفظ العميل في قاعدة البيانات
        from services.customer_service import CustomerService
        customer_service = CustomerService()
        customer = await customer_service.get_or_create(
            bot_user_id=bot_user_id,
            telegram_id=sender_id,
            username=sender_username,
            first_name=sender_name,
        )

        # 2. حفظ المحادثة
        from database.repositories.chat_repository import ChatRepository
        from models.chat import Chat, ChatType
        chat_repo = ChatRepository()
        chat = await chat_repo.create_or_update(Chat(
            bot_user_id=bot_user_id,
            customer_id=customer.id,
            chat_id=chat_id,
            chat_type=ChatType.PRIVATE,
        ))

        # 3. حفظ الرسالة
        from database.repositories.message_repository import MessageRepository
        from models.message import Message, SenderType, MessageType
        msg_repo = MessageRepository()
        db_msg = await msg_repo.create(Message(
            chat_id=chat.id,
            telegram_msg_id=event.message.id,
            sender_id=sender_id,
            sender_type=SenderType.USER,
            content=message_text,
            message_type=MessageType.TEXT,
        ))

        # 4. تحديث الإحصائيات
        from services.statistics_service import StatisticsService
        stats = StatisticsService()
        await stats.record_message_received(bot_user_id)

        # 5. فحص الكلمات المفتاحية
        from database.repositories.keyword_repository import KeywordRepository
        kw_repo = KeywordRepository()
        matched_keywords = await kw_repo.check_message(message_text, bot_user_id)

        if matched_keywords:
            kw_names = ", ".join([kw.keyword for kw in matched_keywords[:3]])
            await notification_service.send(
                bot_user_id=bot_user_id,
                telegram_id=bot_user_id,
                type_="keyword",
                title="🔑 كلمة مفتاحية مكتشفة",
                content=f"وجدنا: {kw_names}\nمن: {sender_name}\nالرسالة: {message_text[:100]}"
            )

        # 6. الرد التلقائي بالذكاء الاصطناعي
        from services.settings_service import SettingsService
        settings = SettingsService()
        auto_reply = await settings.is_auto_reply_enabled(bot_user_id)
        ai_enabled = await settings.is_ai_enabled(bot_user_id)

        if auto_reply and ai_enabled and chat.auto_reply and chat.ai_enabled:
            await _send_ai_reply(event, bot_user_id, customer, chat, message_text, bot_app, notification_service)

        # 7. تنبيه العميل الجديد
        if customer.message_count <= 1:
            await notification_service.send(
                bot_user_id=bot_user_id,
                telegram_id=bot_user_id,
                type_="new_customer",
                title="👤 عميل جديد!",
                content=f"اسم: {customer.display_name}\nUsername: @{sender_username or 'غير محدد'}\nالرسالة: {message_text[:150]}"
            )
            await stats.record_new_customer(bot_user_id)

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)


async def _send_ai_reply(event, bot_user_id: int, customer, chat, message_text: str,
                          bot_app, notification_service):
    """إرسال رد الذكاء الاصطناعي"""
    try:
        from services.ai_service import AIService
        from database.repositories.message_repository import MessageRepository
        from database.repositories.ai_memory_repository import AIMemoryRepository
        from models.message import Message, SenderType, MessageType
        from ai.prompt_manager import PromptManager

        ai_service = AIService()
        msg_repo = MessageRepository()
        memory_repo = AIMemoryRepository()
        prompt_mgr = PromptManager()

        # جلب سياق المحادثة
        recent_msgs = await msg_repo.get_recent_for_chat(chat.id, limit=15)
        memory_context = await memory_repo.get_summary_context(customer.id)
        system_prompt = await prompt_mgr.get_system_prompt(bot_user_id)

        if memory_context:
            system_prompt = f"{system_prompt}\n\n{memory_context}"

        # تحويل الرسائل لتنسيق AI
        formatted = prompt_mgr.format_conversation(recent_msgs)

        # توليد الرد
        response = await ai_service.generate_response(bot_user_id, formatted, system_prompt)

        if not response:
            return

        # إرسال الرد عبر Telethon
        import asyncio
        await asyncio.sleep(1.5)   # تأخير طبيعي
        await event.reply(response)

        # حفظ رد البوت في قاعدة البيانات
        await msg_repo.create(Message(
            chat_id=chat.id,
            sender_id=bot_user_id,
            sender_type=SenderType.BOT,
            content=response,
            message_type=MessageType.TEXT,
            ai_analyzed=True,
        ))

        # تحديث الإحصائيات
        from services.statistics_service import StatisticsService
        stats = StatisticsService()
        await stats.record_message_sent(bot_user_id)
        await stats.record_ai_response(bot_user_id)

        logger.info(f"✅ رد AI أُرسل للعميل {customer.display_name}")

    except Exception as e:
        logger.error(f"خطأ في إرسال رد AI: {e}")

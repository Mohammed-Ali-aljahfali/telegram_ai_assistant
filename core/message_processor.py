"""core/message_processor.py — معالج رسائل Telethon الواردة

يقوم بفرز الرسائل وتفريعها إلى شات خاص أو قنوات مراقبة نشطة:
- الرسائل الخاصة: تحليل بالـ AI، حفظ الحقائق في الذاكرة، تحديث الإحصائيات، والرد التلقائي.
- القنوات والمجموعات: مراقبة للكلمات المفتاحية النشطة للمستخدم فقط (مع تجاهل غير المرقبة تماماً).
"""
from __future__ import annotations

from database.repositories.channel_repository import ChannelRepository
from database.repositories.chat_repository import ChatRepository
from database.repositories.keyword_repository import KeywordRepository
from database.repositories.message_repository import MessageRepository
from database.repositories.customer_repository import CustomerRepository
from database.repositories.ai_memory_repository import AIMemoryRepository
from services.customer_service import CustomerService
from services.statistics_service import StatisticsService
from services.settings_service import SettingsService
from services.ai_service import AIService
from models.chat import Chat, ChatType
from models.message import Message, SenderType, MessageType
from infrastructure.logger import get_logger

logger = get_logger("core.message_processor")

# ─── Singletons/مستودعات جاهزة الاستخدام ─────────────────────────────────────────
channel_repo = ChannelRepository()
chat_repo = ChatRepository()
kw_repo = KeywordRepository()
msg_repo = MessageRepository()
cust_repo = CustomerRepository()
memory_repo = AIMemoryRepository()
customer_service = CustomerService()
stats_service = StatisticsService()
settings_service = SettingsService()
ai_service = AIService()


async def process_incoming_message(event, bot_user_id: int, bot_app, notification_service) -> None:
    """معالجة رسالة واردة عبر Telethon وفرزها وتوجيهها حسب نوع المحادثة."""
    try:
        if not event.message or not event.message.text:
            return

        message_text = event.message.text
        chat_id = event.chat_id
        sender = await event.get_sender()

        # استبعاد الرسائل الصادرة من البوت نفسه أو الحساب الشخصي الصادرة
        if event.message.out:
            return

        # ─── 1. فرز قنوات ومجموعات المراقبة ────────────────────────────────────
        if event.is_channel or event.is_group:
            # التحقق هل القناة/المجموعة مضافة لقنوات المراقبة النشطة للمستخدم
            active_channels = await channel_repo.get_all_active(bot_user_id)
            monitored_ch = next((c for c in active_channels if c.channel_id == chat_id), None)
            
            if not monitored_ch:
                # القناة غير مراقبة أو متوقفة حالياً -> تجاهل تام
                return
            
            logger.info(f"📡 منشور جديد من قناة مراقبة [{monitored_ch.title}] للمستخدم {bot_user_id}")
            
            # تسجيل المحادثة
            chat = await chat_repo.create_or_update(Chat(
                bot_user_id=bot_user_id,
                customer_id=None,
                chat_id=chat_id,
                chat_type=ChatType.CHANNEL if event.is_channel else ChatType.GROUP,
                title=monitored_ch.title,
                username=monitored_ch.username
            ))
            
            # تسجيل الرسالة/المنشور
            sender_id = sender.id if sender else chat_id
            await msg_repo.create(Message(
                chat_id=chat.id,
                telegram_msg_id=event.message.id,
                sender_id=sender_id,
                sender_type=SenderType.USER,
                content=message_text,
                message_type=MessageType.TEXT
            ))
            
            # فحص الكلمات المفتاحية
            matched_keywords = await kw_repo.check_message(message_text, bot_user_id)
            if matched_keywords:
                kw_names = ", ".join([kw.keyword for kw in matched_keywords[:3]])
                await notification_service.send(
                    bot_user_id=bot_user_id,
                    telegram_id=bot_user_id,
                    type_="keyword",
                    title=f"🔔 تنبيه من قناة مراقبة: {chat.title}",
                    content=f"الكلمات المطابقة: {kw_names}\n\n📝 النص:\n{message_text[:200]}"
                )
            
            # تحديث تاريخ آخر فحص
            await channel_repo.update_last_checked(chat_id)
            return

        # ─── 2. فرز المحادثات الخاصة (Direct Messages) ─────────────────────────
        if event.is_private:
            if not sender:
                return
            
            # استبعاد البوتات الأخرى من المحادثات
            if getattr(sender, "bot", False):
                return

            sender_id = sender.id
            sender_name = getattr(sender, "first_name", None) or getattr(sender, "username", str(sender_id))
            sender_username = getattr(sender, "username", None)

            logger.info(f"📨 رسالة خاصة جديدة من {sender_name} ({sender_id}) للمستخدم {bot_user_id}")

            # أ. حفظ أو جلب العميل
            customer = await customer_service.get_or_create(
                bot_user_id=bot_user_id,
                telegram_id=sender_id,
                username=sender_username,
                first_name=sender_name,
            )

            # ب. حفظ المحادثة
            chat = await chat_repo.create_or_update(Chat(
                bot_user_id=bot_user_id,
                customer_id=customer.id,
                chat_id=chat_id,
                chat_type=ChatType.PRIVATE,
                title=sender_name,
                username=sender_username
            ))

            # ج. حفظ الرسالة
            db_msg = await msg_repo.create(Message(
                chat_id=chat.id,
                telegram_msg_id=event.message.id,
                sender_id=sender_id,
                sender_type=SenderType.USER,
                content=message_text,
                message_type=MessageType.TEXT
            ))

            # د. تحديث إحصائيات الرسائل الواردة
            await stats_service.record_message_received(bot_user_id)

            # هـ. فحص الكلمات المفتاحية
            matched_keywords = await kw_repo.check_message(message_text, bot_user_id)
            if matched_keywords:
                kw_names = ", ".join([kw.keyword for kw in matched_keywords[:3]])
                await notification_service.send(
                    bot_user_id=bot_user_id,
                    telegram_id=bot_user_id,
                    type_="keyword",
                    title="🔑 كلمة مفتاحية في خاص",
                    content=f"وجدنا: {kw_names}\nمن: {sender_name}\n\n📝 الرسالة: {message_text[:150]}"
                )

            # و. تنبيه العميل الجديد
            is_new_customer = customer.message_count <= 1
            if is_new_customer:
                await notification_service.send(
                    bot_user_id=bot_user_id,
                    telegram_id=bot_user_id,
                    type_="new_customer",
                    title="👤 عميل جديد!",
                    content=f"الاسم: {customer.display_name}\nالمعرف: @{sender_username or 'غير محدد'}\nالرسالة الأولى: {message_text[:150]}"
                )
                await stats_service.record_new_customer(bot_user_id)

            # ز. الرد التلقائي بالذكاء الاصطناعي مع تشغيل خط تحليل البيانات
            auto_reply_enabled = await settings_service.is_auto_reply_enabled(bot_user_id)
            ai_enabled = await settings_service.is_ai_enabled(bot_user_id)

            # تشغيل التحليل بالـ AI بالخلفية لعدم إبطاء الرد
            analysis = await ai_service.analyze_message(bot_user_id, message_text)
            if analysis:
                intent = analysis.get("intent", "general")
                sentiment = analysis.get("sentiment", "neutral")
                needs_human = analysis.get("needs_human", False)
                interest_score = float(analysis.get("interest_score", 0.0))
                is_important = needs_human or interest_score >= 7.0

                # تحديث تحليل الرسالة
                await msg_repo.update_analysis(db_msg.id, intent, sentiment, is_important)

                # تحديث اهتمام العميل ونوع الخدمة
                await cust_repo.update_interest_score(customer.id, interest_score)
                service_type = analysis.get("service_type")
                if service_type:
                    await cust_repo.update_service_type(customer.id, service_type)

                # حفظ الحقائق والملاحظات في ذاكرة الذكاء الاصطناعي
                key_points = analysis.get("key_points", [])
                for pt in key_points:
                    await memory_repo.store(
                        customer_id=customer.id,
                        bot_user_id=bot_user_id,
                        memory_type="fact",
                        content=pt,
                        importance=interest_score / 10.0 if interest_score else 0.5
                    )

            if auto_reply_enabled and ai_enabled and chat.auto_reply and chat.ai_enabled:
                await _send_ai_reply(event, bot_user_id, customer, chat, message_text, bot_app, notification_service)

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)


async def _send_ai_reply(event, bot_user_id: int, customer, chat, message_text: str,
                          bot_app, notification_service) -> None:
    """إرسال رد الذكاء الاصطناعي للمحادثات الخاصة."""
    try:
        from ai.prompt_manager import PromptManager
        prompt_mgr = PromptManager()

        # جلب سياق المحادثة المباشر والذاكرة المستخلصة
        recent_msgs = await msg_repo.get_recent_for_chat(chat.id, limit=15)
        memory_context = await memory_repo.get_summary_context(customer.id)
        system_prompt = await prompt_mgr.get_system_prompt(bot_user_id)

        if memory_context:
            system_prompt = f"{system_prompt}\n\n{memory_context}"

        # تنسيق المحادثة للذكاء الاصطناعي
        formatted = prompt_mgr.format_conversation(recent_msgs)

        # توليد الرد عبر AIService
        response = await ai_service.generate_response(bot_user_id, formatted, system_prompt)

        if not response:
            return

        # إرسال الرد
        import asyncio
        await asyncio.sleep(1.5)   # تأخير طبيعي لمحاكاة الكتابة البشرية
        await event.reply(response)

        # حفظ رد البوت بقاعدة البيانات
        await msg_repo.create(Message(
            chat_id=chat.id,
            sender_id=bot_user_id,
            sender_type=SenderType.BOT,
            content=response,
            message_type=MessageType.TEXT,
            ai_analyzed=True,
        ))

        # تحديث الإحصائيات للرسائل المرسلة والردود
        await stats_service.record_message_sent(bot_user_id)
        await stats_service.record_ai_response(bot_user_id)

        logger.info(f"✅ رد AI أُرسل للعميل {customer.display_name}")

    except Exception as e:
        logger.error(f"خطأ في إرسال رد AI: {e}")

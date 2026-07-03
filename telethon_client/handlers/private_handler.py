"""
Private Message Handler
=======================
Specialised handler for one-on-one conversations — the primary source of
customer interactions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message, User

logger = logging.getLogger(__name__)


class TelethonPrivateHandler:
    """
    Focused handler for private (1-on-1) Telegram conversations.

    Responsibilities
    ----------------
    - Detect conversation start / resumption.
    - Track "typing" state to appear natural before auto-replies.
    - Escalate to human when the AI confidence is low.
    - Mark conversations as read after processing.
    """

    def __init__(self) -> None:
        # Track active conversation sessions: chat_id -> stage
        self._conversation_state: dict[int, str] = {}
        # Prevent duplicate processing of the same message
        self._processed_ids: set[int] = set()

    async def register_handlers(
        self,
        client: TelegramClient,
        user_id: int,
        bot_app=None,
    ) -> None:
        """Register private-message–specific handlers."""

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def _on_private(event: events.NewMessage.Event) -> None:
            await self.handle_private_message(event, user_id, bot_app, client)

        logger.info("Registered private handlers for user_id=%s", user_id)

    async def handle_private_message(
        self,
        event: events.NewMessage.Event,
        user_id: int,
        bot_app=None,
        client: Optional[TelegramClient] = None,
    ) -> None:
        """
        Full private-message processing pipeline.

        Steps
        -----
        1. De-duplicate (skip already-processed message IDs).
        2. Extract sender and message data.
        3. Determine conversation stage (new / returning).
        4. Apply "is typing" indicator before auto-reply.
        5. Run AI pipeline.
        6. Auto-reply with generated response.
        7. Update conversation stage.
        8. Optionally notify bot user.
        """
        try:
            message: Message = event.message
            if message is None or message.out:
                return

            msg_id = message.id
            if msg_id in self._processed_ids:
                return
            self._processed_ids.add(msg_id)
            # Keep memory bounded
            if len(self._processed_ids) > 10_000:
                self._processed_ids = set(list(self._processed_ids)[-5_000:])

            sender = await event.get_sender()
            if sender is None:
                return
            if isinstance(sender, User) and sender.bot:
                return

            chat_id = event.chat_id
            message_text = message.text or ""

            sender_info = {
                "id": sender.id if hasattr(sender, "id") else None,
                "first_name": getattr(sender, "first_name", None),
                "last_name": getattr(sender, "last_name", None),
                "username": getattr(sender, "username", None),
                "phone": getattr(sender, "phone", None),
                "is_bot": getattr(sender, "bot", False),
            }

            stage = self._conversation_state.get(chat_id, "new")

            message_data = {
                "user_id": user_id,
                "chat_id": chat_id,
                "message_id": msg_id,
                "source": "private",
                "text": message_text,
                "sender": sender_info,
                "stage": stage,
                "date": message.date.isoformat() if message.date else None,
            }

            logger.debug(
                "Private message: user_id=%s, chat_id=%s, stage=%s, len=%d",
                user_id,
                chat_id,
                stage,
                len(message_text),
            )

            # ---- Check auto-reply setting ---------------------------
            auto_reply_enabled = await self._is_auto_reply_enabled(user_id, chat_id)

            # ---- Run AI pipeline ------------------------------------
            ai_result = await self._run_ai_pipeline(message_data, user_id)

            # ---- Auto-reply -----------------------------------------
            if auto_reply_enabled and ai_result:
                response_text = ai_result.get("response_text")
                confidence = ai_result.get("confidence", 1.0)

                if response_text and confidence >= 0.5:
                    # Simulate human typing delay
                    typing_duration = min(len(response_text) * 0.03, 4.0)
                    if client:
                        async with client.action(chat_id, "typing"):
                            await asyncio.sleep(typing_duration)

                    try:
                        await event.reply(response_text)
                        logger.info(
                            "Auto-replied in private chat: user_id=%s, chat_id=%s",
                            user_id,
                            chat_id,
                        )
                    except Exception as reply_exc:
                        logger.error("Auto-reply failed — %s", reply_exc)

                elif confidence < 0.5 and bot_app:
                    # Low-confidence — notify human to take over
                    await self._request_human_takeover(bot_app, user_id, message_data)

            # ---- Update conversation stage --------------------------
            if ai_result:
                new_stage = ai_result.get("conversation_stage", stage)
                self._conversation_state[chat_id] = new_stage

            # ---- Notify bot user ------------------------------------
            if bot_app and ai_result:
                importance = ai_result.get("importance", 0)
                interest = ai_result.get("interest_score", 0)
                if importance >= 7 or interest >= 7:
                    await self._notify_important(bot_app, user_id, message_data, ai_result)

        except Exception as exc:
            logger.error(
                "Unhandled error in handle_private_message: user_id=%s — %s",
                user_id,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _is_auto_reply_enabled(self, user_id: int, chat_id: int) -> bool:
        """Query the chat settings for auto-reply status."""
        try:
            from core.container import Container
            container = Container.get_instance()
            chat_service = getattr(container, "chat_service", None)
            if chat_service:
                return await chat_service.is_auto_reply_enabled(chat_id)
            return False
        except Exception:
            return False

    async def _run_ai_pipeline(self, message_data: dict, user_id: int) -> Optional[dict]:
        """Run the full agent pipeline."""
        try:
            from core.container import Container
            agent_manager = getattr(Container.get_instance(), "agent_manager", None)
            if agent_manager is None:
                return None
            return await agent_manager.process_message(message_data, user_id)
        except Exception as exc:
            logger.warning("AI pipeline error in private handler — %s", exc)
            return None

    async def _request_human_takeover(
        self, bot_app, user_id: int, message_data: dict
    ) -> None:
        """Notify the bot user that manual intervention is needed."""
        try:
            sender = message_data.get("sender", {})
            name = sender.get("first_name") or sender.get("username") or "مجهول"
            text = (message_data.get("text") or "")[:100]
            notification = (
                f"⚠️ *يحتاج تدخل بشري*\n"
                f"👤 العميل: {name}\n"
                f"💬 الرسالة: {text}\n\n"
                f"الذكاء الاصطناعي غير واثق من الرد — يرجى المتابعة يدوياً."
            )
            await bot_app.bot.send_message(
                chat_id=user_id,
                text=notification,
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.warning("Failed to send human takeover notification — %s", exc)

    async def _notify_important(
        self, bot_app, user_id: int, message_data: dict, ai_result: dict
    ) -> None:
        """Send a high-priority notification to the bot user."""
        try:
            sender = message_data.get("sender", {})
            name = sender.get("first_name") or sender.get("username") or "مجهول"
            intent = ai_result.get("intent", "عام")
            interest = ai_result.get("interest_score", 0)
            text = (message_data.get("text") or "")[:150]

            notification = (
                f"🔥 *رسالة عالية الأهمية!*\n"
                f"👤 {name}\n"
                f"🎯 النية: {intent}\n"
                f"⭐ مستوى الاهتمام: {interest}/10\n"
                f"📝 {text}"
            )
            await bot_app.bot.send_message(
                chat_id=user_id,
                text=notification,
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.warning("Failed to send important notification — %s", exc)

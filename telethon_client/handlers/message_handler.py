"""
Telethon Message Handler
========================
Registers Telethon NewMessage event handlers on a user's client and routes
incoming messages through the AI processing pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from telethon import TelegramClient, events
from telethon.tl.types import (
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerChannel,
    PeerChat,
    PeerUser,
    User,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TelethonMessageHandler:
    """
    Registers and manages Telethon ``NewMessage`` event handlers.

    A separate instance of this class is created per user so that the
    ``user_id`` closure is always correct.
    """

    def __init__(self) -> None:
        self._registered_handlers: list = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_handlers(
        self,
        client: TelegramClient,
        user_id: int,
        bot_app=None,
    ) -> None:
        """
        Attach event handlers to *client*.

        Parameters
        ----------
        client:
            The user's live :class:`TelegramClient`.
        user_id:
            Bot user ID — used to scope database writes and notifications.
        bot_app:
            python-telegram-bot ``Application`` instance, or ``None``.
        """

        # Private messages (not from ourselves)
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def _on_private_message(event: events.NewMessage.Event) -> None:
            await self.handle_new_message(event, user_id, bot_app, source="private")

        # Group / supergroup messages
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_group))
        async def _on_group_message(event: events.NewMessage.Event) -> None:
            await self.handle_new_message(event, user_id, bot_app, source="group")

        # Channel posts
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_channel))
        async def _on_channel_post(event: events.NewMessage.Event) -> None:
            await self.handle_new_message(event, user_id, bot_app, source="channel")

        self._registered_handlers.extend([
            _on_private_message,
            _on_group_message,
            _on_channel_post,
        ])

        logger.info(
            "Registered Telethon message handlers for user_id=%s", user_id
        )

    # ------------------------------------------------------------------
    # Core handler
    # ------------------------------------------------------------------

    async def handle_new_message(
        self,
        event: events.NewMessage.Event,
        user_id: int,
        bot_app=None,
        source: str = "private",
    ) -> None:
        """
        Process a single incoming Telegram message.

        Pipeline
        --------
        1. Extract metadata from the event.
        2. Skip messages we should ignore (outgoing, bots, etc.).
        3. Save the raw message to the database.
        4. Run AI analysis via the AgentManager.
        5. Optionally auto-reply if enabled for this chat.
        6. Forward a notification to the bot user.
        """
        try:
            message: Message = event.message
            if message is None:
                return

            # ---- Skip outgoing messages -----------------------------
            if message.out:
                return

            # ---- Extract sender info --------------------------------
            sender = await event.get_sender()
            if sender is None:
                return

            # Skip messages from bots
            if isinstance(sender, User) and sender.bot:
                return

            chat = await event.get_chat()
            chat_id = event.chat_id
            message_text = message.text or ""
            message_id = message.id

            sender_info = _extract_sender_info(sender)
            media_type = _detect_media_type(message)

            logger.debug(
                "New %s message: user_id=%s, chat_id=%s, sender=%s, len=%d",
                source,
                user_id,
                chat_id,
                sender_info.get("id"),
                len(message_text),
            )

            # ---- Build message payload ------------------------------
            message_data = {
                "user_id": user_id,
                "chat_id": chat_id,
                "message_id": message_id,
                "source": source,
                "text": message_text,
                "media_type": media_type,
                "sender": sender_info,
                "date": message.date.isoformat() if message.date else None,
                "reply_to_msg_id": message.reply_to_msg_id,
                "forward_from": _extract_forward_info(message),
            }

            # ---- Step 1: Save to database ---------------------------
            await self._save_message_to_db(message_data, user_id)

            # ---- Step 2: AI analysis --------------------------------
            ai_result = await self._run_ai_pipeline(message_data, user_id, bot_app)

            # ---- Step 3: Auto-reply ---------------------------------
            if ai_result and ai_result.get("should_auto_reply") and source == "private":
                reply_text = ai_result.get("response_text")
                if reply_text:
                    try:
                        await asyncio.sleep(1)  # Small delay for natural feel
                        await event.reply(reply_text)
                        logger.debug(
                            "Auto-replied to chat_id=%s for user_id=%s", chat_id, user_id
                        )
                    except Exception as reply_exc:
                        logger.error("Failed to auto-reply — %s", reply_exc)

            # ---- Step 4: Notify bot user ----------------------------
            if bot_app and ai_result:
                await self._notify_bot_user(
                    bot_app, user_id, message_data, ai_result
                )

        except Exception as exc:
            logger.error(
                "Unhandled error in handle_new_message for user_id=%s — %s",
                user_id,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _save_message_to_db(self, message_data: dict, user_id: int) -> None:
        """Persist the raw message to the database (best-effort)."""
        try:
            # Lazy import to avoid circular dependencies
            from core.container import Container
            db = Container.get_instance().db_manager
            if db is None:
                return

            await db.execute(
                """
                INSERT INTO messages
                    (user_id, chat_id, message_id, source, text, media_type,
                     sender_id, sender_username, sender_first_name, date_sent, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::timestamptz, NOW())
                ON CONFLICT (user_id, chat_id, message_id) DO NOTHING
                """,
                user_id,
                message_data["chat_id"],
                message_data["message_id"],
                message_data["source"],
                message_data.get("text", ""),
                message_data.get("media_type"),
                message_data["sender"].get("id"),
                message_data["sender"].get("username"),
                message_data["sender"].get("first_name"),
                message_data.get("date"),
            )
        except Exception as exc:
            logger.warning("Could not save message to DB — %s", exc)

    async def _run_ai_pipeline(
        self,
        message_data: dict,
        user_id: int,
        bot_app=None,
    ) -> Optional[dict]:
        """Invoke the AgentManager pipeline (best-effort)."""
        try:
            from core.container import Container
            container = Container.get_instance()
            agent_manager = getattr(container, "agent_manager", None)
            if agent_manager is None:
                return None
            return await agent_manager.process_message(message_data, user_id)
        except Exception as exc:
            logger.warning("AI pipeline error — %s", exc)
            return None

    async def _notify_bot_user(
        self,
        bot_app,
        user_id: int,
        message_data: dict,
        ai_result: dict,
    ) -> None:
        """Send a Telegram bot notification to the bot user (best-effort)."""
        try:
            importance = ai_result.get("importance", 0)
            intent = ai_result.get("intent", "general")
            interest = ai_result.get("interest_score", 0)

            # Only notify for important messages
            if importance < 5 and interest < 6:
                return

            sender = message_data.get("sender", {})
            sender_name = sender.get("first_name") or sender.get("username") or "Unknown"
            text_preview = (message_data.get("text") or "")[:100]

            notification = (
                f"📨 *رسالة جديدة مهمة*\n"
                f"👤 من: {sender_name}\n"
                f"💬 النية: {intent}\n"
                f"⭐ الاهتمام: {interest}/10\n"
                f"📝 {text_preview}{'...' if len(text_preview) == 100 else ''}"
            )

            await bot_app.bot.send_message(
                chat_id=user_id,
                text=notification,
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.warning("Failed to send bot notification — %s", exc)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _extract_sender_info(sender) -> dict:
    """Extract a simple dict from a Telethon User / Channel entity."""
    if isinstance(sender, User):
        return {
            "id": sender.id,
            "first_name": sender.first_name,
            "last_name": sender.last_name,
            "username": sender.username,
            "is_bot": sender.bot,
            "phone": sender.phone,
        }
    return {
        "id": getattr(sender, "id", None),
        "first_name": None,
        "last_name": None,
        "username": getattr(sender, "username", None),
        "is_bot": False,
        "phone": None,
    }


def _detect_media_type(message: Message) -> Optional[str]:
    """Return a human-readable media type string or ``None``."""
    if message.photo:
        return "photo"
    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if doc:
            for attr in doc.attributes:
                type_name = type(attr).__name__
                if "Video" in type_name:
                    return "video"
                if "Audio" in type_name:
                    return "audio"
                if "Sticker" in type_name:
                    return "sticker"
        return "document"
    if message.geo:
        return "location"
    if message.contact:
        return "contact"
    return None


def _extract_forward_info(message: Message) -> Optional[dict]:
    """Extract forward metadata if the message is forwarded."""
    fwd = message.fwd_from
    if fwd is None:
        return None
    return {
        "from_id": getattr(fwd.from_id, "user_id", None),
        "from_name": fwd.from_name,
        "date": fwd.date.isoformat() if fwd.date else None,
    }

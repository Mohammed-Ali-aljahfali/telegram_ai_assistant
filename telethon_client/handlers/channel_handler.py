"""
Channel Handler
===============
Monitors subscribed channels for new posts and keywords.
"""

from __future__ import annotations

import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Message

logger = logging.getLogger(__name__)


class TelethonChannelHandler:
    """
    Handles incoming posts from Telegram channels the user has joined for
    monitoring purposes.

    Unlike private-message handlers, channel posts are not auto-replied to —
    instead, the handler scans for keyword matches and fires notifications.
    """

    def __init__(self) -> None:
        self._keywords_cache: dict[int, list[str]] = {}  # user_id -> keywords

    async def register_handlers(
        self,
        client: TelegramClient,
        user_id: int,
        bot_app=None,
    ) -> None:
        """Attach channel post handlers to *client*."""

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_channel and not e.is_group))
        async def _on_channel_post(event: events.NewMessage.Event) -> None:
            await self.handle_channel_post(event, user_id, bot_app)

        logger.info("Registered channel handlers for user_id=%s", user_id)

    async def handle_channel_post(
        self,
        event: events.NewMessage.Event,
        user_id: int,
        bot_app=None,
    ) -> None:
        """
        Process a channel post.

        1. Check if the channel is in the user's monitored list.
        2. Save the post to the database.
        3. Scan for keyword matches.
        4. Notify the bot user if a keyword matches or the post is important.
        """
        try:
            message: Message = event.message
            if message is None or message.out:
                return

            chat = await event.get_chat()
            if not isinstance(chat, Channel):
                return

            channel_id = chat.id
            channel_title = chat.title or str(channel_id)
            post_text = message.text or ""

            logger.debug(
                "Channel post: user_id=%s, channel=%s, len=%d",
                user_id,
                channel_title,
                len(post_text),
            )

            # Check if channel is monitored
            if not await self._is_monitored(user_id, channel_id):
                return

            # Save to database
            await self._save_channel_post(
                user_id, channel_id, channel_title, message
            )

            # Keyword matching
            matched_keywords = await self._check_keywords(user_id, post_text)

            if bot_app and matched_keywords:
                preview = post_text[:200]
                notification = (
                    f"🔔 *تنبيه من قناة {channel_title}*\n"
                    f"🔑 الكلمات المطابقة: {', '.join(matched_keywords)}\n\n"
                    f"📝 {preview}{'...' if len(post_text) > 200 else ''}"
                )
                try:
                    await bot_app.bot.send_message(
                        chat_id=user_id,
                        text=notification,
                        parse_mode="Markdown",
                    )
                except Exception as notify_exc:
                    logger.warning("Failed to notify for channel post — %s", notify_exc)

        except Exception as exc:
            logger.error(
                "Error handling channel post for user_id=%s — %s",
                user_id,
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _is_monitored(self, user_id: int, channel_id: int) -> bool:
        """Return True if *channel_id* is in the user's monitored channel list."""
        try:
            from core.container import Container
            db = Container.get_instance().db_manager
            if db is None:
                return False
            row = await db.fetchrow(
                """
                SELECT 1 FROM monitored_channels
                WHERE user_id = $1 AND channel_id = $2 AND is_active = TRUE
                """,
                user_id,
                channel_id,
            )
            return row is not None
        except Exception as exc:
            logger.warning("Could not check monitored channels — %s", exc)
            return False

    async def _save_channel_post(
        self,
        user_id: int,
        channel_id: int,
        channel_title: str,
        message: Message,
    ) -> None:
        """Persist a channel post to the database."""
        try:
            from core.container import Container
            db = Container.get_instance().db_manager
            if db is None:
                return
            await db.execute(
                """
                INSERT INTO channel_posts
                    (user_id, channel_id, channel_title, message_id, text, date_posted, created_at)
                VALUES ($1, $2, $3, $4, $5, $6::timestamptz, NOW())
                ON CONFLICT (user_id, channel_id, message_id) DO NOTHING
                """,
                user_id,
                channel_id,
                channel_title,
                message.id,
                message.text or "",
                message.date.isoformat() if message.date else None,
            )
        except Exception as exc:
            logger.warning("Could not save channel post — %s", exc)

    async def _check_keywords(self, user_id: int, text: str) -> list[str]:
        """Return a list of monitored keywords that appear in *text*."""
        try:
            from core.container import Container
            db = Container.get_instance().db_manager
            if db is None:
                return []

            # Cache keywords per user to reduce DB hits
            if user_id not in self._keywords_cache:
                rows = await db.fetch(
                    "SELECT keyword FROM channel_keywords WHERE user_id = $1",
                    user_id,
                )
                self._keywords_cache[user_id] = [r["keyword"].lower() for r in rows]

            keywords = self._keywords_cache[user_id]
            text_lower = text.lower()
            return [kw for kw in keywords if kw in text_lower]
        except Exception as exc:
            logger.warning("Keyword check failed — %s", exc)
            return []

    def invalidate_keywords_cache(self, user_id: int) -> None:
        """Force a fresh keyword fetch on next message."""
        self._keywords_cache.pop(user_id, None)

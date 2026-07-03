"""database/repositories/channel_repository.py — مستودع القنوات"""
from datetime import datetime
from typing import Optional
from database.connection import get_db
from models.chat import Channel, RequiredChannel
from infrastructure.logger import get_logger

logger = get_logger("channel_repo")


class ChannelRepository:

    def __init__(self):
        self.db = get_db()

    async def add_channel(self, channel: Channel) -> Channel:
        uid = await self.db.execute(
            """INSERT OR REPLACE INTO monitored_channels
               (bot_user_id, channel_id, username, title, channel_type, is_active, auto_reply, keywords_only)
               VALUES (?,?,?,?,?,?,?,?)""",
            (channel.bot_user_id, channel.channel_id, channel.username,
             channel.title, channel.channel_type,
             1 if channel.is_active else 0,
             1 if channel.auto_reply else 0,
             1 if channel.keywords_only else 0)
        )
        channel.id = uid
        return channel

    async def remove_channel(self, bot_user_id: int, channel_id: int):
        await self.db.execute(
            "DELETE FROM monitored_channels WHERE bot_user_id=? AND channel_id=?",
            (bot_user_id, channel_id)
        )

    async def get_all_active(self, bot_user_id: int) -> list[Channel]:
        rows = await self.db.fetchall(
            "SELECT * FROM monitored_channels WHERE bot_user_id=? AND is_active=1",
            (bot_user_id,)
        )
        return [self._row_to_channel(r) for r in rows]

    async def get_all_for_user(self, bot_user_id: int) -> list[Channel]:
        rows = await self.db.fetchall(
            "SELECT * FROM monitored_channels WHERE bot_user_id=? ORDER BY added_at DESC",
            (bot_user_id,)
        )
        return [self._row_to_channel(r) for r in rows]

    async def toggle_active(self, bot_user_id: int, channel_id: int, active: bool):
        await self.db.execute(
            "UPDATE monitored_channels SET is_active=? WHERE bot_user_id=? AND channel_id=?",
            (1 if active else 0, bot_user_id, channel_id)
        )

    async def update_last_checked(self, channel_id: int):
        await self.db.execute(
            "UPDATE monitored_channels SET last_checked=? WHERE channel_id=?",
            (datetime.now(), channel_id)
        )

    # ─── Required Channels ───────────────────────────────────────

    async def add_required_channel(self, channel: RequiredChannel) -> RequiredChannel:
        uid = await self.db.execute(
            """INSERT INTO required_channels
               (channel_id, channel_username, title, channel_type, is_active, added_by)
               VALUES (?,?,?,?,?,?)""",
            (channel.channel_id, channel.channel_username, channel.title,
             channel.channel_type, 1 if channel.is_active else 0, channel.added_by)
        )
        channel.id = uid
        return channel

    async def remove_required_channel(self, channel_id: int):
        await self.db.execute(
            "DELETE FROM required_channels WHERE channel_id=?", (channel_id,)
        )

    async def get_required_channels(self) -> list[RequiredChannel]:
        rows = await self.db.fetchall(
            "SELECT * FROM required_channels WHERE is_active=1 ORDER BY added_at DESC"
        )
        return [self._row_to_required(r) for r in rows]

    async def get_all_required_channels(self) -> list[RequiredChannel]:
        rows = await self.db.fetchall(
            "SELECT * FROM required_channels ORDER BY added_at DESC"
        )
        return [self._row_to_required(r) for r in rows]

    async def toggle_required_channel(self, channel_id: int, active: bool):
        await self.db.execute(
            "UPDATE required_channels SET is_active=? WHERE channel_id=?",
            (1 if active else 0, channel_id)
        )

    def _row_to_channel(self, row) -> Channel:
        d = dict(row)
        d["is_active"] = bool(d.get("is_active", 1))
        d["auto_reply"] = bool(d.get("auto_reply", 0))
        d["keywords_only"] = bool(d.get("keywords_only", 1))
        return Channel(**d)

    def _row_to_required(self, row) -> RequiredChannel:
        d = dict(row)
        d["is_active"] = bool(d.get("is_active", 1))
        return RequiredChannel(**d)

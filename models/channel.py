"""
Channel models – MonitoredChannel and RequiredChannel.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ChannelStatus(str, Enum):
    """Operational status of a channel entry."""

    ACTIVE = "active"
    PAUSED = "paused"
    REMOVED = "removed"
    ERROR = "error"


class MonitoredChannel(BaseModel):
    """
    A Telegram channel whose messages are scraped / monitored for leads.

    Attributes:
        id: Internal database primary key.
        owner_telegram_id: BotUser who added this channel.
        channel_id: Telegram channel ID (typically negative).
        channel_username: Public @username of the channel.
        channel_title: Display title of the channel.
        status: Monitoring status.
        filter_keywords: Optional list of keywords to filter messages by.
        last_checked_at: When the channel was last scraped.
        messages_scraped: Running total of messages fetched.
        created_at: When this record was created.
    """

    model_config = {"from_attributes": True}

    id: Optional[int] = None
    owner_telegram_id: int = Field(..., gt=0)
    channel_id: Optional[int] = None
    channel_username: Optional[str] = Field(default=None, max_length=64)
    channel_title: Optional[str] = Field(default=None, max_length=256)
    status: ChannelStatus = ChannelStatus.ACTIVE
    filter_keywords: list[str] = Field(default_factory=list)
    last_checked_at: Optional[datetime] = None
    messages_scraped: int = Field(default=0, ge=0)
    created_at: Optional[datetime] = None

    @field_validator("channel_username", mode="before")
    @classmethod
    def strip_at(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str):
            return v.lstrip("@").strip() or None
        return v

    @field_validator("filter_keywords", mode="before")
    @classmethod
    def parse_keywords(cls, v: Any) -> list[str]:
        import json

        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return [k.strip() for k in v.split(",") if k.strip()]
        return v if isinstance(v, list) else []

    def to_db_dict(self) -> dict[str, Any]:
        import json

        return {
            "owner_telegram_id": self.owner_telegram_id,
            "channel_id": self.channel_id,
            "channel_username": self.channel_username,
            "channel_title": self.channel_title,
            "status": self.status.value,
            "filter_keywords": json.dumps(self.filter_keywords),
            "last_checked_at": (
                self.last_checked_at.isoformat() if self.last_checked_at else None
            ),
            "messages_scraped": self.messages_scraped,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "MonitoredChannel":
        import json

        data = dict(row)
        if isinstance(data.get("filter_keywords"), str):
            try:
                data["filter_keywords"] = json.loads(data["filter_keywords"])
            except (json.JSONDecodeError, TypeError):
                data["filter_keywords"] = []
        return cls(**data)


class RequiredChannel(BaseModel):
    """
    A channel that users must join before the bot will respond to them.

    Attributes:
        id: Internal primary key.
        channel_id: Telegram channel ID.
        channel_username: @username of the required channel.
        channel_title: Display title.
        is_active: Whether this requirement is currently enforced.
        created_at: When this record was created.
    """

    model_config = {"from_attributes": True}

    id: Optional[int] = None
    channel_id: Optional[int] = None
    channel_username: Optional[str] = Field(default=None, max_length=64)
    channel_title: Optional[str] = Field(default=None, max_length=256)
    is_active: bool = True
    created_at: Optional[datetime] = None

    @field_validator("channel_username", mode="before")
    @classmethod
    def strip_at(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str):
            return v.lstrip("@").strip() or None
        return v

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "channel_username": self.channel_username,
            "channel_title": self.channel_title,
            "is_active": int(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "RequiredChannel":
        data = dict(row)
        if isinstance(data.get("is_active"), int):
            data["is_active"] = bool(data["is_active"])
        return cls(**data)

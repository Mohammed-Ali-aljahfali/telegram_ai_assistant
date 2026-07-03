"""models/chat.py — نموذج المحادثة"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ChatType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
    CHANNEL = "channel"


class Chat(BaseModel):
    id: Optional[int] = None
    bot_user_id: int
    customer_id: Optional[int] = None
    chat_id: int
    chat_type: ChatType = ChatType.PRIVATE
    title: Optional[str] = None
    username: Optional[str] = None
    auto_reply: bool = True
    ai_enabled: bool = True
    status: str = "active"
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Channel(BaseModel):
    id: Optional[int] = None
    bot_user_id: int
    channel_id: int
    username: Optional[str] = None
    title: Optional[str] = None
    channel_type: str = "channel"
    is_active: bool = True
    auto_reply: bool = False
    keywords_only: bool = True
    added_at: Optional[datetime] = None
    last_checked: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RequiredChannel(BaseModel):
    id: Optional[int] = None
    channel_id: int
    channel_username: Optional[str] = None
    title: Optional[str] = None
    channel_type: str = "channel"
    is_active: bool = True
    added_by: Optional[int] = None
    added_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

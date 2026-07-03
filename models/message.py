"""models/message.py — نموذج الرسالة"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class MessageIntent(str, Enum):
    INQUIRY = "inquiry"
    SERVICE_REQUEST = "service_request"
    NEGOTIATION = "negotiation"
    COMPLAINT = "complaint"
    FOLLOW_UP = "follow_up"
    GENERAL = "general"


class MessageSentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class MessageType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    STICKER = "sticker"
    VOICE = "voice"
    VIDEO = "video"
    OTHER = "other"


class SenderType(str, Enum):
    USER = "user"        # العميل
    BOT = "bot"          # رد الذكاء الاصطناعي
    SYSTEM = "system"    # النظام


class Message(BaseModel):
    id: Optional[int] = None
    chat_id: int
    telegram_msg_id: Optional[int] = None
    sender_id: Optional[int] = None
    sender_type: SenderType = SenderType.USER
    content: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    intent: Optional[MessageIntent] = None
    sentiment: Optional[MessageSentiment] = None
    is_important: bool = False
    ai_analyzed: bool = False
    created_at: Optional[datetime] = None

    @property
    def intent_emoji(self) -> str:
        emojis = {
            MessageIntent.INQUIRY: "❓",
            MessageIntent.SERVICE_REQUEST: "📋",
            MessageIntent.NEGOTIATION: "🤝",
            MessageIntent.COMPLAINT: "😤",
            MessageIntent.FOLLOW_UP: "🔄",
            MessageIntent.GENERAL: "💬",
        }
        return emojis.get(self.intent, "💬")

    model_config = {"from_attributes": True}

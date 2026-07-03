"""models/customer.py — نموذج العميل"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CustomerStatus(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    INTERESTED = "interested"
    CONVERTED = "converted"
    LOST = "lost"


class Customer(BaseModel):
    id: Optional[int] = None
    bot_user_id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    language: str = "ar"
    status: CustomerStatus = CustomerStatus.NEW
    interest_score: float = 0.0
    service_type: Optional[str] = None
    notes: Optional[str] = None
    first_contact: Optional[datetime] = None
    last_contact: Optional[datetime] = None
    message_count: int = 0
    summary: Optional[str] = None

    @property
    def display_name(self) -> str:
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else self.username or f"#{self.telegram_id}"

    @property
    def status_emoji(self) -> str:
        emojis = {
            CustomerStatus.NEW: "🆕",
            CustomerStatus.ACTIVE: "🟢",
            CustomerStatus.INTERESTED: "⭐",
            CustomerStatus.CONVERTED: "✅",
            CustomerStatus.LOST: "❌",
        }
        return emojis.get(self.status, "❓")

    model_config = {"from_attributes": True}

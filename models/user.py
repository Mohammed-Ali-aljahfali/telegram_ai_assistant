"""models/user.py — نموذج مستخدم البوت"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    DEVELOPER = "developer"
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class BotUser(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    is_authenticated: bool = False
    telethon_session: Optional[str] = None   # مشفّر
    two_factor_hint: Optional[str] = None
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    settings: dict = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.first_name or self.username or f"User#{self.telegram_id}"

    @property
    def is_developer(self) -> bool:
        from config import config
        return self.role == UserRole.DEVELOPER or self.telegram_id in (config.DEVELOPER_ID, config.ADMIN_CHAT_ID)

    @property
    def is_admin(self) -> bool:
        from config import config
        return self.role in (UserRole.DEVELOPER, UserRole.ADMIN) or self.telegram_id in (config.DEVELOPER_ID, config.ADMIN_CHAT_ID)

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    model_config = {"from_attributes": True}

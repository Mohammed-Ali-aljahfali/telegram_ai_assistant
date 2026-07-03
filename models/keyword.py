"""models/keyword.py — نموذج الكلمة المفتاحية"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class KeywordCategory(str, Enum):
    SERVICE = "service"
    INQUIRY = "inquiry"
    COMPETITOR = "competitor"
    SPAM = "spam"
    CUSTOM = "custom"


class KeywordAction(str, Enum):
    ALERT = "alert"
    REPLY = "reply"
    IGNORE = "ignore"


class Keyword(BaseModel):
    id: Optional[int] = None
    bot_user_id: int
    keyword: str
    category: KeywordCategory = KeywordCategory.CUSTOM
    action: KeywordAction = KeywordAction.ALERT
    reply_template: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Settings(BaseModel):
    id: Optional[int] = None
    bot_user_id: Optional[int] = None
    key: str
    value: Optional[str] = None
    value_type: str = "string"
    category: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    def get_typed_value(self):
        if self.value is None:
            return None
        if self.value_type == "int":
            return int(self.value)
        if self.value_type == "bool":
            return self.value.lower() in ("true", "1", "yes")
        if self.value_type == "json":
            import json
            return json.loads(self.value)
        return self.value

    model_config = {"from_attributes": True}

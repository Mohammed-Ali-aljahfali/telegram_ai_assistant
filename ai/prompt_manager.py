"""ai/prompt_manager.py — إدارة البرومبتات"""
from typing import Optional
from database.repositories.settings_repository import SettingsRepository
from infrastructure.logger import get_logger

logger = get_logger("ai.prompts")

DEFAULT_SYSTEM_PROMPT = """أنت مساعد ذكي احترافي لإدارة العملاء عبر Telegram.

مهمتك الأساسية:
1. التحدث مع العملاء المحتملين بأسلوب احترافي ودود
2. فهم احتياجاتهم وتحديد الخدمة المطلوبة
3. الرد بشكل واضح ومفيد
4. قياس مستوى اهتمام العميل
5. التفاوض بشكل مهذب واحترافي

قواعد مهمة:
- كن دائماً محترفاً وودوداً
- لا تعطِ أسعاراً محددة إلا إذا طُلب منك
- اسأل أسئلة توضيحية عند الحاجة
- أجب باللغة التي يتحدث بها العميل
"""

DEFAULT_ANALYSIS_PROMPT = """حلل الرسالة التالية وأعطني JSON بهذا الهيكل:
{
  "intent": "inquiry|service_request|negotiation|complaint|follow_up|general",
  "sentiment": "positive|negative|neutral",
  "interest_score": 0-10,
  "service_type": "وصف الخدمة المطلوبة أو null",
  "key_points": ["نقطة 1", "نقطة 2"],
  "language": "ar|en|other",
  "needs_human": true|false
}"""


class PromptManager:

    def __init__(self):
        self.settings_repo = SettingsRepository()

    async def get_system_prompt(self, bot_user_id: Optional[int] = None) -> str:
        if bot_user_id:
            prompt = await self.settings_repo.get("ai_system_prompt", bot_user_id)
            if prompt:
                return prompt
        global_prompt = await self.settings_repo.get("ai_system_prompt")
        return global_prompt or DEFAULT_SYSTEM_PROMPT

    async def set_system_prompt(self, bot_user_id: int, prompt: str):
        await self.settings_repo.set(
            "ai_system_prompt", prompt, bot_user_id,
            category="ai", description="البرومبت الأساسي للذكاء الاصطناعي"
        )

    async def get_analysis_prompt(self) -> str:
        return DEFAULT_ANALYSIS_PROMPT

    def format_conversation(self, messages: list) -> list[dict]:
        """تحويل رسائل قاعدة البيانات لتنسيق AI"""
        result = []
        for msg in messages:
            if hasattr(msg, "sender_type"):
                role = "assistant" if msg.sender_type in ("bot", "system") else "user"
                content = msg.content or ""
            else:
                role = msg.get("role", "user")
                content = msg.get("content", "")
            if content:
                result.append({"role": role, "content": content})
        return result

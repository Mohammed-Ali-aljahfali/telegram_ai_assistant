"""services/ai_service.py — خدمة الذكاء الاصطناعي المركزية"""
from typing import Optional
from ai.ai_provider import BaseAIProvider
from ai.providers.openai_provider import OpenAIProvider
from ai.providers.gemini_provider import GeminiProvider
from ai.providers.claude_provider import ClaudeProvider
from ai.prompt_manager import PromptManager
from database.repositories.settings_repository import SettingsRepository
from infrastructure.logger import get_logger

logger = get_logger("ai_service")


def _decrypt_key_safely(value: Optional[str]) -> Optional[str]:
    """فك تشفير مفتاح الـ API بشكل آمن إذا كان مشفراً، أو إرجاعه كما هو."""
    if not value:
        return None
    from infrastructure.crypto import decrypt_text
    decrypted = decrypt_text(value)
    if decrypted:
        return decrypted
    return value


class AIService:
    """الخدمة المركزية للذكاء الاصطناعي"""

    def __init__(self):
        self.settings_repo = SettingsRepository()
        self.prompt_manager = PromptManager()
        self._providers: dict[int, BaseAIProvider] = {}   # user_id -> provider

    async def get_provider(self, bot_user_id: int) -> Optional[BaseAIProvider]:
        if bot_user_id in self._providers:
            return self._providers[bot_user_id]

        provider_name = await self.settings_repo.get("ai_provider", bot_user_id) or "openai"
        model = await self.settings_repo.get("ai_model", bot_user_id)

        from config import config
        if provider_name == "openai":
            db_key = await self.settings_repo.get("openai_api_key", bot_user_id)
            api_key = _decrypt_key_safely(db_key) or config.OPENAI_API_KEY
            if api_key:
                provider = OpenAIProvider(api_key, model or "gpt-4o-mini")
                self._providers[bot_user_id] = provider
                return provider
        elif provider_name == "gemini":
            db_key = await self.settings_repo.get("gemini_api_key", bot_user_id)
            api_key = _decrypt_key_safely(db_key) or config.GEMINI_API_KEY
            if api_key:
                provider = GeminiProvider(api_key, model or "gemini-1.5-flash")
                self._providers[bot_user_id] = provider
                return provider
        elif provider_name == "claude":
            db_key = await self.settings_repo.get("claude_api_key", bot_user_id)
            api_key = _decrypt_key_safely(db_key) or config.CLAUDE_API_KEY
            if api_key:
                provider = ClaudeProvider(api_key, model or "claude-3-haiku-20240307")
                self._providers[bot_user_id] = provider
                return provider

        return None

    async def set_provider(self, bot_user_id: int, provider_name: str,
                           api_key: str, model: str = None):
        """تعيين مزود الذكاء الاصطناعي"""
        from infrastructure.crypto import encrypt_text
        await self.settings_repo.set("ai_provider", provider_name, bot_user_id, category="ai")
        await self.settings_repo.set(f"{provider_name}_api_key", encrypt_text(api_key),
                                      bot_user_id, category="ai")
        if model:
            await self.settings_repo.set("ai_model", model, bot_user_id, category="ai")
        self._providers.pop(bot_user_id, None)   # إعادة التهيئة

    async def generate_response(self, bot_user_id: int, messages: list[dict],
                                 system_prompt: str = None) -> Optional[str]:
        provider = await self.get_provider(bot_user_id)
        if not provider:
            return None
        if not system_prompt:
            system_prompt = await self.prompt_manager.get_system_prompt(bot_user_id)
        temp = await self.settings_repo.get("ai_temperature", bot_user_id)
        temperature = float(temp) if temp else 0.7
        return await provider.generate_response(messages, system_prompt, temperature)

    async def analyze_message(self, bot_user_id: int, text: str) -> dict:
        provider = await self.get_provider(bot_user_id)
        if not provider:
            return {}
        task = await self.prompt_manager.get_analysis_prompt()
        return await provider.analyze_text(text, task)

    async def test(self, bot_user_id: int, test_message: str = "مرحبا") -> tuple[bool, str]:
        try:
            provider = await self.get_provider(bot_user_id)
            if not provider:
                return False, "❌ لم يتم تعيين مزود AI. أضف API Key أولاً."
            response = await provider.generate_response(
                [{"role": "user", "content": test_message}], max_tokens=100
            )
            return True, f"✅ الذكاء الاصطناعي يعمل!\n\n*الرد:*\n{response}"
        except Exception as e:
            return False, f"❌ خطأ: {str(e)}"

    def clear_provider_cache(self, bot_user_id: int):
        self._providers.pop(bot_user_id, None)

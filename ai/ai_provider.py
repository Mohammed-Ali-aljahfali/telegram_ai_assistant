"""ai/ai_provider.py — واجهة مجردة لمزودي الذكاء الاصطناعي"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseAIProvider(ABC):
    """واجهة موحدة لجميع مزودي الذكاء الاصطناعي"""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """توليد رد من الذكاء الاصطناعي"""
        pass

    @abstractmethod
    async def analyze_text(self, text: str, task: str) -> dict:
        """تحليل نص لمهمة محددة"""
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """قائمة النماذج المتاحة"""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """اختبار الاتصال"""
        pass

    def get_name(self) -> str:
        return self.__class__.__name__.replace("Provider", "")

"""ai/providers/claude_provider.py — مزود Anthropic Claude"""
from typing import Optional
from ai.ai_provider import BaseAIProvider
from infrastructure.logger import get_logger

logger = get_logger("ai.claude")


class ClaudeProvider(BaseAIProvider):

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if not self._client:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        try:
            client = self._get_client()

            # دمج الرسائل المتتالية من نفس الطرف لـ Claude
            formatted_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "assistant"
                content = msg["content"]
                if formatted_messages and formatted_messages[-1]["role"] == role:
                    formatted_messages[-1]["content"] += f"\n{content}"
                else:
                    formatted_messages.append({"role": role, "content": content})

            # يجب أن تبدأ المحادثة دائماً بـ user في Claude
            while formatted_messages and formatted_messages[0]["role"] != "user":
                formatted_messages.pop(0)

            if not formatted_messages:
                formatted_messages = [{"role": "user", "content": "مرحبا"}]

            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt or "أنت مساعد ذكي محترف.",
                messages=formatted_messages,
                temperature=temperature,
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Claude error: {e}")
            raise

    async def analyze_text(self, text: str, task: str) -> dict:
        import json
        result = await self.generate_response(
            [{"role": "user", "content": f"مهمتك: {task}\n\nالنص:\n{text}\n\nأجب بـ JSON فقط."}],
            temperature=0.3, max_tokens=500
        )
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            return json.loads(result[start:end]) if start >= 0 else {"raw": result}
        except Exception:
            return {"raw": result}

    def get_available_models(self) -> list[str]:
        return ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"]

    async def test_connection(self) -> bool:
        try:
            await self.generate_response(
                [{"role": "user", "content": "مرحبا"}], max_tokens=10
            )
            return True
        except Exception:
            return False

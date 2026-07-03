"""ai/providers/gemini_provider.py — مزود Google Gemini"""
from typing import Optional
from ai.ai_provider import BaseAIProvider
from infrastructure.logger import get_logger

logger = get_logger("ai.gemini")


class GeminiProvider(BaseAIProvider):

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if not self._client:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        try:
            import google.generativeai as genai
            import asyncio

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                self.model,
                system_instruction=system_prompt or "",
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            # تحويل رسائل OpenAI format لـ Gemini
            history = []
            last_user_msg = ""
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                if msg["role"] == "user":
                    last_user_msg = msg["content"]
                    if history:
                        history.append({"role": role, "parts": [msg["content"]]})
                else:
                    history.append({"role": role, "parts": [msg["content"]]})

            chat = model.start_chat(history=history[:-1] if history else [])
            response = await asyncio.to_thread(chat.send_message, last_user_msg or messages[-1]["content"])
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini error: {e}")
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
        return ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]

    async def test_connection(self) -> bool:
        try:
            await self.generate_response(
                [{"role": "user", "content": "مرحبا"}], max_tokens=10
            )
            return True
        except Exception:
            return False

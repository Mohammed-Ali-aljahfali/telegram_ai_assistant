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

            # system_instruction يجب أن لا يكون فارغاً — Gemini ترفض القيم الفارغة
            sys_instruction = (system_prompt or "").strip() or None

            model_kwargs = dict(
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            if sys_instruction:
                model_kwargs["system_instruction"] = sys_instruction

            model = genai.GenerativeModel(self.model, **model_kwargs)

            # تحويل رسائل OpenAI format لـ Gemini مع ضمان التناوب الصحيح والبدء بـ user
            raw_history = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                content = (msg.get("content") or "").strip()
                if not content:          # تخطي الرسائل الفارغة تماماً
                    continue
                if raw_history and raw_history[-1]["role"] == role:
                    # دمج الرسائل المتتالية من نفس الطرف
                    raw_history[-1]["parts"][0] += f"\n{content}"
                else:
                    raw_history.append({"role": role, "parts": [content]})

            # يجب أن تبدأ المحادثة دائماً بـ user في Gemini
            while raw_history and raw_history[0]["role"] != "user":
                raw_history.pop(0)

            # سحب آخر رسالة للمستخدم لإرسالها مع send_message
            last_user_msg = ""
            if raw_history and raw_history[-1]["role"] == "user":
                last_user_msg = raw_history.pop()["parts"][0]

            # التحقق النهائي: لا نرسل محتوى فارغاً أبداً إلى Gemini
            send_content = last_user_msg.strip()
            if not send_content:
                # بحث احتياطي في قائمة الرسائل الأصلية
                for msg in reversed(messages):
                    if msg.get("role") == "user" and (msg.get("content") or "").strip():
                        send_content = msg["content"].strip()
                        break
            if not send_content:
                send_content = "مرحبا"

            chat = model.start_chat(history=raw_history)
            response = await asyncio.to_thread(chat.send_message, send_content)
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
        return ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

    async def test_connection(self) -> bool:
        try:
            await self.generate_response(
                [{"role": "user", "content": "مرحبا"}], max_tokens=10
            )
            return True
        except Exception:
            return False

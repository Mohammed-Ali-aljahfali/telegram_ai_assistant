"""ai/providers/gemini_provider.py — مزود Google Gemini"""
from typing import Optional
from ai.ai_provider import BaseAIProvider
from infrastructure.logger import get_logger

logger = get_logger("ai.gemini")


def _clean_parts(history: list[dict]) -> list[dict]:
    """
    تنظيف تاريخ المحادثة من أي parts فارغة تماماً.
    Gemini API ترفض أي parts تحتوي على نص فارغ أو مسافات فقط.
    """
    clean = []
    for turn in history:
        parts = [p for p in turn.get("parts", []) if isinstance(p, str) and p.strip()]
        if parts:
            clean.append({"role": turn["role"], "parts": parts})
    return clean


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

            # ✅ system_instruction يجب أن يكون غير فارغ أو لا يُرسل أبداً
            sys_instruction = (system_prompt or "").strip() or None

            model_kwargs: dict = {
                "generation_config": genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            }
            if sys_instruction:
                model_kwargs["system_instruction"] = sys_instruction

            model = genai.GenerativeModel(self.model, **model_kwargs)

            # ✅ تحويل رسائل OpenAI format لـ Gemini مع ضمان التناوب الصحيح
            raw_history: list[dict] = []
            for msg in messages:
                role = "user" if msg.get("role") == "user" else "model"
                content = (msg.get("content") or "").strip()
                if not content:
                    # ✅ تخطي الرسائل الفارغة كلياً
                    continue
                if raw_history and raw_history[-1]["role"] == role:
                    # دمج رسائل متتالية من نفس الطرف
                    existing = raw_history[-1]["parts"][0].strip()
                    raw_history[-1]["parts"][0] = f"{existing}\n{content}" if existing else content
                else:
                    raw_history.append({"role": role, "parts": [content]})

            # ✅ يجب أن تبدأ المحادثة دائماً بـ user في Gemini
            while raw_history and raw_history[0]["role"] != "user":
                raw_history.pop(0)

            # ✅ سحب آخر رسالة للمستخدم لإرسالها عبر send_message
            last_user_msg = ""
            if raw_history and raw_history[-1]["role"] == "user":
                last_user_msg = raw_history.pop()["parts"][0].strip()

            # ✅ تنظيف نهائي للتاريخ من أي parts فارغة
            raw_history = _clean_parts(raw_history)

            # ✅ التحقق المزدوج من أن رسالة الإرسال ليست فارغة
            send_content = last_user_msg
            if not send_content:
                for msg in reversed(messages):
                    candidate = (msg.get("content") or "").strip()
                    if msg.get("role") == "user" and candidate:
                        send_content = candidate
                        break
            if not send_content:
                send_content = "مرحبا"

            logger.debug(
                "Gemini send | history_turns=%d | content_len=%d",
                len(raw_history), len(send_content)
            )

            chat = model.start_chat(history=raw_history)
            response = await asyncio.to_thread(chat.send_message, send_content)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Gemini error: {e}")
            raise

    async def analyze_text(self, text: str, task: str) -> dict:
        import json
        # ✅ التحقق من أن النص والمهمة غير فارغين
        text = (text or "").strip()
        task = (task or "").strip()
        if not text or not task:
            logger.warning("analyze_text called with empty text or task")
            return {}

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

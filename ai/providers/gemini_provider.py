"""ai/providers/gemini_provider.py — مزود Google Gemini

يدعم كلا تنسيقي مفاتيح Google AI Studio:
  - المفاتيح القديمة: تبدأ بـ AIzaSy  (google-generativeai)
  - المفاتيح الجديدة: تبدأ بـ AQ.     (google-genai SDK الجديد)
"""
from typing import Optional
from ai.ai_provider import BaseAIProvider
from infrastructure.logger import get_logger

logger = get_logger("ai.gemini")


def _is_new_key_format(api_key: str) -> bool:
    """مفاتيح AQ. تستخدم SDK الجديد google-genai"""
    return api_key.startswith("AQ.")


def _clean_parts(history: list[dict]) -> list[dict]:
    """تنظيف تاريخ المحادثة من أي parts فارغة — Gemini API ترفضها."""
    clean = []
    for turn in history:
        parts = [p for p in turn.get("parts", []) if isinstance(p, str) and p.strip()]
        if parts:
            clean.append({"role": turn["role"], "parts": parts})
    return clean


class GeminiProvider(BaseAIProvider):

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None

    # ──────────────────────────────────────────────────────────────────
    # SDK الجديد: google-genai  (مفاتيح AQ.)
    # ──────────────────────────────────────────────────────────────────
    async def _generate_new_sdk(
        self,
        messages: list[dict],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        from google import genai
        from google.genai import types
        import asyncio

        client = genai.Client(api_key=self.api_key)

        # بناء محتوى المحادثة
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            contents.append(types.Content(role=role, parts=[types.Part(text=content)]))

        if not contents:
            contents.append(types.Content(role="user", parts=[types.Part(text="مرحبا")]))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_prompt and system_prompt.strip():
            config.system_instruction = system_prompt.strip()

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=self.model,
            contents=contents,
            config=config,
        )
        return response.text.strip()

    # ──────────────────────────────────────────────────────────────────
    # SDK القديم: google-generativeai  (مفاتيح AIzaSy)
    # ──────────────────────────────────────────────────────────────────
    async def _generate_legacy_sdk(
        self,
        messages: list[dict],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        import google.generativeai as genai
        import asyncio

        genai.configure(api_key=self.api_key)

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

        raw_history: list[dict] = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if raw_history and raw_history[-1]["role"] == role:
                existing = raw_history[-1]["parts"][0].strip()
                raw_history[-1]["parts"][0] = f"{existing}\n{content}" if existing else content
            else:
                raw_history.append({"role": role, "parts": [content]})

        while raw_history and raw_history[0]["role"] != "user":
            raw_history.pop(0)

        last_user_msg = ""
        if raw_history and raw_history[-1]["role"] == "user":
            last_user_msg = raw_history.pop()["parts"][0].strip()

        raw_history = _clean_parts(raw_history)

        send_content = last_user_msg
        if not send_content:
            for msg in reversed(messages):
                candidate = (msg.get("content") or "").strip()
                if msg.get("role") == "user" and candidate:
                    send_content = candidate
                    break
        if not send_content:
            send_content = "مرحبا"

        chat = model.start_chat(history=raw_history)
        response = await asyncio.to_thread(chat.send_message, send_content)
        return response.text.strip()

    # ──────────────────────────────────────────────────────────────────
    # الواجهة الموحدة
    # ──────────────────────────────────────────────────────────────────
    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        try:
            if _is_new_key_format(self.api_key):
                logger.debug("Gemini: using new google-genai SDK (AQ. key)")
                return await self._generate_new_sdk(messages, system_prompt, temperature, max_tokens)
            else:
                logger.debug("Gemini: using legacy google-generativeai SDK (AIzaSy key)")
                return await self._generate_legacy_sdk(messages, system_prompt, temperature, max_tokens)
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            raise

    async def analyze_text(self, text: str, task: str) -> dict:
        import json
        text = (text or "").strip()
        task = (task or "").strip()
        if not text or not task:
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
        return [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

    async def test_connection(self) -> bool:
        try:
            await self.generate_response(
                [{"role": "user", "content": "مرحبا"}], max_tokens=10
            )
            return True
        except Exception:
            return False

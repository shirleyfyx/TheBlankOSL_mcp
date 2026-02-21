import asyncio
from typing import Any
from google import genai

from .base import BaseLLMClient

def _get_api_key(api_key: str | None) -> str:
    """Require API key from caller (CLI config). Raises if missing."""
    if not api_key or not api_key.strip():
        raise ValueError(
            "Gemini API key not set. Run: blankosl_cli config --gemini-api-key <your_key>"
        )
    return api_key.strip()

class GeminiClient(BaseLLMClient):
    """LLM client using Google Gemini API. API key from CLI config only."""

    def __init__(self, api_key: str | None = None):
        self._api_key = _get_api_key(api_key)
        self._client = None

    @property
    def id(self) -> str:
        return "gemini"

    @property
    def name(self) -> str:
        return "Google Gemini"

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _chat_sync(self, messages: list[dict[str, Any]]) -> str:
        client = self._get_client()
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()
            if role == "system":
                parts.append(f"[System] {content}")
            elif role == "user":
                parts.append(content)
            elif role == "assistant":
                parts.append(f"[Assistant] {content}")
        prompt = "\n\n".join(parts).strip()
        if not prompt:
            return ""

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if not response:
                return "[No response from model]"
            try:
                text = response.text
            except (ValueError, AttributeError):
                parts_list = getattr(response, "candidates", None) or []
                if parts_list and hasattr(parts_list[0], "content") and parts_list[0].content.parts:
                    text = getattr(parts_list[0].content.parts[0], "text", "") or ""
                else:
                    text = ""
            return (text or "[No response from model]").strip()
        except Exception as e:
            return f"[Gemini error: {e}]"

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        return await asyncio.to_thread(self._chat_sync, messages)

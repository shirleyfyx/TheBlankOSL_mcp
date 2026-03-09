import asyncio
from typing import Any

from groq import Groq

from .base import BaseLLMClient


def _format_groq_error(ex: Exception) -> str:
    """Turn Groq API errors into a short, readable message."""
    msg = str(ex)
    if "429" in msg or "rate_limit" in msg.lower():
        return "Groq rate limit exceeded. Wait a minute or check your plan: https://console.groq.com/docs/rate-limits"
    if "401" in msg or "UNAUTHENTICATED" in msg or "invalid_api_key" in msg.lower():
        return "Groq API key invalid or missing. Run: blankosl_cli config --groq-api-key <your_key>"
    if "400" in msg or "invalid_request" in msg.lower():
        return f"Groq request error: {msg[:200]}"
    return f"[Groq error: {msg[:300]}]"


def _get_api_key(api_key: str | None) -> str:
    """Require API key from caller (CLI config). Raises if missing."""
    if not api_key or not api_key.strip():
        raise ValueError(
            "Groq API key not set. Run: blankosl_cli config --groq-api-key <your_key>"
        )
    return api_key.strip()


def _messages_to_groq(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert our [{role, content}, ...] to Groq API format (role + content only)."""
    out: list[dict[str, str]] = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if role == "system":
            out.append({"role": "system", "content": content})
        elif role == "user":
            out.append({"role": "user", "content": content})
        elif role == "assistant":
            out.append({"role": "assistant", "content": content})
    return out


def _response_text(completion: Any) -> str:
    """Extract reply text from chat completion response."""
    if not completion:
        return "[No response from model]"
    try:
        choices = getattr(completion, "choices", None) or []
        if not choices:
            return "[No response from model]"
        msg = getattr(choices[0], "message", None)
        if not msg:
            return "[No response from model]"
        return (getattr(msg, "content", None) or "[No response from model]").strip()
    except (ValueError, AttributeError):
        return "[No response from model]"


class GroqClient(BaseLLMClient):
    """LLM client using Groq API (OpenAI-compatible chat completions)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = _get_api_key(api_key)
        self._client: Groq | None = None

    @property
    def id(self) -> str:
        return "groq"

    @property
    def name(self) -> str:
        return "Groq"

    def _get_client(self) -> Groq:
        if self._client is None:
            self._client = Groq(api_key=self._api_key)
        return self._client

    def _chat_sync(self, messages: list[dict[str, Any]]) -> str:
        if not messages:
            return ""
        groq_messages = _messages_to_groq(messages)
        try:
            client = self._get_client()
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=groq_messages,
            )
            return _response_text(completion)
        except Exception as e:
            return _format_groq_error(e)

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        return await asyncio.to_thread(self._chat_sync, messages)

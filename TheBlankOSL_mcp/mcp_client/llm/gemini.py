import asyncio
from typing import Any

from google import genai
from google.genai import types

from .base import BaseLLMClient

def _get_api_key(api_key: str | None) -> str:
    """Require API key from caller (CLI config). Raises if missing."""
    if not api_key or not api_key.strip():
        raise ValueError(
            "Gemini API key not set. Run: blankosl_cli config --gemini-api-key <your_key>"
        )
    return api_key.strip()

def _messages_to_sdk_history(messages: list[dict[str, Any]]) -> list[types.Content]:
    """Convert our [{role, content}, ...] to SDK Content list (role user/model, parts)."""
    out: list[types.Content] = []
    for m in messages:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if role == "system":
            out.append(types.Content(role="user", parts=[types.Part.from_text(f"[System] {content}")]))
        elif role == "user":
            out.append(types.Content(role="user", parts=[types.Part.from_text(content)]))
        elif role == "assistant":
            out.append(types.Content(role="model", parts=[types.Part.from_text(content)]))
    return out

def _response_text(response: Any) -> str:
    """Extract reply text from generate_content response."""
    if not response:
        return "[No response from model]"
    try:
        return (response.text or "[No response from model]").strip()
    except (ValueError, AttributeError):
        parts_list = getattr(response, "candidates", None) or []
        if parts_list and hasattr(parts_list[0], "content") and parts_list[0].content.parts:
            return (getattr(parts_list[0].content.parts[0], "text", "") or "[No response from model]").strip()
        return "[No response from model]"

class GeminiClient(BaseLLMClient):
    """LLM client using Google Gemini API. Uses SDK ChatSession to keep chat history."""

    def __init__(self, api_key: str | None = None):
        self._api_key = _get_api_key(api_key)
        self._client: genai.Client | None = None
        self._chat_session: Any = None  # Chat from client.chats.create(...)
        self._session_turns: int = 0  # number of user+model turn pairs in the session

    @property
    def id(self) -> str:
        return "gemini"

    @property
    def name(self) -> str:
        return "Google Gemini"

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _chat_sync(self, messages: list[dict[str, Any]]) -> str:
        if not messages:
            return ""
        new_content = (messages[-1].get("content") or "").strip()
        # Reuse session when this is a continuation (previous turns + one new user message)
        is_continuation = (
            self._chat_session is not None
            and len(messages) == 2 * self._session_turns + 1
        )
        if is_continuation:
            try:
                response = self._chat_session.send_message(new_content)
            except Exception as e:
                return f"[Gemini error: {e}]"
            self._session_turns += 1
        else:
            # New or reset: create ChatSession with history = all but last message, send last
            history = _messages_to_sdk_history(messages[:-1])
            try:
                client = self._get_client()
                self._chat_session = client.chats.create(
                    model="gemini-2.5-flash",
                    history=history,
                )
                response = self._chat_session.send_message(new_content)
            except Exception as e:
                return f"[Gemini error: {e}]"
            self._session_turns = (len(messages) + 1) // 2
        return _response_text(response)

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        return await asyncio.to_thread(self._chat_sync, messages)

import asyncio
from typing import Any
from ollama import Client
from .base import BaseLLMClient

# Configuration constants
NEBULA_HOST = "http://ece-nebula04.eng.uwaterloo.ca:11434"
TARGET_MODEL = "qwen3-next:latest"

def _format_ollama_error(ex: Exception) -> str:
    """Turn Ollama/Network errors into a short, readable message."""
    msg = str(ex)
    if "Connection refused" in msg or "NewConnectionError" in msg or "ConnectTimeout" in msg:
        return f"Qwen connection failed. Check if Nebula server ({NEBULA_HOST}) is reachable."
    if "not found" in msg.lower():
        return f"Qwen model not found: {TARGET_MODEL}. Check server models."
    return f"[Qwen error: {msg[:300]}]"


class QwenClient(BaseLLMClient):
    """LLM client for Qwen3 models hosted on Ollama."""

    def __init__(self, host: str = NEBULA_HOST, model: str = TARGET_MODEL):
        self._host = host
        self._model = model
        self._client = Client(host=self._host)

    @property
    def id(self) -> str:
        return "qwen"

    @property
    def name(self) -> str:
        return "Qwen 3"

    def _chat_sync(self, messages: list[dict[str, Any]]) -> str:
        if not messages:
            return ""

        # Clean messages for Ollama (list of {role: str, content: str})
        clean_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()
            clean_messages.append({"role": role, "content": content})

        try:
            response = self._client.chat(
                model=self._model,
                messages=clean_messages,
                options={
                    "num_ctx": 125000,
                    "temperature": 0.7,
                },
            )
            return response.get("message", {}).get("content", "")
        except Exception as e:
            return _format_ollama_error(e)

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        return await asyncio.to_thread(self._chat_sync, messages)

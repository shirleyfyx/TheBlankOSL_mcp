from typing import Any

from ..utils import settings_mgr
from .base import BaseLLMClient
from .gemini import GeminiClient
from .groq import GroqClient
from .qwen import QwenClient

_BACKENDS: dict[str, tuple[str, type[BaseLLMClient]]] = {
    "gemini": ("Google Gemini", GeminiClient),
    "groq": ("Groq", GroqClient),
    "qwen": ("Uwaterloo Qwen", QwenClient),
}


def list_backends() -> list[dict[str, str]]:
    return [{"id": bid, "name": name} for bid, (name, _) in _BACKENDS.items()]


def get_llm_kwargs(backend_id: str) -> dict[str, Any]:
    """Return kwargs for get_client(backend_id, **kwargs). Add new backends here."""
    settings = settings_mgr.load()
    if backend_id == "gemini":
        return {"api_key": settings.gemini_api_key}
    if backend_id == "groq":
        return {"api_key": settings.groq_api_key}
    # e.g. if backend_id == "openai": return {"api_key": settings.openai_api_key}
    return {}


def get_client(backend_id: str, **kwargs: Any) -> BaseLLMClient | None:
    entry = _BACKENDS.get(backend_id)
    if not entry:
        return None
    _name, factory = entry
    if not kwargs:
        kwargs = get_llm_kwargs(backend_id)
    return factory(**kwargs)


def get_backend_name(backend_id: str) -> str | None:
    entry = _BACKENDS.get(backend_id)
    return entry[0] if entry else None

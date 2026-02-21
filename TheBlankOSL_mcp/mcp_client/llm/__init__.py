from typing import Any

from .base import BaseLLMClient
from .gemini import GeminiClient

_BACKENDS: dict[str, tuple[str, type[BaseLLMClient]]] = {
    "gemini": ("Google Gemini", GeminiClient),
}

def list_backends() -> list[dict[str, str]]:
    return [{"id": bid, "name": name} for bid, (name, _) in _BACKENDS.items()]

def get_client(backend_id: str, **kwargs: Any) -> BaseLLMClient | None:
    entry = _BACKENDS.get(backend_id)
    if not entry:
        return None
    _name, factory = entry
    return factory(**kwargs)

def get_backend_name(backend_id: str) -> str | None:
    entry = _BACKENDS.get(backend_id)
    return entry[0] if entry else None

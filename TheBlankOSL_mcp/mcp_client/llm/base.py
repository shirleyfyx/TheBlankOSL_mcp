"""Abstract base for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    """Interface that all LLM backends must implement."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Backend identifier (e.g. 'gemini')."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name (e.g. 'Google Gemini')."""
        ...

    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]]) -> str:
        """Send messages and return the assistant reply text."""
        ...

"""Abstract base for all model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from n3rverberage.providers.models import ToolResult


class ModelProvider(ABC):
    """Abstract interface for LLM providers.

    All providers implement three completion methods:
    - ``complete()``: plain text response
    - ``complete_structured()``: typed JSON response
    - ``complete_with_tools()``: response with tool call candidates
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model or self._default_model()
        self.base_url = base_url or self._default_base_url()

    @abstractmethod
    def _default_model(self) -> str:
        """Return the default model ID for this provider."""
        ...

    @abstractmethod
    def _default_base_url(self) -> str:
        """Return the default base URL for this provider."""
        ...

    @abstractmethod
    def complete(self, messages: list[dict], **kwargs: Any) -> str:
        """Send a completion request and return the text response."""
        ...

    @abstractmethod
    def complete_structured(
        self,
        messages: list[dict],
        output_type: type[BaseModel],
        **kwargs: Any,
    ) -> BaseModel:
        """Send a completion request and return a validated structured response."""
        ...

    @abstractmethod
    def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        **kwargs: Any,
    ) -> ToolResult:
        """Send a completion request with tool definitions."""
        ...

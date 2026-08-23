"""Fallback provider — chain-of-responsibility for quota exhaustion."""

from __future__ import annotations

import sys
from typing import Any

from pydantic import BaseModel

from n3rverberage.providers.base import ModelProvider
from n3rverberage.providers.models import (
    AllProvidersExhaustedError,
    QuotaExhaustedError,
    ToolResult,
)


class FallbackProvider(ModelProvider):
    """Provider that chains multiple providers, falling back on quota exhaustion.

    Only :class:`QuotaExhaustedError` triggers the next provider.
    All other errors propagate immediately.

    Parameters
    ----------
    providers:
        Ordered list of providers to try. At least one is required.
    """

    def __init__(
        self,
        providers: list[ModelProvider],
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        # Must set _providers BEFORE super().__init__ because
        # _default_model() reads it
        self._providers = providers
        super().__init__(api_key, model, base_url)

    def _default_model(self) -> str:
        return self._providers[0].model if self._providers else "unknown"

    def _default_base_url(self) -> str:
        return "fallback"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(self, messages: list[dict], **kwargs: Any) -> str:
        exhausted: list[str] = []
        for provider in self._providers:
            try:
                return provider.complete(messages, **kwargs)
            except QuotaExhaustedError as exc:
                exhausted.append(exc.model_id)
                _log_fallback(exc.model_id)
        raise AllProvidersExhaustedError(exhausted)

    def complete_structured(
        self,
        messages: list[dict],
        output_type: type[BaseModel],
        **kwargs: Any,
    ) -> BaseModel:
        exhausted: list[str] = []
        for provider in self._providers:
            try:
                return provider.complete_structured(messages, output_type, **kwargs)
            except QuotaExhaustedError as exc:
                exhausted.append(exc.model_id)
                _log_fallback(exc.model_id)
        raise AllProvidersExhaustedError(exhausted)

    def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        **kwargs: Any,
    ) -> ToolResult:
        exhausted: list[str] = []
        for provider in self._providers:
            try:
                return provider.complete_with_tools(messages, tools, **kwargs)
            except QuotaExhaustedError as exc:
                exhausted.append(exc.model_id)
                _log_fallback(exc.model_id)
        raise AllProvidersExhaustedError(exhausted)


def _log_fallback(model_id: str) -> None:
    """Log fallback message to stderr."""
    print(f"[fallback] {model_id} exhausted, trying next.", file=sys.stderr)
